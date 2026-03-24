from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# CSS injected into every captured page to suppress UI noise
# ---------------------------------------------------------------------------

CLEANUP_CSS = """
/* Hide Shopify preview bar */
#preview-bar-iframe,
.shopify-preview-bar {
    display: none !important;
}

/* Hide common cookie banners */
#cookie-banner,
.cookie-banner,
.cookie-notice,
.cookie-consent,
[id*="cookie"],
[class*="cookie"],
.cc-window,
#onetrust-banner-sdk {
    display: none !important;
}

/* Hide Drift chat widget */
#drift-widget,
#drift-frame-controller,
#drift-frame-chat,
.drift-conductor-item {
    display: none !important;
}

/* Hide Tidio chat widget */
#tidio-chat,
#tidio-chat-iframe {
    display: none !important;
}

/* Hide Intercom widget */
#intercom-container,
.intercom-lightweight-app,
.intercom-launcher,
#intercom-frame {
    display: none !important;
}
"""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class CaptureResult:
    page: str
    breakpoint: int
    source: str
    image_path: str
    status: str = "success"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class CaptureEngine:
    def __init__(self, storage_path: str) -> None:
        self.storage_path = storage_path

    async def capture_page(
        self,
        url: str,
        page_name: str,
        run_dir: str,
        source: str,
        breakpoints: list[int],
        password: str | None = None,
        wait_after_load_ms: int = 2000,
    ) -> list[CaptureResult]:
        """Capture screenshots at each breakpoint and return a list of CaptureResult."""
        results: list[CaptureResult] = []

        for bp in breakpoints:
            try:
                image_path = await self._take_screenshot(
                    url=url,
                    page_name=page_name,
                    run_dir=run_dir,
                    source=source,
                    breakpoint=bp,
                    password=password,
                    wait_after_load_ms=wait_after_load_ms,
                )
                results.append(
                    CaptureResult(
                        page=page_name,
                        breakpoint=bp,
                        source=source,
                        image_path=image_path,
                        status="success",
                    )
                )
            except Exception:
                # Retry once
                try:
                    image_path = await self._take_screenshot(
                        url=url,
                        page_name=page_name,
                        run_dir=run_dir,
                        source=source,
                        breakpoint=bp,
                        password=password,
                        wait_after_load_ms=wait_after_load_ms,
                    )
                    results.append(
                        CaptureResult(
                            page=page_name,
                            breakpoint=bp,
                            source=source,
                            image_path=image_path,
                            status="success",
                        )
                    )
                except Exception:
                    results.append(
                        CaptureResult(
                            page=page_name,
                            breakpoint=bp,
                            source=source,
                            image_path="",
                            status="capture_failed",
                        )
                    )

        return results

    async def _take_screenshot(
        self,
        url: str,
        page_name: str,
        run_dir: str,
        source: str,
        breakpoint: int,
        password: str | None = None,
        wait_after_load_ms: int = 2000,
    ) -> str:
        """Launch Playwright, capture a full-page screenshot, and return the file path."""
        output_dir = os.path.join(self.storage_path, run_dir, source, page_name)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{breakpoint}.png")

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": breakpoint, "height": 900}
            )
            page = await context.new_page()

            # Handle password-protected Shopify stores
            if password and "myshopify.com" in url:
                await page.goto(url, wait_until="networkidle")
                await page.fill("input[type='password']", password)
                await page.click("button[type='submit'], input[type='submit']")
                await page.wait_for_load_state("networkidle")

            # Navigate to target URL
            await page.goto(url, wait_until="networkidle")

            # Inject cleanup CSS to suppress UI noise
            await page.add_style_tag(content=CLEANUP_CSS)

            # Allow dynamic content to settle
            await asyncio.sleep(wait_after_load_ms / 1000)

            # Full-page screenshot
            await page.screenshot(path=output_path, full_page=True)

            await browser.close()

        return output_path
