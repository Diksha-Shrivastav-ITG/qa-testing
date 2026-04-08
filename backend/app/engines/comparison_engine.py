from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import time
from dataclasses import dataclass, field

import logging
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SSIM_THRESHOLD = 0.95

VISION_PROMPT = """\
You are an expert UI/UX QA engineer comparing a REFERENCE DESIGN against a LIVE WEBSITE.

You are given three images:
  1. DESIGN — the reference design (how it SHOULD look)
  2. SHOPIFY — the live website screenshot (how it ACTUALLY looks)
  3. DIFF — a visual difference heatmap (bright areas = high difference)

Page: {page}
Viewport: {breakpoint}px
SSIM Score: {ssim_pct}% (100% = identical, lower = more differences)

IMPORTANT: The SSIM score is {ssim_pct}%, which means there ARE visual differences. You MUST find and report them. Do NOT return an empty issues list when SSIM is below 90%.

IGNORE these expected differences:
- Different product photos, hero images (different image content is OK)
- Different product prices, names, reviews, stock levels
- Different promotional banners or sale text

YOU MUST REPORT these structural/stylistic differences:
- Font differences: size, weight, family, line-height, letter-spacing
  Example: "Heading font-size is ~40px in design but ~32px on live site"
- Spacing differences: padding, margin, gap between sections
  Example: "Section padding is ~80px in design but ~40px on live site"
- Color differences: background colors, text colors, button colors
  Example: "CTA button is #1a73e8 (blue) in design but #333333 (dark gray) on live site"
- Layout differences: column count, flex direction, grid structure, alignment
  Example: "Features section uses 4 columns in design but 3 columns on live site"
- Button/CTA differences: size, border-radius, padding, colors
- Navigation differences: height, layout, spacing, font
- Missing or extra sections: sections present in design but missing on live site
- Border and shadow differences: missing borders, wrong border-radius, shadows

For EACH issue, be extremely specific with approximate pixel values and color codes.
Compare section by section from top to bottom.

Return ONLY valid JSON (no markdown, no extra text):
{{
  "issues": [
    {{
      "type": "font|spacing|color|layout|button|navigation|component|missing_section",
      "severity": "critical|high|medium|low",
      "element": "human-readable element name (e.g. 'Hero section heading', 'Add to Cart button', 'Navigation bar')",
      "description": "SPECIFIC difference with values — e.g. 'Hero heading font-size is approximately 48px in design but 36px on live site. Font weight appears to be 700 (bold) in design but 400 (regular) on live site.'",
      "suggestion": "exact CSS fix — e.g. 'Change font-size: 48px; font-weight: 700;'"
    }}
  ]
}}

Rules:
- You MUST report at least 3-5 issues when SSIM is below 80%.
- Be specific: include approximate px values, hex colors, and CSS properties.
- Compare the pages section by section from top to bottom.
- Do NOT include "location", "selector", or "x"/"y" fields.
"""

AI_ONLY_PROMPT = """\
You are a senior Shopify QA tester doing a final review before launch.
Think like a human QA — only flag things a client or developer would ACTUALLY need to fix.

Page: {page}
Viewport: {breakpoint}px

RULES — read carefully:
- Only report REAL, VISIBLE problems that hurt the user experience or look broken.
- Do NOT report things that are normal for Shopify themes (e.g. product grids, standard footer layouts).
- Do NOT report subjective style preferences ("I would use a different font").
- Do NOT report content issues (product names, prices, stock levels, review counts).
- Do NOT report responsive issues on the wrong viewport (don't flag mobile issues on desktop screenshots).
- MAXIMUM 5-8 issues per page. If the page looks good, report 0-2 issues.

Only flag these categories:
1. BROKEN layout: overlapping elements, content cut off, horizontal scroll, broken grid
2. BROKEN images: missing/broken images (not loaded), severely wrong aspect ratio
3. CRITICAL spacing: sections touching each other, zero padding around content, text touching edges
4. POOR contrast: text unreadable against background (WCAG AA fail level)
5. BROKEN buttons: buttons with no visible text, buttons that look disabled but shouldn't be
6. BROKEN navigation: menu items overlapping, dropdown cut off, hamburger menu not visible

Severity guide:
- critical: Something is BROKEN — user cannot use the feature or content is unreadable
- high: Clearly wrong — client would flag this immediately
- medium: Noticeable imperfection — developer should fix but not a blocker
- low: Minor polish — nice to fix but acceptable for launch

Return ONLY valid JSON:
{{
  "issues": [
    {{
      "type": "layout|spacing|color|button|navigation|image|content",
      "severity": "critical|high|medium|low",
      "element": "human-readable name of the element (e.g. 'Hero banner image', 'Add to Cart button', 'Main navigation bar', 'Footer newsletter section')",
      "description": "what is actually wrong — be specific about what you SEE in the screenshot",
      "suggestion": "specific actionable fix a developer can implement"
    }}
  ]
}}

IMPORTANT:
- Do NOT include "location", "selector", or "x"/"y" fields — they are not needed.
- The "element" field should be a plain English name like "Product grid section" or "Header logo", NOT a CSS selector.
- If the page looks professional and well-built, return {{"issues": []}} or very few issues.
"""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ComparisonResult:
    page: str
    breakpoint: int
    ssim_score: float
    diff_image_path: str
    heatmap_path: str
    ai_issues: list = field(default_factory=list)
    ai_status: str = "completed"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class ComparisonEngine:
    # Class-level semaphore: max 3 concurrent Bedrock calls across all instances
    _ai_semaphore = asyncio.Semaphore(5)

    def __init__(
        self,
        storage_path: str,
        aws_access_key: str = "",
        aws_secret_key: str = "",
        aws_region: str = "us-east-1",
        bedrock_model_id: str = "amazon.nova-pro-v1:0",
        groq_api_key: str = "",  # kept for backward compat, not used
    ) -> None:
        self.storage_path = storage_path
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.aws_region = aws_region
        self.bedrock_model_id = bedrock_model_id

    # ------------------------------------------------------------------
    # SSIM computation
    # ------------------------------------------------------------------

    def compute_ssim(
        self,
        image1_path: str,
        image2_path: str,
        output_dir: str,
    ) -> tuple[float, str, str]:
        os.makedirs(output_dir, exist_ok=True)

        img1 = Image.open(image1_path).convert("RGB")
        img2 = Image.open(image2_path).convert("RGB")

        min_w = min(img1.width, img2.width)
        min_h = min(img1.height, img2.height)
        img1 = img1.resize((min_w, min_h), Image.LANCZOS)
        img2 = img2.resize((min_w, min_h), Image.LANCZOS)

        arr1 = np.array(img1, dtype=np.float64)
        arr2 = np.array(img2, dtype=np.float64)

        score, diff = ssim(arr1, arr2, channel_axis=2, full=True, data_range=255)

        diff_normalized = (1 - diff) * 255
        diff_rgb = np.zeros_like(arr1, dtype=np.uint8)
        diff_rgb[:, :, 0] = np.clip(diff_normalized.mean(axis=2), 0, 255).astype(np.uint8)
        diff_image = Image.fromarray(diff_rgb, mode="RGB")
        diff_path = os.path.join(output_dir, "diff.png")
        diff_image.save(diff_path)

        heatmap_arr = np.clip(diff_normalized.mean(axis=2), 0, 255).astype(np.uint8)
        heatmap_image = Image.fromarray(heatmap_arr, mode="L")
        heatmap_path = os.path.join(output_dir, "heatmap.png")
        heatmap_image.save(heatmap_path)

        return float(score), diff_path, heatmap_path

    # ------------------------------------------------------------------
    # Image encoding helper
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

    @staticmethod
    def _encode_image_bytes(path: str, max_width: int = 1024, quality: int = 85) -> bytes:
        img = Image.open(path).convert("RGB")
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # AWS Bedrock AI caller
    # ------------------------------------------------------------------

    async def _call_bedrock(self, prompt: str, image_bytes_list: list[bytes], max_tokens: int = 2048) -> dict:
        """Call AWS Bedrock with text + images and return parsed JSON."""
        import boto3

        def _invoke():
            client = boto3.client(
                "bedrock-runtime",
                region_name=self.aws_region,
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
            )

            # Build content blocks: text + images
            content_blocks = [{"text": prompt}]
            for idx, img_bytes in enumerate(image_bytes_list):
                content_blocks.append({
                    "image": {
                        "format": "jpeg",
                        "source": {"bytes": img_bytes},
                    }
                })

            body = {
                "messages": [
                    {"role": "user", "content": content_blocks}
                ],
                "inferenceConfig": {
                    "maxTokens": max_tokens,
                    "temperature": 0.1,
                },
            }

            response = client.converse(
                modelId=self.bedrock_model_id,
                messages=body["messages"],
                inferenceConfig=body["inferenceConfig"],
            )

            # Log token usage
            usage = response.get("usage", {})
            input_tokens = usage.get("inputTokens", 0)
            output_tokens = usage.get("outputTokens", 0)
            total_tokens = usage.get("totalTokens", input_tokens + output_tokens)
            stop_reason = response.get("stopReason", "unknown")
            num_images = len(image_bytes_list)
            total_image_kb = round(sum(len(b) for b in image_bytes_list) / 1024, 1)
            prompt_chars = len(prompt)

            logger.info(
                "BEDROCK_USAGE | model=%s | input_tokens=%d | output_tokens=%d | total_tokens=%d | "
                "stop_reason=%s | images=%d | image_size_kb=%.1f | prompt_chars=%d",
                self.bedrock_model_id, input_tokens, output_tokens, total_tokens,
                stop_reason, num_images, total_image_kb, prompt_chars,
            )

            # Extract text from response
            output_message = response.get("output", {}).get("message", {})
            content_list = output_message.get("content", [])
            text = ""
            for block in content_list:
                if "text" in block:
                    text += block["text"]
            return text.strip()

        for attempt in range(3):
            async with self._ai_semaphore:
                try:
                    loop = asyncio.get_event_loop()
                    content = await loop.run_in_executor(None, _invoke)

                    # Strip markdown fences
                    if content.startswith("```"):
                        lines = content.splitlines()
                        content = "\n".join(
                            ln for ln in lines if not ln.startswith("```")
                        ).strip()
                    return json.loads(content)

                except json.JSONDecodeError:
                    return {"issues": []}
                except Exception as exc:
                    if attempt < 2 and "throttl" in str(exc).lower():
                        await asyncio.sleep(2 ** attempt)
                        continue
                    if attempt < 2:
                        await asyncio.sleep(1)
                        continue
                    raise

        return {"issues": []}

    # ------------------------------------------------------------------
    # Design-vs-Shopify comparison (3 images → Bedrock)
    # ------------------------------------------------------------------

    async def analyze_with_ai(
        self,
        design_path: str,
        shopify_path: str,
        diff_path: str,
        page: str = "",
        breakpoint: int = 0,
        ssim_score: float = 0.0,
        design_css: str = "",
        shopify_css: str = "",
    ) -> dict:
        design_bytes = self._encode_image_bytes(design_path)
        shopify_bytes = self._encode_image_bytes(shopify_path)
        diff_bytes = self._encode_image_bytes(diff_path)

        ssim_pct = round(ssim_score * 100, 1)
        prompt = VISION_PROMPT.format(page=page or "unknown", breakpoint=breakpoint or "N/A", ssim_pct=ssim_pct)

        # Append real CSS data so AI uses actual values, not guesses
        if design_css or shopify_css:
            prompt += "\n\n=== ACTUAL COMPUTED CSS VALUES (use these exact values, do NOT guess) ===\n"
            if design_css:
                prompt += f"\nDESIGN CSS (extracted from reference site):\n{design_css}\n"
            if shopify_css:
                prompt += f"\nSHOPIFY CSS (extracted from live site):\n{shopify_css}\n"
            prompt += "\nIMPORTANT: Use the EXACT values from the CSS data above. Do NOT approximate or guess pixel values. Compare the actual computed values element by element.\n"

        return await self._call_bedrock(prompt, [design_bytes, shopify_bytes, diff_bytes])

    # ------------------------------------------------------------------
    # AI-only analysis (single Shopify screenshot, no design reference)
    # ------------------------------------------------------------------

    async def analyze_single_page(
        self,
        shopify_path: str,
        page: str = "",
        breakpoint: int = 0,
    ) -> dict:
        """Analyze a single Shopify screenshot without a design reference."""
        shopify_bytes = self._encode_image_bytes(shopify_path)
        prompt = AI_ONLY_PROMPT.format(page=page or "unknown", breakpoint=breakpoint or "N/A")

        return await self._call_bedrock(prompt, [shopify_bytes])

    # ------------------------------------------------------------------
    # Main compare (design mode)
    # ------------------------------------------------------------------

    async def compare(
        self,
        design_path: str,
        shopify_path: str,
        output_dir: str,
        page: str,
        breakpoint: int,
        design_css: str = "",
        shopify_css: str = "",
    ) -> ComparisonResult:
        os.makedirs(output_dir, exist_ok=True)

        score, diff_path, heatmap_path = self.compute_ssim(
            design_path, shopify_path, output_dir
        )

        ai_issues: list = []
        ai_status = "completed"

        # Always run AI analysis for design comparison to get detailed written differences
        try:
            result = await self.analyze_with_ai(
                design_path, shopify_path, diff_path,
                page=page, breakpoint=breakpoint,
                ssim_score=score,
                design_css=design_css,
                shopify_css=shopify_css,
            )
            ai_issues = result.get("issues", [])
        except Exception:
            ai_status = "failed"

        return ComparisonResult(
            page=page,
            breakpoint=breakpoint,
            ssim_score=score,
            diff_image_path=diff_path,
            heatmap_path=heatmap_path,
            ai_issues=ai_issues,
            ai_status=ai_status,
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

        # Create a dummy diff path (just copy the shopify image as placeholder)
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
            ssim_score=0.0,  # No SSIM without a reference image
            diff_image_path=dummy_diff,
            heatmap_path=dummy_heatmap,
            ai_issues=ai_issues,
            ai_status=ai_status,
        )
