from __future__ import annotations

import asyncio
import base64
import io
import json
import os
from dataclasses import dataclass, field

from PIL import Image

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Pixel mismatch threshold passed to pixelmatch (0–1 scale, same default as Playwright)
PIXEL_THRESHOLD = 0.10

# Hybrid score weights
VISUAL_WEIGHT = 0.80   # pixelmatch-based visual similarity
DOM_WEIGHT    = 0.20   # DOM / style-based similarity

VISION_PROMPT = """\
You are a visual QA expert comparing a reference design against a live Shopify implementation.

THREE IMAGES PROVIDED:
  Image 1 = REFERENCE DESIGN — what the page SHOULD look like
  Image 2 = SHOPIFY LIVE — what the Shopify page CURRENTLY looks like
  Image 3 = DIFF MAP — red/bright areas show pixel differences between Image 1 and Image 2

Page: {page}
Viewport: {breakpoint}px wide

YOUR TASK:
Look at Image 1 (reference) and Image 2 (Shopify) carefully. Find EVERY visible difference.
Be thorough — report ALL differences, not just the most obvious ones.

CHECK ALL OF THESE CATEGORIES:
1. FONTS — font family, size, weight, color on headings, body text, and buttons
2. COLORS — background colors of sections, hero, header, footer; button colors; text colors
3. LAYOUT — missing sections, extra sections, different column count, wrong element order
4. SPACING — padding above/below sections; gaps between elements; margins
5. BUTTONS — background color, size, shape, border-radius, text color
6. NAVIGATION — height, background, link colors, number of nav items, logo size
7. IMAGES — missing images, wrong aspect ratio, wrong image placement
8. TYPOGRAPHY — alignment, line height, letter spacing

Write each description as a plain English sentence:
  "The hero section background is white in Shopify but should be dark navy (reference design)"
  "The H1 heading uses Arial in Shopify but the reference design uses Playfair Display"
  "The primary button is 40px tall in Shopify but should be 56px (reference design)"
  "The navigation has 4 items in Shopify but the reference shows 6 items"

SEVERITY:
- critical: Element is completely missing or layout is entirely broken
- high: Clearly wrong — client would immediately notice this
- medium: Noticeably different — should be fixed before launch
- low: Minor polish difference

IGNORE ONLY:
- Product images, prices, review counts, stock levels (content, not design)
- Differences smaller than 3px that are not visible to the human eye

For the "suggestion" field, write a plain English developer instruction — NOT raw CSS code.
Good examples:
  "Update the hero background colour in the theme settings or section CSS to match the dark navy shown in the reference"
  "Change the H1 font family to Playfair Display in the theme typography settings"
  "Increase the primary button height to 56px and update the background colour to match the reference design"
  "Add the missing navigation items back to the header menu in the Shopify admin"
Bad examples (do NOT output raw CSS like these):
  "background-color: #0A0E1A; height: 56px"
  "font-family: Playfair Display, serif"

Return ONLY valid JSON — no markdown fences, no extra text:
{{
  "issues": [
    {{
      "type": "font|layout|spacing|color|button|navigation|section|image",
      "severity": "critical|high|medium|low",
      "element": "human-readable element name e.g. 'H1 heading', 'Hero section', 'Primary button', 'Navigation bar', 'Footer background', 'Section 2'",
      "description": "plain English sentence — what Shopify shows vs what the reference shows, with specific values",
      "suggestion": "plain English developer instruction explaining what to change and where — no raw CSS"
    }}
  ]
}}

You MUST report at least 3-5 issues if there are any visible differences. Do not under-report.
If the pages are truly pixel-perfect identical, return {{"issues": []}}.
"""

AI_ONLY_PROMPT = """\
You are a senior QA engineer doing a detailed visual review of a Shopify store page.
Your job is to find and report ALL visual and UX issues on this page.

Page: {page}
Viewport: {breakpoint}px wide

INSPECT THE SCREENSHOT CAREFULLY and report issues in these categories:

1. LAYOUT — overlapping elements, content cut off, broken grid, elements out of place, horizontal scroll
2. IMAGES — images that failed to load (broken), wrong proportions, distorted aspect ratio
3. SPACING — sections with no padding, text touching edges, inconsistent gaps
4. CONTRAST & COLORS — text hard to read against background, low contrast, unexpected colors
5. BUTTONS & CTAs — buttons with no text, invisible, missing, wrong color, or too small
6. NAVIGATION — overlapping nav items, missing hamburger menu on mobile, logo missing
7. TYPOGRAPHY — very small or very large text, wrong weight, hard to read
8. MISSING ELEMENTS — sections that appear empty, placeholder content, missing icons

Write each description as a clear sentence explaining what is wrong and where:
  "The hero image has not loaded and shows a broken placeholder"
  "Navigation items overlap each other at this viewport width"
  "The footer has no padding and text touches the edge of the screen"
  "The Add to Cart button has very low contrast and is hard to see"
  "The H1 heading font size is extremely small at approximately 12px"

SEVERITY:
- critical: Users cannot use the feature or content is unreadable/broken
- high: Clearly wrong — client would immediately flag this
- medium: Noticeable issue — should be fixed before launch
- low: Minor polish issue

Report EVERYTHING you see. Do not skip issues because they seem minor.
Aim for 5-15 issues on a typical page. Only return 0 if the page is truly flawless.

Return ONLY valid JSON — no markdown fences, no extra text:
{{
  "issues": [
    {{
      "type": "layout|spacing|color|button|navigation|image|font",
      "severity": "critical|high|medium|low",
      "element": "plain English element name e.g. 'Hero banner', 'Add to Cart button', 'Navigation bar', 'Footer', 'H1 heading', 'Section 2'",
      "description": "plain English sentence describing exactly what is wrong and where on the page",
      "suggestion": "specific actionable fix for a developer"
    }}
  ]
}}
"""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ComparisonResult:
    page: str
    breakpoint: int
    ssim_score: float          # normalized visual score 0–1 (visual_score / 100)
    diff_image_path: str
    heatmap_path: str
    ai_issues: list = field(default_factory=list)
    ai_status: str = "completed"
    dom_score: float | None = None      # 0–100, populated only in design mode
    hybrid_score: float | None = None   # 0–100, weighted blend of visual + DOM
    mismatch_pct: float = 0.0           # raw mismatch percentage (0–100)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class ComparisonEngine:
    # Class-level semaphore: max 5 concurrent AI calls across all instances
    _ai_semaphore = asyncio.Semaphore(5)

    def __init__(self, storage_path: str, openai_api_key: str = "",
                 aws_access_key: str = "", aws_bedrock_secret_key: str = "",
                 aws_region: str = "us-east-1", bedrock_model_id: str = "amazon.nova-pro-v1:0") -> None:
        self.openai_api_key = openai_api_key
        self.aws_access_key = aws_access_key
        self.aws_bedrock_secret_key = aws_bedrock_secret_key
        self.aws_region = aws_region
        self.bedrock_model_id = bedrock_model_id
        self.storage_path = storage_path

    # ------------------------------------------------------------------
    # Pixelmatch-style visual comparison
    # ------------------------------------------------------------------

    def compute_visual_diff(
        self,
        image1_path: str,
        image2_path: str,
        output_dir: str,
        threshold: float = PIXEL_THRESHOLD,
    ) -> tuple[float, float, str, str]:
        """Compare two screenshots using pixelmatch — the same algorithm Playwright uses
        internally for toHaveScreenshot().

        Differences are rendered as yellow (anti-aliased) / red (hard) pixels on a
        dark background, matching Playwright's diff image format.

        Args:
            image1_path: Path to the reference / design screenshot.
            image2_path: Path to the Shopify screenshot.
            output_dir:  Directory to write diff.png and heatmap.png.
            threshold:   Per-channel difference threshold (default 0.10).

        Returns:
            (visual_score_normalized, mismatch_pct, diff_path, heatmap_path)
            - visual_score_normalized: 0.0–1.0  (1.0 = identical), stored in ssim_score DB col
            - mismatch_pct:            0.0–100.0 percentage of mismatched pixels
        """
        from pixelmatch.contrib.PIL import pixelmatch

        os.makedirs(output_dir, exist_ok=True)

        img1 = Image.open(image1_path).convert("RGBA")
        img2 = Image.open(image2_path).convert("RGBA")

        # Normalise both images to the same (smaller) dimensions
        w = min(img1.width, img2.width)
        h = min(img1.height, img2.height)
        img1 = img1.resize((w, h), Image.LANCZOS)
        img2 = img2.resize((w, h), Image.LANCZOS)

        diff = Image.new("RGBA", (w, h))
        mismatch_count = pixelmatch(img1, img2, diff, threshold=threshold, includeAA=True)

        total_pixels = w * h
        mismatch_pct = (mismatch_count / total_pixels) * 100.0
        visual_score = max(0.0, 100.0 - mismatch_pct)
        visual_score_normalized = visual_score / 100.0  # 0–1 for DB compat

        diff_path = os.path.join(output_dir, "diff.png")
        diff.save(diff_path)

        # Heatmap: grayscale version of the diff image
        heatmap_path = os.path.join(output_dir, "heatmap.png")
        diff.convert("L").save(heatmap_path)

        return visual_score_normalized, mismatch_pct, diff_path, heatmap_path

    # ------------------------------------------------------------------
    # AI helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _encode_image(path: str, max_width: int = 1024, quality: int = 85) -> str:
        img = Image.open(path).convert("RGB")
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    # ------------------------------------------------------------------
    # GPT-4o vision call  (primary — best visual comparison accuracy)
    # ------------------------------------------------------------------

    async def _call_openai(self, messages: list, max_tokens: int = 4096) -> dict:
        """Call OpenAI GPT-4o with structured JSON output.

        Returns {"issues": None} immediately if the key looks like a non-OpenAI key
        (e.g. Anthropic keys start with "sk-ant-") so the caller falls back to Groq
        without wasting 3 retry attempts on a guaranteed auth failure.
        """
        if not self.openai_api_key or self.openai_api_key.startswith("sk-ant-"):
            return {"issues": None}  # signal caller to use Groq instead

        import logging
        _log = logging.getLogger(__name__)

        try:
            from openai import AsyncOpenAI, RateLimitError, APIError
        except ImportError:
            _log.warning("openai package not installed — falling back to Groq")
            return {"issues": None}  # None signals caller to try next provider

        client = AsyncOpenAI(api_key=self.openai_api_key)

        for attempt in range(3):
            async with self._ai_semaphore:
                try:
                    response = await client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0.1,
                        max_tokens=max_tokens,
                    )
                    content = response.choices[0].message.content.strip()
                    return json.loads(content)

                except RateLimitError:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    _log.warning("OpenAI rate limit after %d attempts — falling back to Groq", attempt + 1)
                    return {"issues": None}

                except json.JSONDecodeError:
                    return {"issues": []}

                except APIError as exc:
                    _log.warning("OpenAI API error (attempt %d): %s", attempt + 1, exc)
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return {"issues": None}  # signal to try Groq

                except Exception as exc:  # noqa: BLE001
                    _log.warning("OpenAI call failed (attempt %d): %s", attempt + 1, exc)
                    if attempt < 2:
                        await asyncio.sleep(1.5 ** attempt)
                        continue
                    return {"issues": None}

        return {"issues": None}

    # ------------------------------------------------------------------
    # AWS Bedrock Nova Pro vision call  (fallback)
    # ------------------------------------------------------------------

    async def _call_bedrock(self, messages: list, max_tokens: int = 2048) -> dict:
        """Call AWS Bedrock Nova Pro — used as fallback when OpenAI key is absent.

        Converts OpenAI-style messages (with data-URI image_url content) into the
        Bedrock Converse API format expected by amazon.nova-pro-v1:0.
        """
        import base64
        import logging
        _log = logging.getLogger(__name__)

        if not self.aws_access_key or not self.aws_bedrock_secret_key:
            _log.warning("AWS Bedrock credentials not configured — skipping Bedrock call")
            return {"issues": []}

        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError:
            _log.warning("boto3 not installed — cannot use Bedrock")
            return {"issues": []}

        client = boto3.client(
            "bedrock-runtime",
            region_name=self.aws_region,
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_bedrock_secret_key,
        )

        # Convert OpenAI-format messages → Bedrock Converse format
        bedrock_messages = []
        for msg in messages:
            content_blocks = []
            raw_content = msg.get("content", [])
            if isinstance(raw_content, str):
                content_blocks.append({"text": raw_content})
            else:
                for item in raw_content:
                    if item.get("type") == "text":
                        content_blocks.append({"text": item["text"]})
                    elif item.get("type") == "image_url":
                        url = item["image_url"]["url"]
                        if url.startswith("data:image/"):
                            _, b64data = url.split(",", 1)
                            img_bytes = base64.b64decode(b64data)
                            fmt = "jpeg"
                            if "image/png" in url:
                                fmt = "png"
                            elif "image/webp" in url:
                                fmt = "webp"
                            content_blocks.append({
                                "image": {
                                    "format": fmt,
                                    "source": {"bytes": img_bytes},
                                }
                            })
            bedrock_messages.append({"role": msg["role"], "content": content_blocks})

        loop = asyncio.get_event_loop()

        for attempt in range(3):
            async with self._ai_semaphore:
                try:
                    response = await loop.run_in_executor(
                        None,
                        lambda: client.converse(
                            modelId=self.bedrock_model_id,
                            messages=bedrock_messages,
                            inferenceConfig={
                                "maxTokens": max_tokens,
                                "temperature": 0.1,
                            },
                        ),
                    )

                    content_blocks = response["output"]["message"]["content"]
                    content = "".join(
                        block.get("text", "") for block in content_blocks
                    ).strip()

                    # Strip markdown fences
                    if "```" in content:
                        lines = content.splitlines()
                        content = "\n".join(
                            ln for ln in lines
                            if not ln.strip().startswith("```")
                        ).strip()

                    # Extract first {...} JSON block if model added extra prose
                    if not content.startswith("{"):
                        start = content.find("{")
                        end = content.rfind("}") + 1
                        if start != -1 and end > start:
                            content = content[start:end]

                    return json.loads(content)

                except ClientError as exc:
                    code = exc.response.get("Error", {}).get("Code", "")
                    if code == "ThrottlingException" and attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    _log.warning("Bedrock API error (attempt %d): %s", attempt + 1, exc)
                    if attempt < 2:
                        await asyncio.sleep(1.5 ** attempt)
                        continue
                    return {"issues": []}
                except json.JSONDecodeError:
                    return {"issues": []}
                except Exception as exc:  # noqa: BLE001
                    _log.warning("Bedrock call failed (attempt %d): %s", attempt + 1, exc)
                    if attempt < 2:
                        await asyncio.sleep(1.5 ** attempt)
                        continue
                    return {"issues": []}

        return {"issues": []}

    # ------------------------------------------------------------------
    # Unified vision call — GPT-4o → Bedrock fallback
    # ------------------------------------------------------------------

    async def _call_vision(self, messages: list, max_tokens: int = 4096) -> dict:
        """Route to the best available vision API.

        Priority:
          1. OpenAI GPT-4o       — if OPENAI_API_KEY is configured
          2. AWS Bedrock Nova Pro — fallback

        Returns {"issues": [...]} in all cases.
        """
        import logging
        _log = logging.getLogger(__name__)

        if self.openai_api_key:
            result = await self._call_openai(messages, max_tokens)
            # None in "issues" means OpenAI failed and wants us to fall back
            if result.get("issues") is not None:
                return result

        # Fallback: AWS Bedrock Nova Pro
        if self.aws_access_key and self.aws_bedrock_secret_key:
            return await self._call_bedrock(messages, min(max_tokens, 4096))

        _log.error(
            "No vision API key configured — set OPENAI_API_KEY or AWS Bedrock credentials in .env. "
            "Zero issues will be returned until a key is provided."
        )
        return {"issues": []}

    # ------------------------------------------------------------------
    # Design-vs-Shopify visual comparison (3 images → GPT-4o / Bedrock)
    # ------------------------------------------------------------------

    async def analyze_with_groq(
        self,
        design_path: str,
        shopify_path: str,
        diff_path: str,
        page: str = "",
        breakpoint: int = 0,
    ) -> dict:
        """Analyse reference vs Shopify screenshots. Uses GPT-4o if available, else AWS Bedrock."""
        design_b64  = self._encode_image(design_path, max_width=1280)
        shopify_b64 = self._encode_image(shopify_path, max_width=1280)
        diff_b64    = self._encode_image(diff_path, max_width=1280)

        prompt = VISION_PROMPT.format(page=page or "unknown", breakpoint=breakpoint or "N/A")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{design_b64}",  "detail": "high"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{shopify_b64}", "detail": "high"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{diff_b64}",    "detail": "low"}},
                ],
            }
        ]
        return await self._call_vision(messages)

    # ------------------------------------------------------------------
    # AI-only analysis (single Shopify screenshot, no design reference)
    # ------------------------------------------------------------------

    async def analyze_single_page(
        self,
        shopify_path: str,
        page: str = "",
        breakpoint: int = 0,
    ) -> dict:
        """Analyse a single Shopify screenshot without a design reference.

        Uses the same OpenAI → Groq fallback chain as the design comparison path
        so GPT-4o is tried first when an OpenAI key is configured.
        """
        shopify_b64 = self._encode_image(shopify_path, max_width=1280)
        prompt = AI_ONLY_PROMPT.format(page=page or "unknown", breakpoint=breakpoint or "N/A")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{shopify_b64}", "detail": "high"}},
                ],
            }
        ]
        return await self._call_vision(messages, max_tokens=4096)

    # ------------------------------------------------------------------
    # Hybrid score calculator
    # ------------------------------------------------------------------

    @staticmethod
    def compute_hybrid_score(visual_score_normalized: float, dom_score: float | None) -> float:
        """Blend visual score and DOM style score into a final 0–100 score.

        Args:
            visual_score_normalized: Pixelmatch visual score in [0, 1].
            dom_score:               DOM comparison score in [0, 100], or None.

        Returns:
            Hybrid score in [0, 100].
        """
        visual_pct = visual_score_normalized * 100  # convert [0,1] → [0,100]
        if dom_score is None:
            return round(visual_pct, 2)
        return round(visual_pct * VISUAL_WEIGHT + dom_score * DOM_WEIGHT, 2)

    # ------------------------------------------------------------------
    # Main compare — reference mode (pixelmatch visual diff + Groq issues)
    # ------------------------------------------------------------------

    async def compare(
        self,
        design_path: str,
        shopify_path: str,
        output_dir: str,
        page: str,
        breakpoint: int,
    ) -> ComparisonResult:
        os.makedirs(output_dir, exist_ok=True)

        visual_norm, mismatch_pct, diff_path, heatmap_path = self.compute_visual_diff(
            design_path, shopify_path, output_dir
        )

        ai_issues: list = []
        ai_status = "completed"

        result = await self.analyze_with_groq(
            design_path, shopify_path, diff_path,
            page=page, breakpoint=breakpoint,
        )
        ai_issues = result.get("issues", [])

        return ComparisonResult(
            page=page,
            breakpoint=breakpoint,
            ssim_score=visual_norm,
            diff_image_path=diff_path,
            heatmap_path=heatmap_path,
            ai_issues=ai_issues,
            ai_status=ai_status,
            mismatch_pct=mismatch_pct,
        )

    # ------------------------------------------------------------------
    # AI-only compare (no design reference)
    # ------------------------------------------------------------------

    async def compare_ai_only(
        self,
        shopify_path: str,
        output_dir: str,
        page: str,
        breakpoint: int,
    ) -> ComparisonResult:
        """Run AI-only analysis on a single Shopify screenshot."""
        os.makedirs(output_dir, exist_ok=True)

        dummy_diff = os.path.join(output_dir, "diff.png")
        dummy_heatmap = os.path.join(output_dir, "heatmap.png")
        if not os.path.exists(dummy_diff):
            Image.new("RGB", (10, 10), color=(128, 128, 128)).save(dummy_diff)
        if not os.path.exists(dummy_heatmap):
            Image.new("L", (10, 10), color=128).save(dummy_heatmap)

        ai_issues: list = []
        ai_status = "completed"

        try:
            result = await self.analyze_single_page(
                shopify_path, page=page, breakpoint=breakpoint
            )
            ai_issues = result.get("issues", [])
        except Exception:
            ai_status = "failed"

        return ComparisonResult(
            page=page,
            breakpoint=breakpoint,
            ssim_score=0.0,
            diff_image_path=dummy_diff,
            heatmap_path=dummy_heatmap,
            ai_issues=ai_issues,
            ai_status=ai_status,
            mismatch_pct=0.0,
        )
