from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import time
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SSIM_THRESHOLD = 0.95

VISION_PROMPT = """\
You are a senior Shopify QA engineer performing a detailed visual quality audit.

You are given three images:
  1. DESIGN — the approved design mockup (Framer or Figma)
  2. SHOPIFY — the live Shopify implementation screenshot
  3. DIFF — a visual difference heatmap (bright = high difference)

Page: {page}
Viewport: {breakpoint}px

IGNORE these differences (expected):
- Product photos, hero images, banners, and image assets
- Product prices, SKUs, and inventory data
- Product names, titles, descriptions, and reviews
- Color swatches, size selectors, variant options
- Any user-generated or dynamic content

FOCUS on structural and stylistic discrepancies:
- Font family, size, weight, line-height (e.g. "font-size should be 18px, currently 14px")
- Layout: grid misalignment, wrong column count, broken flex layout
- Spacing: wrong margin/padding/gap values (e.g. "section padding should be 80px, currently 40px")
- Colors: wrong button color, background, border color (include actual hex codes)
- Button/CTA: wrong size, shape, border-radius, padding, missing hover state
- Navigation: wrong height, font, spacing, missing items
- Component mismatches: wrong card style, missing borders, wrong icon size
- Alignment: text/element misaligned relative to design

Return ONLY valid JSON (no markdown, no extra text):
{{
  "issues": [
    {{
      "type": "font|spacing|color|layout|button|navigation|image|component",
      "severity": "critical|high|medium|low",
      "element": "human-readable element name (e.g. 'Add to Cart button', 'Page heading', 'Navigation bar', 'Hero banner')",
      "description": "specific discrepancy observed (e.g. 'Button background is #333 in Shopify but #1a73e8 in design')",
      "suggestion": "exact CSS fix (e.g. 'Change background-color: #1a73e8; border-radius: 8px;')"
    }}
  ]
}}

Do NOT include "location", "selector", or "x"/"y" fields.
Provide specific, actionable suggestions with CSS property values. If no real differences exist, return {{"issues": []}}.
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
    # Class-level semaphore: max 3 concurrent Groq calls across all instances
    _groq_semaphore = asyncio.Semaphore(3)

    def __init__(self, groq_api_key: str, storage_path: str) -> None:
        self.groq_api_key = groq_api_key
        self.storage_path = storage_path

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
    # Groq helpers
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

    async def _call_groq(self, messages: list, max_tokens: int = 2048) -> dict:
        from groq import AsyncGroq, RateLimitError

        client = AsyncGroq(api_key=self.groq_api_key)

        for attempt in range(3):
            async with self._groq_semaphore:
                try:
                    response = await client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=messages,
                        temperature=0.1,
                        max_tokens=max_tokens,
                    )
                    content = response.choices[0].message.content.strip()
                    # Strip markdown fences
                    if content.startswith("```"):
                        lines = content.splitlines()
                        content = "\n".join(
                            ln for ln in lines if not ln.startswith("```")
                        ).strip()
                    return json.loads(content)

                except RateLimitError:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise
                except json.JSONDecodeError:
                    return {"issues": []}

        return {"issues": []}

    # ------------------------------------------------------------------
    # Design-vs-Shopify comparison (3 images → Groq)
    # ------------------------------------------------------------------

    async def analyze_with_groq(
        self,
        design_path: str,
        shopify_path: str,
        diff_path: str,
        page: str = "",
        breakpoint: int = 0,
    ) -> dict:
        design_b64 = self._encode_image(design_path)
        shopify_b64 = self._encode_image(shopify_path)
        diff_b64 = self._encode_image(diff_path)

        prompt = VISION_PROMPT.format(page=page or "unknown", breakpoint=breakpoint or "N/A")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{design_b64}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{shopify_b64}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{diff_b64}"}},
                ],
            }
        ]
        return await self._call_groq(messages)

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
        shopify_b64 = self._encode_image(shopify_path)
        prompt = AI_ONLY_PROMPT.format(page=page or "unknown", breakpoint=breakpoint or "N/A")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{shopify_b64}"}},
                ],
            }
        ]
        return await self._call_groq(messages)

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
    ) -> ComparisonResult:
        os.makedirs(output_dir, exist_ok=True)

        score, diff_path, heatmap_path = self.compute_ssim(
            design_path, shopify_path, output_dir
        )

        ai_issues: list = []
        ai_status = "completed"

        if score < SSIM_THRESHOLD:
            try:
                result = await self.analyze_with_groq(
                    design_path, shopify_path, diff_path,
                    page=page, breakpoint=breakpoint,
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
