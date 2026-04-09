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
        name: 'Page Title Tag',
        status: title.length > 0 ? 'pass' : 'fail',
        error: title.length > 0
            ? 'PASSED — Title tag found: "' + title + '" (' + title.length + ' chars)'
            : 'FAILED — Page <title> is empty or missing. Every page must have a descriptive title for SEO and browser tab display.',
        severity: 'major'
    });

    // 2. CHECK: Page has exactly one <h1>
    const h1s = document.querySelectorAll('h1');
    let h1Detail = '';
    if (h1s.length === 1) {
        h1Detail = 'PASSED — Single H1 found: "' + h1s[0].textContent.trim().substring(0, 100) + '"';
    } else if (h1s.length === 0) {
        h1Detail = 'FAILED — No H1 heading found on the page. Each page should have exactly one H1 for proper heading structure and SEO.';
    } else {
        const h1Texts = Array.from(h1s).map(function(h, i) { return '  H1 #' + (i + 1) + ': "' + h.textContent.trim().substring(0, 80) + '"'; });
        h1Detail = 'FAILED — Found ' + h1s.length + ' H1 headings (should be exactly 1 per page):\\n' + h1Texts.join('\\n');
    }
    results.push({
        name: 'Single H1 Heading',
        status: h1s.length === 1 ? 'pass' : 'fail',
        error: h1Detail,
        severity: h1s.length === 0 ? 'major' : 'minor'
    });

    // 3. CHECK: All images have alt text
    const imgs = Array.from(document.querySelectorAll('img'));
    const missingAlt = imgs.filter(img => !img.alt && isVisible(img));
    let imgAltDetail = '';
    if (missingAlt.length === 0) {
        imgAltDetail = 'PASSED — All ' + imgs.length + ' images on the page have alt text attributes for accessibility.';
    } else {
        const missingSrcs = missingAlt.slice(0, 10).map(function(img, i) {
            const src = img.src || img.getAttribute('data-src') || '(no src)';
            const shortSrc = src.length > 80 ? '...' + src.slice(-60) : src;
            return '  ' + (i + 1) + '. ' + shortSrc;
        });
        imgAltDetail = 'FAILED — ' + missingAlt.length + ' of ' + imgs.length + ' visible images are missing alt text:\\n' + missingSrcs.join('\\n');
        if (missingAlt.length > 10) imgAltDetail += '\\n  ... and ' + (missingAlt.length - 10) + ' more';
    }
    results.push({
        name: 'Image Alt Text',
        status: missingAlt.length === 0 ? 'pass' : 'fail',
        error: imgAltDetail,
        severity: 'minor'
    });

    // 4. CHECK: No broken images
    const brokenImgs = imgs.filter(img => img.src && img.complete && img.naturalWidth === 0 && isVisible(img));
    let brokenDetail = '';
    if (brokenImgs.length === 0) {
        brokenDetail = 'PASSED — All ' + imgs.length + ' images loaded successfully. No broken images detected.';
    } else {
        const brokenSrcs = brokenImgs.slice(0, 10).map(function(img, i) {
            const src = img.src || '(unknown)';
            const shortSrc = src.length > 80 ? '...' + src.slice(-60) : src;
            return '  ' + (i + 1) + '. ' + shortSrc;
        });
        brokenDetail = 'FAILED — ' + brokenImgs.length + ' image(s) failed to load (broken or inaccessible):\\n' + brokenSrcs.join('\\n');
    }
    results.push({
        name: 'No Broken Images',
        status: brokenImgs.length === 0 ? 'pass' : 'fail',
        error: brokenDetail,
        severity: 'major'
    });

    // 5. CHECK: Navigation exists
    const nav = document.querySelector('nav, header nav, [role="navigation"]');
    let navDetail = '';
    if (nav && isVisible(nav)) {
        const navTag = nav.tagName.toLowerCase();
        const navRole = nav.getAttribute('role') || '';
        navDetail = 'PASSED — Navigation element found (<' + navTag + (navRole ? ' role="' + navRole + '"' : '') + '>). Navigation is visible and accessible.';
    } else if (nav) {
        navDetail = 'FAILED — A <nav> element exists in the DOM but is not visible (display:none, zero dimensions, or hidden). Users cannot see or interact with the navigation.';
    } else {
        navDetail = 'FAILED — No <nav>, <header nav>, or [role="navigation"] element found on the page. A visible navigation menu is essential for site usability.';
    }
    results.push({
        name: 'Navigation Menu Exists',
        status: nav && isVisible(nav) ? 'pass' : 'fail',
        error: navDetail,
        severity: 'major'
    });

    // 6. CHECK: Navigation has links
    if (nav) {
        const navLinks = nav.querySelectorAll('a[href]');
        let navLinksDetail = '';
        if (navLinks.length >= 2) {
            const linkTexts = Array.from(navLinks).slice(0, 15).map(function(a) {
                const text = a.textContent.trim().substring(0, 50) || '(no text)';
                const href = a.getAttribute('href') || '';
                return '  • ' + text + ' → ' + href;
            });
            navLinksDetail = 'PASSED — Navigation contains ' + navLinks.length + ' links:\\n' + linkTexts.join('\\n');
            if (navLinks.length > 15) navLinksDetail += '\\n  ... and ' + (navLinks.length - 15) + ' more links';
        } else {
            navLinksDetail = 'FAILED — Navigation only has ' + navLinks.length + ' link(s). Expected at least 2 navigation links for proper site navigation.';
        }
        results.push({
            name: 'Navigation Contains Links',
            status: navLinks.length >= 2 ? 'pass' : 'fail',
            error: navLinksDetail,
            severity: 'major'
        });
    }

    // 7. CHECK: No visible error messages
    const errorBanners = document.querySelectorAll('[class*="error"], [class*="Error"], .shopify-challenge__container');
    const realErrors = Array.from(errorBanners).filter(el => isVisible(el) && el.textContent.length > 5);
    let errorDetail = '';
    if (realErrors.length === 0) {
        errorDetail = 'PASSED — No visible error messages, error banners, or Shopify challenge screens detected on the page.';
    } else {
        const errorTexts = realErrors.slice(0, 5).map(function(el, i) {
            const text = el.textContent.trim().substring(0, 120);
            const cls = el.className || '(no class)';
            return '  ' + (i + 1) + '. [.' + cls.split(' ')[0] + '] "' + text + '"';
        });
        errorDetail = 'FAILED — Found ' + realErrors.length + ' visible error element(s) on the page:\\n' + errorTexts.join('\\n');
    }
    results.push({
        name: 'No Visible Error Messages',
        status: realErrors.length === 0 ? 'pass' : 'fail',
        error: errorDetail,
        severity: 'critical'
    });

    // 8. CHECK: Footer exists
    const footer = document.querySelector('footer, [role="contentinfo"]');
    let footerDetail = '';
    if (footer) {
        const footerLinks = footer.querySelectorAll('a[href]');
        footerDetail = 'PASSED — Footer section found (<' + footer.tagName.toLowerCase() + '>). Contains ' + footerLinks.length + ' links.';
    } else {
        footerDetail = 'FAILED — No <footer> or [role="contentinfo"] element found. A footer section is expected for contact info, legal links, and site navigation.';
    }
    results.push({
        name: 'Footer Section Exists',
        status: footer ? 'pass' : 'fail',
        error: footerDetail,
        severity: 'minor'
    });

    // 9. CHECK: No horizontal overflow
    const scrollW = document.documentElement.scrollWidth;
    const clientW = document.documentElement.clientWidth;
    const hasHScroll = scrollW > clientW + 5;
    let hScrollDetail = '';
    if (!hasHScroll) {
        hScrollDetail = 'PASSED — No horizontal overflow detected. Page width (' + scrollW + 'px) fits within viewport (' + clientW + 'px).';
    } else {
        hScrollDetail = 'FAILED — Page has horizontal overflow. Content width is ' + scrollW + 'px but viewport is only ' + clientW + 'px (' + (scrollW - clientW) + 'px overflow). This causes an unwanted horizontal scrollbar.';
    }
    results.push({
        name: 'No Horizontal Scroll / Overflow',
        status: !hasHScroll ? 'pass' : 'fail',
        error: hScrollDetail,
        severity: 'major'
    });

    // 10. CHECK: Links with href="#" or empty href
    const allLinks = Array.from(document.querySelectorAll('a'));
    const badLinks = allLinks.filter(a => {
        const href = (a.getAttribute('href') || '').trim();
        return isVisible(a) && (!href || href === '#' || href === 'javascript:void(0)');
    });
    let badLinksDetail = '';
    if (badLinks.length === 0) {
        badLinksDetail = 'PASSED — All ' + allLinks.length + ' links on the page have valid href attributes. No empty or placeholder links found.';
    } else {
        const badLinkTexts = badLinks.slice(0, 10).map(function(a, i) {
            const text = a.textContent.trim().substring(0, 50) || '(no text)';
            const href = a.getAttribute('href') || '(empty)';
            return '  ' + (i + 1) + '. "' + text + '" → href="' + href + '"';
        });
        badLinksDetail = 'FAILED — ' + badLinks.length + ' link(s) have empty or placeholder href values:\\n' + badLinkTexts.join('\\n');
        if (badLinks.length > 10) badLinksDetail += '\\n  ... and ' + (badLinks.length - 10) + ' more';
    }
    results.push({
        name: 'No Empty/Placeholder Links',
        status: badLinks.length === 0 ? 'pass' : 'fail',
        error: badLinksDetail,
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
    let btnDetail = '';
    if (unlabeled.length === 0) {
        btnDetail = 'PASSED — All ' + buttons.length + ' buttons on the page have accessible names (text, aria-label, or title attribute).';
    } else {
        const btnInfos = unlabeled.slice(0, 10).map(function(btn, i) {
            const cls = btn.className ? '.' + btn.className.split(' ')[0] : '';
            const tag = '<button' + cls + '>';
            return '  ' + (i + 1) + '. ' + tag + ' — no text, aria-label, or title';
        });
        btnDetail = 'FAILED — ' + unlabeled.length + ' of ' + buttons.length + ' button(s) have no accessible name:\\n' + btnInfos.join('\\n');
    }
    results.push({
        name: 'Buttons Have Accessible Names',
        status: unlabeled.length === 0 ? 'pass' : 'fail',
        error: btnDetail,
        severity: 'minor'
    });

    // 12. CHECK: Add to Cart form exists (if on product page)
    const isProduct = window.location.pathname.includes('/products/');
    if (isProduct) {
        const cartForm = document.querySelector('form[action*="/cart/add"]');
        let cartDetail = '';
        if (cartForm) {
            const submitBtn = cartForm.querySelector('button[type="submit"], input[type="submit"], button[name="add"]');
            const btnText = submitBtn ? (submitBtn.textContent || submitBtn.value || '').trim() : '(no submit button found)';
            cartDetail = 'PASSED — Add to Cart form found with action="/cart/add". Submit button: "' + btnText + '"';
        } else {
            cartDetail = 'FAILED — No form with action="/cart/add" found on this product page. Customers cannot add this product to their cart. This is a critical e-commerce issue.';
        }
        results.push({
            name: 'Product Add to Cart Form',
            status: cartForm ? 'pass' : 'fail',
            error: cartDetail,
            severity: 'critical'
        });
    }

    // 13. CHECK: Meta viewport tag exists
    const viewport = document.querySelector('meta[name="viewport"]');
    let vpDetail = '';
    if (viewport) {
        vpDetail = 'PASSED — Meta viewport tag found: <meta name="viewport" content="' + (viewport.getAttribute('content') || '') + '">. Page is configured for mobile devices.';
    } else {
        vpDetail = 'FAILED — Missing <meta name="viewport"> tag. Without this, the page will not scale properly on mobile devices, causing poor mobile experience.';
    }
    results.push({
        name: 'Meta Viewport Tag (Mobile-Friendly)',
        status: viewport ? 'pass' : 'fail',
        error: vpDetail,
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
                                test_name="Broken Link Detected",
                                status="fail",
                                severity="minor",
                                error_message=f"FAILED — HTTP {resp.status_code} for {url}",
                            )
                        )
                except Exception as exc:
                    failures.append(
                        FunctionalResult(
                            test_name="Broken Link Detected",
                            status="fail",
                            severity="minor",
                            error_message=f"FAILED — Request failed for {url}: {exc}",
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
                        test_name="Broken Image",
                        status="fail",
                        severity="major",
                        error_message="FAILED — Image has empty src attribute. The <img> tag has no source URL.",
                    )
                )
            elif complete and natural_width == 0:
                short_src = src if len(src) <= 100 else "..." + src[-80:]
                failures.append(
                    FunctionalResult(
                        test_name="Broken Image",
                        status="fail",
                        severity="major",
                        error_message=f"FAILED — Image failed to load: {short_src}",
                    )
                )

            # Missing alt text (accessibility issue)
            if src and not alt:
                short_src = src if len(src) <= 100 else "..." + src[-80:]
                failures.append(
                    FunctionalResult(
                        test_name="Image Missing Alt Text",
                        status="fail",
                        severity="minor",
                        error_message=f"FAILED — Image missing alt text: {short_src}",
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
