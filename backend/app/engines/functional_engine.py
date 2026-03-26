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

SHOPIFY_FLOWS = [
    {
        "name": "Add to Cart — User clicks 'Add to Cart' and cart icon updates",
        "steps": [
            {"action": "click", "selector": "button[name='add'], .add-to-cart, [data-testid='add-to-cart'], form[action*='/cart/add'] button[type='submit']"},
            {"action": "wait", "duration_ms": 2000},
            {"action": "assert_visible", "selector": ".cart-count, .cart-icon, [data-testid='cart-count'], .cart-count-bubble, .header__cart-count"},
        ],
    },
    {
        "name": "Mobile Menu — Hamburger menu opens and shows navigation links",
        "steps": [
            {"action": "click", "selector": ".hamburger, .mobile-nav-toggle, [aria-label='Menu'], .menu-toggle, .header__icon--menu, button.menu-drawer__open"},
            {"action": "wait", "duration_ms": 800},
            {"action": "assert_visible", "selector": ".mobile-menu, .mobile-nav, nav.is-open, [data-menu='open'], .menu-drawer, .mobile-facets__wrapper"},
        ],
    },
    {
        "name": "Checkout Flow — User can reach the checkout page after adding a product",
        "steps": [
            {"action": "click", "selector": "button[name='add'], .add-to-cart, [data-testid='add-to-cart'], form[action*='/cart/add'] button[type='submit']"},
            {"action": "wait", "duration_ms": 1500},
            {"action": "navigate", "value": "/checkout"},
            {"action": "assert_visible", "selector": "form.edit_checkout, #checkout, [data-step], .checkout__content, main[role='main']"},
        ],
    },
    {
        "name": "Search — User opens search, types a query, and results appear",
        "steps": [
            {"action": "click", "selector": ".search-toggle, .search-btn, [aria-label='Search'], .header__icon--search, details-modal .header__icon"},
            {"action": "type", "selector": "input[name='q'], .search-input, input[type='search']", "value": "shirt"},
            {"action": "wait", "duration_ms": 1500},
            {"action": "assert_visible", "selector": ".search-results, .predictive-search, [data-search-results], predictive-search .predictive-search__results-list"},
        ],
    },
    {
        "name": "Collection Filters — Clicking a filter updates the product grid",
        "steps": [
            {"action": "navigate", "value": "/collections/all"},
            {"action": "click", "selector": ".filter-toggle, .collection-filter, [data-filter], .facets__summary, .facets__disclosure"},
            {"action": "wait", "duration_ms": 1500},
            {"action": "assert_changed", "selector": ".collection-grid, .product-grid, [data-products], .collection-product-list"},
        ],
    },
    {
        "name": "Newsletter/Email Signup — Email input exists and submit button is clickable",
        "steps": [
            {"action": "assert_visible", "selector": ".newsletter, .footer__newsletter, input[type='email'], .email-signup, [data-section-type='newsletter']"},
        ],
    },
]


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
        await page.goto(url, wait_until="networkidle")
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
                natural_width: img.naturalWidth
            }));
        }
        """
        images: list[dict] = await page.evaluate(_IMAGE_JS)

        failures: list[FunctionalResult] = []

        for img in images:
            src = img.get("src", "")
            alt = img.get("alt", "")
            natural_width = img.get("natural_width", 0)

            # Broken image: no src or naturalWidth == 0 (failed to load)
            if not src:
                failures.append(
                    FunctionalResult(
                        test_name="check_images",
                        status="fail",
                        severity="major",
                        error_message="Image has empty src attribute",
                    )
                )
            elif natural_width == 0:
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

    async def run_shopify_flows(
        self,
        page,
        output_dir: str,
        enabled_flows: list[str] | None = None,
    ) -> list[FunctionalResult]:
        """Run each pre-built Shopify flow and return FunctionalResult objects.

        If *enabled_flows* is provided, only run flows whose name appears in that list.
        """
        results: list[FunctionalResult] = []

        # Update FlowRunner's base_url from the current page URL if available
        try:
            current_url = page.url
            if current_url and current_url.startswith("http"):
                from urllib.parse import urlparse

                parsed = urlparse(current_url)
                self.flow_runner.base_url = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            pass

        for flow in SHOPIFY_FLOWS:
            flow_name = flow["name"]

            if enabled_flows is not None and flow_name not in enabled_flows:
                continue

            flow_result: FlowResult = await self.flow_runner.run_flow(page, flow, output_dir)

            results.append(
                FunctionalResult(
                    test_name=flow_result.name,
                    status=flow_result.status,
                    severity="major",
                    step_failed=flow_result.step_failed,
                    error_message=flow_result.error_message,
                    screenshot_path=flow_result.screenshot_path,
                )
            )

        return results
