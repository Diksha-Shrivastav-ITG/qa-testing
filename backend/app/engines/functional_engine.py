from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import httpx

from app.engines.flow_runner import FlowResult, FlowRunner


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class FunctionalResult:
    test_name: str
    status: str  # "pass" or "fail"
    severity: str = "major"
    step_failed: Optional[int] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Pre-built Shopify flows
# ---------------------------------------------------------------------------

# JavaScript that discovers what's actually on the page and tests it
_SMART_FUNCTIONAL_JS = """
() => {
    const results = [];

    // Helper: check if element exists and is visible
    function isVisible(el) {
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 &&
               style.display !== 'none' && style.visibility !== 'hidden' &&
               style.opacity !== '0';
    }

    // 1. CHECK: Page has a <title> tag
    const title = document.title || '';
    results.push({
        name: 'Page has a title tag',
        status: title.length > 0 ? 'pass' : 'fail',
        error: title.length > 0 ? null : 'Page <title> is empty or missing',
        severity: 'major'
    });

    // 2. CHECK: Page has exactly one <h1>
    const h1s = document.querySelectorAll('h1');
    results.push({
        name: 'Page has exactly one H1 heading',
        status: h1s.length === 1 ? 'pass' : 'fail',
        error: h1s.length === 0 ? 'No H1 heading found on the page' :
               h1s.length > 1 ? `Found ${h1s.length} H1 headings — should be exactly 1 for SEO` : null,
        severity: h1s.length === 0 ? 'major' : 'minor'
    });

    // 3. CHECK: All images have alt text
    const imgs = Array.from(document.querySelectorAll('img'));
    const missingAlt = imgs.filter(img => !img.alt && isVisible(img));
    results.push({
        name: 'All visible images have alt text',
        status: missingAlt.length === 0 ? 'pass' : 'fail',
        error: missingAlt.length > 0 ? `${missingAlt.length} visible image(s) missing alt text` : null,
        severity: 'minor'
    });

    // 4. CHECK: No broken images (only flag images where complete=true to avoid
    //    false positives from images that are still loading)
    const brokenImgs = imgs.filter(img => img.src && img.complete && img.naturalWidth === 0 && isVisible(img));
    results.push({
        name: 'No broken images on the page',
        status: brokenImgs.length === 0 ? 'pass' : 'fail',
        error: brokenImgs.length > 0 ? `${brokenImgs.length} image(s) failed to load` : null,
        severity: 'major'
    });

    // 5. CHECK: Navigation exists
    const nav = document.querySelector('nav, header nav, [role="navigation"]');
    results.push({
        name: 'Navigation menu exists',
        status: nav && isVisible(nav) ? 'pass' : 'fail',
        error: !nav ? 'No <nav> element found' : !isVisible(nav) ? 'Navigation exists but is not visible' : null,
        severity: 'major'
    });

    // 6. CHECK: Navigation has links
    if (nav) {
        const navLinks = nav.querySelectorAll('a[href]');
        results.push({
            name: 'Navigation contains links',
            status: navLinks.length >= 2 ? 'pass' : 'fail',
            error: navLinks.length < 2 ? `Navigation only has ${navLinks.length} link(s) — expected at least 2` : null,
            severity: 'major'
        });
    }

    // 7. CHECK: No console errors in the page (check for error elements)
    const errorBanners = document.querySelectorAll('[class*="error"], [class*="Error"], .shopify-challenge__container');
    const realErrors = Array.from(errorBanners).filter(el => isVisible(el) && el.textContent.length > 5);
    results.push({
        name: 'No visible error messages on page',
        status: realErrors.length === 0 ? 'pass' : 'fail',
        error: realErrors.length > 0 ? `Found ${realErrors.length} visible error element(s) on the page` : null,
        severity: 'critical'
    });

    // 8. CHECK: Footer exists
    const footer = document.querySelector('footer, [role="contentinfo"]');
    results.push({
        name: 'Footer section exists',
        status: footer ? 'pass' : 'fail',
        error: footer ? null : 'No <footer> element found',
        severity: 'minor'
    });

    // 9. CHECK: No horizontal overflow
    const hasHScroll = document.documentElement.scrollWidth > document.documentElement.clientWidth + 5;
    results.push({
        name: 'No horizontal scroll / overflow',
        status: !hasHScroll ? 'pass' : 'fail',
        error: hasHScroll ? `Page has horizontal overflow (${document.documentElement.scrollWidth}px > ${document.documentElement.clientWidth}px)` : null,
        severity: 'major'
    });

    // 10. CHECK: Links with href="#" or empty href
    const badLinks = Array.from(document.querySelectorAll('a')).filter(a => {
        const href = (a.getAttribute('href') || '').trim();
        return isVisible(a) && (!href || href === '#' || href === 'javascript:void(0)');
    });
    results.push({
        name: 'No links with empty or placeholder href',
        status: badLinks.length === 0 ? 'pass' : 'fail',
        error: badLinks.length > 0 ? `${badLinks.length} link(s) have empty or "#" href` : null,
        severity: 'minor'
    });

    // 11. CHECK: Buttons have accessible names
    const buttons = Array.from(document.querySelectorAll('button'));
    const unlabeled = buttons.filter(btn => {
        if (!isVisible(btn)) return false;
        const text = (btn.textContent || '').trim();
        const aria = btn.getAttribute('aria-label') || '';
        const title = btn.getAttribute('title') || '';
        return !text && !aria && !title;
    });
    results.push({
        name: 'All buttons have accessible names',
        status: unlabeled.length === 0 ? 'pass' : 'fail',
        error: unlabeled.length > 0 ? `${unlabeled.length} button(s) have no text, aria-label, or title` : null,
        severity: 'minor'
    });

    // 12. CHECK: Add to Cart form exists (if on product page)
    const isProduct = window.location.pathname.includes('/products/');
    if (isProduct) {
        const cartForm = document.querySelector('form[action*="/cart/add"]');
        results.push({
            name: 'Product page has Add to Cart form',
            status: cartForm ? 'pass' : 'fail',
            error: cartForm ? null : 'No form with action="/cart/add" found on this product page',
            severity: 'critical'
        });
    }

    // 13. CHECK: Meta viewport tag exists
    const viewport = document.querySelector('meta[name="viewport"]');
    results.push({
        name: 'Meta viewport tag exists (mobile-friendly)',
        status: viewport ? 'pass' : 'fail',
        error: viewport ? null : 'Missing <meta name="viewport"> — page may not be mobile-friendly',
        severity: 'major'
    });

    return results;
}
"""


# ---------------------------------------------------------------------------
# FunctionalEngine
# ---------------------------------------------------------------------------


class FunctionalEngine:
    """Runs surface-level functional tests (link/image checks) and Shopify UI flows."""

    def __init__(self, storage_path: str) -> None:
        self.storage_path = storage_path
        self.flow_runner = FlowRunner()

    # ------------------------------------------------------------------
    # Playwright helper
    # ------------------------------------------------------------------

    async def _create_page(self, url: str, viewport_width: int = 1440):
        """Launch Playwright, navigate to *url*, and return the page object."""
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": viewport_width, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        return page

    # ------------------------------------------------------------------
    # Surface tests
    # ------------------------------------------------------------------

    async def check_links(self, page) -> list[FunctionalResult]:
        """Fetch all href links via JS and HEAD-request each one.

        Returns a list of FunctionalResult for any link returning HTTP 400+.
        """
        _LINK_JS = """
        () => {
            return Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(href => href.startsWith('http'));
        }
        """
        links: list[str] = await page.evaluate(_LINK_JS)

        failures: list[FunctionalResult] = []

        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            for url in links:
                try:
                    resp = await client.head(url)
                    if resp.status_code >= 400:
                        failures.append(
                            FunctionalResult(
                                test_name="check_links",
                                status="fail",
                                severity="minor",
                                error_message=f"HTTP {resp.status_code} for {url}",
                            )
                        )
                except Exception as exc:
                    failures.append(
                        FunctionalResult(
                            test_name="check_links",
                            status="fail",
                            severity="minor",
                            error_message=f"Request failed for {url}: {exc}",
                        )
                    )

        return failures

    async def check_images(self, page) -> list[FunctionalResult]:
        """Check all <img> elements for broken sources and missing alt text.

        Returns a list of FunctionalResult for broken or inaccessible images.
        """
        _IMAGE_JS = """
        () => {
            return Array.from(document.querySelectorAll('img')).map(img => ({
                src: img.src || '',
                alt: img.alt || '',
                natural_width: img.naturalWidth,
                complete: img.complete
            }));
        }
        """
        images: list[dict] = await page.evaluate(_IMAGE_JS)

        failures: list[FunctionalResult] = []

        for img in images:
            src = img.get("src", "")
            alt = img.get("alt", "")
            natural_width = img.get("natural_width", 0)
            complete = img.get("complete", True)

            # Broken image: no src or naturalWidth == 0 after the browser has
            # finished loading it (complete=true). Skipping incomplete images
            # avoids false positives when the page is still loading resources.
            if not src:
                failures.append(
                    FunctionalResult(
                        test_name="check_images",
                        status="fail",
                        severity="major",
                        error_message="Image has empty src attribute",
                    )
                )
            elif complete and natural_width == 0:
                failures.append(
                    FunctionalResult(
                        test_name="check_images",
                        status="fail",
                        severity="major",
                        error_message=f"Image failed to load: {src}",
                    )
                )

            # Missing alt text (accessibility issue)
            if src and not alt:
                failures.append(
                    FunctionalResult(
                        test_name="check_images",
                        status="fail",
                        severity="minor",
                        error_message=f"Image missing alt text: {src}",
                    )
                )

        return failures

    async def run_surface_tests(self, page, output_dir: str) -> list[FunctionalResult]:
        """Run link and image surface checks and return all failures."""
        link_failures = await self.check_links(page)
        image_failures = await self.check_images(page)
        return link_failures + image_failures

    # ------------------------------------------------------------------
    # Shopify flow tests
    # ------------------------------------------------------------------

    async def run_smart_tests(
        self,
        page,
        output_dir: str,
    ) -> list[FunctionalResult]:
        """Run smart functional tests that discover elements on the page.

        No hardcoded selectors — tests check what actually exists.
        """
        results: list[FunctionalResult] = []

        try:
            raw_results = await page.evaluate(_SMART_FUNCTIONAL_JS)
        except Exception as exc:
            return [FunctionalResult(
                test_name="Smart functional tests",
                status="fail",
                severity="major",
                error_message=f"Could not run tests: {exc}",
            )]

        for item in raw_results:
            results.append(FunctionalResult(
                test_name=item.get("name", "Unknown test"),
                status=item.get("status", "fail"),
                severity=item.get("severity", "minor"),
                error_message=item.get("error"),
            ))

        return results

    # Keep backward compatibility
    async def run_shopify_flows(
        self,
        page,
        output_dir: str,
        enabled_flows: list[str] | None = None,
    ) -> list[FunctionalResult]:
        """Run smart tests instead of hardcoded flows."""
        return await self.run_smart_tests(page, output_dir)
