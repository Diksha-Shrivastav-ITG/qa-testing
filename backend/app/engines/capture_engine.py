from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# CSS injected into every captured page to suppress UI noise
# ---------------------------------------------------------------------------

CLEANUP_CSS = """
/* Hide Shopify preview bar (all variants) */
#preview-bar-iframe,
.shopify-preview-bar,
#shopify-theme-controls,
[id*="preview-bar"],
[class*="preview-bar"],
iframe[src*="preview-bar"],
.theme-preview-bar,
[data-preview-bar],
x-shopify-y { /* Shopify custom element for preview */
    display: none !important;
    height: 0 !important;
    max-height: 0 !important;
    overflow: hidden !important;
}
/* Remove top padding/margin that the preview bar adds to body */
body {
    margin-top: 0 !important;
    padding-top: 0 !important;
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

    async def _wait_for_page_stable(self, page, timeout_s: float = 8) -> None:
        """Wait for page to load: quick scroll + wait for images. Capped at 8s total."""
        try:
            await asyncio.wait_for(self._do_page_stable(page), timeout=timeout_s)
        except (asyncio.TimeoutError, Exception):
            pass

    async def _do_page_stable(self, page) -> None:
        """Quick scroll to trigger lazy loading, then wait for images."""
        # Fast scroll to bottom and back
        await page.evaluate("""
            () => {
                window.scrollTo(0, document.body.scrollHeight);
            }
        """)
        await asyncio.sleep(0.5)
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)

        # Wait for images (max 3s)
        await page.evaluate("""
            () => new Promise(resolve => {
                const images = Array.from(document.images);
                if (!images.length || images.every(img => img.complete)) { resolve(); return; }
                let loaded = 0;
                const total = images.length;
                const check = () => { loaded++; if (loaded >= total) resolve(); };
                images.forEach(img => {
                    if (img.complete) { loaded++; }
                    else { img.addEventListener('load', check); img.addEventListener('error', check); }
                });
                if (loaded >= total) resolve();
                setTimeout(resolve, 3000);
            })
        """)

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
            browser = await pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                viewport={"width": breakpoint, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            # Remove navigator.webdriver flag so Shopify doesn't detect automation
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            base_store = f"{parsed.scheme}://{parsed.netloc}"
            domain = parsed.netloc

            # Handle password-protected Shopify stores
            if password:
                try:
                    await page.goto(f"{base_store}/password", wait_until="networkidle", timeout=20000)
                    pwd_input = page.locator("input[type='password']")
                    if await pwd_input.is_visible(timeout=3000):
                        await pwd_input.fill(password)
                        await page.locator("button[type='submit'], input[type='submit']").click()
                        await page.wait_for_load_state("networkidle")
                        await asyncio.sleep(1)
                except Exception:
                    pass

            # Set preview_theme_id cookie for unpublished theme previews
            query_params = parse_qs(parsed.query)
            preview_id = query_params.get("preview_theme_id", [None])[0]
            if preview_id:
                await context.add_cookies([{
                    "name": "preview_theme_id",
                    "value": preview_id,
                    "domain": domain,
                    "path": "/",
                }])

            # Navigate to the target URL
            await page.goto(url, wait_until="networkidle", timeout=15000)

            # Inject cleanup CSS to suppress UI noise
            await page.add_style_tag(content=CLEANUP_CSS)

            # Allow dynamic content to settle with smart wait
            await self._wait_for_page_stable(page)

            # Full-page screenshot
            await page.screenshot(path=output_path, full_page=True)

            await browser.close()

        return output_path
