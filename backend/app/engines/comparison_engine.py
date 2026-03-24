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

VISION_PROMPT = """You are a senior Shopify developer performing a quality assurance review.
You will be given three images: a design mockup, a live Shopify implementation, and a visual diff.

Your task is to identify UI discrepancies between the design and the Shopify implementation.

IMPORTANT — Ignore the following as they are expected to differ:
- Product images, photos, or any image assets
- Product prices and pricing information
- Product names, titles, and descriptions
- Color swatches and product variants
- Any dynamic or user-generated content

Focus exclusively on structural and stylistic issues such as:
- Font family, size, weight, and style differences
- Layout and structural problems (grid, flexbox, positioning)
- Spacing issues (margin, padding, gap)
- Color differences in UI components (buttons, backgrounds, borders, text)
- Button styles, shapes, sizes, and states
- Navigation components and menus
- UI component discrepancies (cards, badges, icons, dividers)
- Alignment and proportional differences

Return ONLY a valid JSON object with no additional text or markdown, in this exact format:
{
  "issues": [
    {
      "type": "string — category of issue (e.g. font, spacing, color, layout, button)",
      "severity": "string — one of: critical, high, medium, low",
      "element": "string — the UI element affected",
      "description": "string — clear description of the discrepancy",
      "location": {"x": 0, "y": 0},
      "selector": "string — CSS selector for the element if identifiable",
      "suggestion": "string — recommended fix"
    }
  ]
}

If no issues are found, return: {"issues": []}
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
        """Compute SSIM between two images.

        Returns (score, diff_image_path, heatmap_path).
        Both output images are saved to output_dir.
        """
        os.makedirs(output_dir, exist_ok=True)

        img1 = Image.open(image1_path).convert("RGB")
        img2 = Image.open(image2_path).convert("RGB")

        # Resize both images to the minimum dimensions of the two
        min_w = min(img1.width, img2.width)
        min_h = min(img1.height, img2.height)
        img1 = img1.resize((min_w, min_h), Image.LANCZOS)
        img2 = img2.resize((min_w, min_h), Image.LANCZOS)

        arr1 = np.array(img1, dtype=np.float64)
        arr2 = np.array(img2, dtype=np.float64)

        score, diff = ssim(arr1, arr2, channel_axis=2, full=True, data_range=255)

        # Diff image: highlight differences in red
        # diff values are in [0,1]; low diff = high difference
        diff_normalized = (1 - diff) * 255  # shape (H, W, 3)
        diff_rgb = np.zeros_like(arr1, dtype=np.uint8)
        diff_rgb[:, :, 0] = np.clip(diff_normalized.mean(axis=2), 0, 255).astype(np.uint8)  # red channel only
        diff_image = Image.fromarray(diff_rgb, mode="RGB")
        diff_path = os.path.join(output_dir, "diff.png")
        diff_image.save(diff_path)

        # Heatmap: mean of diff_normalized across channels, saved as grayscale
        heatmap_arr = np.clip(diff_normalized.mean(axis=2), 0, 255).astype(np.uint8)
        heatmap_image = Image.fromarray(heatmap_arr, mode="L")
        heatmap_path = os.path.join(output_dir, "heatmap.png")
        heatmap_image.save(heatmap_path)

        return float(score), diff_path, heatmap_path

    # ------------------------------------------------------------------
    # Groq AI Vision analysis
    # ------------------------------------------------------------------

    async def analyze_with_groq(
        self,
        design_path: str,
        shopify_path: str,
        diff_path: str,
    ) -> dict:
        """Send images to Groq vision model and return parsed issues dict.

        Uses a class-level semaphore to limit concurrency to 3 simultaneous
        calls. Retries up to 3 times on HTTP 429 (rate limit) with exponential
        backoff.
        """
        from groq import AsyncGroq, RateLimitError

        def _encode_image(path: str, max_width: int = 1024, quality: int = 85) -> str:
            """Resize to max_width, compress as JPEG, base64-encode."""
            img = Image.open(path).convert("RGB")
            if img.width > max_width:
                ratio = max_width / img.width
                new_h = int(img.height * ratio)
                img = img.resize((max_width, new_h), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            return base64.b64encode(buf.getvalue()).decode("utf-8")

        design_b64 = _encode_image(design_path)
        shopify_b64 = _encode_image(shopify_path)
        diff_b64 = _encode_image(diff_path)

        client = AsyncGroq(api_key=self.groq_api_key)

        for attempt in range(3):
            async with self._groq_semaphore:
                try:
                    response = await client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": VISION_PROMPT},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{design_b64}",
                                        },
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{shopify_b64}",
                                        },
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{diff_b64}",
                                        },
                                    },
                                ],
                            }
                        ],
                        temperature=0.1,
                        max_tokens=2048,
                    )

                    content = response.choices[0].message.content.strip()

                    # Strip markdown code fences if present
                    if content.startswith("```"):
                        lines = content.splitlines()
                        content = "\n".join(
                            line for line in lines if not line.startswith("```")
                        ).strip()

                    return json.loads(content)

                except RateLimitError:
                    if attempt < 2:
                        wait = 2 ** attempt  # 1s, 2s
                        await asyncio.sleep(wait)
                        continue
                    raise

        # Should not reach here
        return {"issues": []}

    # ------------------------------------------------------------------
    # Main compare entry point
    # ------------------------------------------------------------------

    async def compare(
        self,
        design_path: str,
        shopify_path: str,
        output_dir: str,
        page: str,
        breakpoint: int,
    ) -> ComparisonResult:
        """Run SSIM comparison; invoke Groq AI vision if score is below threshold.

        Returns a ComparisonResult with all relevant paths and AI issues.
        """
        os.makedirs(output_dir, exist_ok=True)

        score, diff_path, heatmap_path = self.compute_ssim(
            design_path, shopify_path, output_dir
        )

        ai_issues: list = []
        ai_status = "completed"

        if score < SSIM_THRESHOLD:
            try:
                result = await self.analyze_with_groq(design_path, shopify_path, diff_path)
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
