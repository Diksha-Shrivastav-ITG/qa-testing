"""
Issue Annotator
===============
For each detected issue, finds the element on the live Shopify page using
Playwright, crops the already-captured full-page screenshot to that element,
and draws a thick red border around it.

If the element cannot be located via CSS selectors, a fallback crop of the
top viewport is saved instead — so every issue always gets a screenshot.

Usage:
    paths = await annotate_issues(
        shopify_url   = "https://mystore.myshopify.com/",
        breakpoint    = 1440,
        issues        = [{"element": "H1 heading", ...}, ...],
        full_page_path= "/app/storage/run_1/shopify/home/1440.png",
        output_dir    = "/app/storage/run_1/issues/home/1440",
        password      = None,
    )
    # paths[i] = absolute path to annotated screenshot (never None if full_page_path exists)
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

# ---------------------------------------------------------------------------
# Element name → CSS selector candidates
# Ordered from most-specific to most-generic (first match wins)
# ---------------------------------------------------------------------------

_BASE_MAP: dict[str, list[str]] = {
    # ── Headings ─────────────────────────────────────────────────────────────
    "h1 heading":   ["h1:first-of-type", "h1"],
    "h2 heading":   ["h2:first-of-type", "h2"],
    "h3 heading":   ["h3:first-of-type", "h3"],
    "h4 heading":   ["h4:first-of-type", "h4"],
    "body text":    ["main p:first-of-type", "p:first-of-type", "p"],
    "heading":      ["h1:first-of-type", "h2:first-of-type", "h1", "h2"],
    "subheading":   ["h2:first-of-type", "h3:first-of-type", "h2", "h3"],
    "text":         ["main p:first-of-type", "p:first-of-type", "p"],
    "font":         ["body", "main"],

    # ── Header / Navigation ───────────────────────────────────────────────────
    "header": [
        "header", ".site-header", ".header", "#header",
        "[role='banner']", ".shopify-section-header",
    ],
    "header background": [
        "header", ".site-header", ".header", "#header",
    ],
    "header logo": [
        ".site-header__logo img", ".header__logo img",
        "header .logo img", "header .site-logo img",
        ".header__logo", "header img", ".logo",
    ],
    "logo": [
        ".site-header__logo img", ".header__logo img",
        "header .logo img", "header img", ".logo img", ".logo",
    ],
    "navigation": [
        "header nav", ".site-nav", "nav", ".header__nav",
        ".navigation", ".navbar", "[role='navigation']",
    ],
    "navigation bar": [
        "header nav", ".site-nav", "nav", ".header__nav",
        ".navigation", ".navbar", "[role='navigation']",
    ],
    "navigation links": [
        ".site-nav__item", "header nav a", ".site-nav a",
        "nav a", ".nav__links", ".navigation a",
    ],
    "menu": [
        "header nav", ".site-nav", "nav", ".header__nav",
        ".navigation", ".navbar",
    ],
    "announcement bar": [
        ".announcement-bar", ".announcement", ".promo-bar",
        ".top-bar", "#announcement-bar", ".header-top",
    ],

    # ── Hero / Banner ──────────────────────────────────────────────────────────
    "hero section": [
        ".hero", ".banner", ".hero-section", ".slideshow",
        ".shopify-section:first-of-type", "section:first-of-type",
        ".index-section:first-of-type",
    ],
    "hero banner": [
        ".hero", ".banner", ".hero-section",
        ".shopify-section:first-of-type", "section:first-of-type",
    ],
    "hero image": [
        ".hero img", ".banner img", ".hero__image", ".hero-section img",
        ".slideshow img", ".slideshow__image", "section:first-of-type img",
        ".shopify-section:first-of-type img",
    ],
    "hero": [
        ".hero", ".banner", ".hero-section", ".slideshow",
        ".shopify-section:first-of-type", "section:first-of-type",
    ],
    "banner": [
        ".hero", ".banner", ".hero-section",
        ".shopify-section:first-of-type", "section:first-of-type",
    ],
    "slideshow": [
        ".slideshow", ".hero", ".banner",
        ".shopify-section:first-of-type",
    ],

    # ── Images (generic) ──────────────────────────────────────────────────────
    "image": [
        "main img:first-of-type", ".featured-image", ".product__image",
        ".hero img", "section:first-of-type img", "img",
    ],
    "product image": [
        ".product__image img", ".product-image img", ".product-media img",
        ".product__media img", ".product-single__photo img",
        "figure.product__media img", ".product img",
        "main img:first-of-type", ".featured-image",
    ],
    "product photo": [
        ".product__image img", ".product-media img", ".product__media img",
        ".product-single__photo img", "main img:first-of-type",
    ],
    "featured image": [
        ".featured-image", ".hero img", ".product__image img",
        "main img:first-of-type", "section:first-of-type img",
    ],
    "thumbnail": [
        ".product-thumbnail img", ".thumbnail img",
        ".product__thumbs img", ".product-thumbs img",
    ],
    "background image": [
        ".hero", ".banner", ".section__bg", "section:first-of-type",
    ],

    # ── Icons ─────────────────────────────────────────────────────────────────
    "icon": [
        "svg:first-of-type", ".icon:first-of-type",
        "i.icon:first-of-type", ".icon-wrapper:first-of-type",
        "main svg:first-of-type",
    ],
    "icons": [
        "svg:first-of-type", ".icon:first-of-type",
        ".feature-icon:first-of-type", "main svg:first-of-type",
    ],
    "social icons": [
        ".social-icons", ".social-links", ".footer__social",
        ".social-media-icons",
    ],
    "trust badge": [
        ".trust-badge", ".trust-badges", ".badge",
        ".payment-icons", ".footer__payment",
    ],
    "badge": [
        ".badge", ".trust-badge", ".product-badge",
        ".label", ".tag",
    ],

    # ── Buttons ───────────────────────────────────────────────────────────────
    "primary button": [
        ".btn-primary", ".button--primary", "button.btn-primary",
        ".shopify-payment-button__button", ".btn--primary",
        "a.button:first-of-type", "button.btn:first-of-type",
        "button[type='submit']:first-of-type",
    ],
    "primary button text": [
        ".btn-primary", ".button--primary", ".btn--primary",
        "button[type='submit']:first-of-type",
    ],
    "add to cart button": [
        ".product-form__submit", "button[name='add']",
        ".shopify-payment-button__button", ".add-to-cart",
    ],
    "button": [
        "a.button:first-of-type", "button.btn:first-of-type",
        ".btn:first-of-type", "button:first-of-type",
    ],
    "cta button": [
        "a.button:first-of-type", ".btn-primary",
        ".button--primary", ".hero a.button",
    ],
    "checkout button": [
        ".shopify-payment-button__button", ".cart__checkout-button",
        "button[name='checkout']",
    ],

    # ── Colors / Spacing / Layout ─────────────────────────────────────────────
    "color": ["body", "main"],
    "background color": ["body", "main", ".shopify-section:first-of-type"],
    "spacing": ["main", ".page-width", ".container"],
    "layout": ["main", ".page-width", ".container"],
    "alignment": ["main", ".page-width", "section:first-of-type"],
    "padding": ["main", ".page-width"],
    "margin": ["main", ".page-width"],

    # ── Product / Collection ───────────────────────────────────────────────────
    "product": [
        ".product", ".product-single", ".product__info",
        "main .product",
    ],
    "product title": [
        ".product__title", ".product-single__title",
        "h1.product__title", ".product-title", "main h1",
    ],
    "product price": [
        ".price", ".product__price", ".product-single__price",
        ".price__regular", "span.price",
    ],
    "product description": [
        ".product__description", ".product-single__description",
        ".product-description", "main .rte",
    ],
    "collection": [
        ".collection", ".collection-grid", ".product-grid",
        ".collection-list",
    ],
    "collection grid": [
        ".collection-grid", ".product-grid", ".grid--collection",
    ],

    # ── Forms ─────────────────────────────────────────────────────────────────
    "form": ["form:first-of-type", "main form", ".contact-form"],
    "input": ["input:first-of-type", "input[type='text']:first-of-type"],
    "search": [
        ".search", ".search-form", "input[type='search']",
        ".header__search",
    ],

    # ── Page-level ────────────────────────────────────────────────────────────
    "page container":   [".page-width", ".container", "main", ".main-content"],
    "page background":  ["body", "main"],
    "page":             ["main", ".main-content", ".page-width"],
    "section":          [".shopify-section:first-of-type", "section:first-of-type"],

    # ── Footer ────────────────────────────────────────────────────────────────
    "footer": [
        "footer", ".site-footer", ".footer", "#footer",
        "[role='contentinfo']",
    ],
    "footer background": [
        "footer", ".site-footer", ".footer", "#footer",
    ],
    "footer text": [
        "footer p:first-of-type", ".footer p:first-of-type",
        ".site-footer p:first-of-type", "footer",
    ],
    "footer links": [
        "footer a:first-of-type", ".footer a:first-of-type",
        ".site-footer a",
    ],

    # ── Reviews / Testimonials ─────────────────────────────────────────────────
    "review": [
        ".product-reviews", ".reviews", ".review",
        ".spr-container", "[data-reviews]",
    ],
    "testimonial": [
        ".testimonials", ".testimonial", ".reviews",
        ".customer-reviews",
    ],
    "star rating": [
        ".spr-starrating", ".rating", ".stars",
        ".product-reviews__rating",
    ],

    # ── Missing sections (no single element to highlight) ────────────────────
    "missing sections": [],
    "missing":          [],
}

# Dynamically add section-level selectors for sections 1-10
_SECTION_CANDIDATES = [
    ".shopify-section:nth-of-type({n})",
    "section:nth-of-type({n})",
    "main > section:nth-child({n})",
    "main > div.section:nth-child({n})",
    ".index-section:nth-of-type({n})",
]
for _n in range(1, 11):
    _sec_sels = [s.format(n=_n) for s in _SECTION_CANDIDATES]
    _BASE_MAP[f"section {_n}"]            = _sec_sels
    _BASE_MAP[f"section {_n} background"] = _sec_sels
    _BASE_MAP[f"section {_n} container"]  = _sec_sels
    _BASE_MAP[f"section {_n} headings"]   = _sec_sels
    _BASE_MAP[f"section {_n} images"]     = _sec_sels
    _BASE_MAP[f"section {_n} buttons"]    = _sec_sels
    for _tag in ("h1", "h2", "h3", "h4"):
        _BASE_MAP[f"section {_n} › {_tag} heading"] = [
            f".shopify-section:nth-of-type({_n}) {_tag}",
            f"section:nth-of-type({_n}) {_tag}",
        ]
        _BASE_MAP[f"section {_n} › {_tag.upper()} heading"] = (
            _BASE_MAP[f"section {_n} › {_tag} heading"]
        )
    _BASE_MAP[f"section {_n} › body text"] = [
        f".shopify-section:nth-of-type({_n}) p:first-of-type",
        f"section:nth-of-type({_n}) p:first-of-type",
    ]
    for _j in range(1, 7):
        _BASE_MAP[f"section {_n} › image {_j}"] = [
            f".shopify-section:nth-of-type({_n}) img:nth-of-type({_j})",
            f"section:nth-of-type({_n}) img:nth-of-type({_j})",
        ]
        _BASE_MAP[f"section {_n} › icon {_j}"] = [
            f".shopify-section:nth-of-type({_n}) svg:nth-of-type({_j})",
            f"section:nth-of-type({_n}) svg:nth-of-type({_j})",
        ]


def _resolve_selectors(element_name: str) -> list[str]:
    """Map a human-readable element label to a prioritised list of CSS selectors."""
    key = element_name.lower().strip()

    # 1. Exact match
    if key in _BASE_MAP:
        return _BASE_MAP[key]

    # 2. Strip trailing punctuation / source tags
    stripped = key.rstrip(".")
    if stripped in _BASE_MAP:
        return _BASE_MAP[stripped]

    # 3. Substring match — longest key that is a substring of `key` wins
    best_key = ""
    for map_key in _BASE_MAP:
        if map_key in key and len(map_key) > len(best_key):
            best_key = map_key
    if best_key:
        return _BASE_MAP[best_key]

    # 4. Section number pattern: "Section N › ..."
    import re
    m = re.match(r"section (\d+)", key)
    if m:
        n = int(m.group(1))
        return [s.format(n=n) for s in _SECTION_CANDIDATES]

    return []


# ---------------------------------------------------------------------------
# PIL annotation helpers
# ---------------------------------------------------------------------------


def _crop_and_annotate(
    full_page_path: str,
    bbox: dict,           # {x, y, width, height} in page coordinates (pixels)
    output_path: str,
    padding: int = 80,
    border_width: int = 6,
    border_color: tuple = (220, 38, 38),   # Tailwind red-600
) -> str:
    """Crop the full-page screenshot to the element area and draw a red border."""
    from PIL import Image, ImageDraw

    img = Image.open(full_page_path).convert("RGB")
    iw, ih = img.size

    x  = max(0, int(bbox["x"]))
    y  = max(0, int(bbox["y"]))
    bw = max(1, int(bbox["width"]))
    bh = max(1, int(bbox["height"]))

    # Clamp element bounds to image
    x2 = min(iw, x + bw)
    y2 = min(ih, y + bh)

    # Crop region (element + padding)
    cx1 = max(0, x  - padding)
    cy1 = max(0, y  - padding)
    cx2 = min(iw, x2 + padding)
    cy2 = min(ih, y2 + padding)

    # Ensure a minimum visible crop
    if cx2 - cx1 < 120:
        cx1 = max(0, cx1 - 60)
        cx2 = min(iw, cx2 + 60)
    if cy2 - cy1 < 80:
        cy1 = max(0, cy1 - 40)
        cy2 = min(ih, cy2 + 40)

    cropped = img.crop((cx1, cy1, cx2, cy2))
    draw    = ImageDraw.Draw(cropped, "RGBA")

    # Red border (relative to crop offset)
    rx1 = x  - cx1
    ry1 = y  - cy1
    rx2 = x2 - cx1
    ry2 = y2 - cy1

    # Subtle red fill overlay on the element
    draw.rectangle([rx1, ry1, rx2, ry2], fill=(220, 38, 38, 30))

    # Thick red border — draw multiple times for width
    for offset in range(border_width):
        draw.rectangle(
            [rx1 - offset, ry1 - offset, rx2 + offset, ry2 + offset],
            outline=(*border_color, 255),
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # Save as RGB (drop alpha for storage efficiency)
    cropped.convert("RGB").save(output_path, format="PNG", optimize=True)
    return output_path


def _viewport_crop(
    full_page_path: str,
    output_path: str,
    viewport_height: int = 700,
) -> str:
    """Fallback: save the top <viewport_height> pixels of the full-page screenshot.

    Used when a CSS selector cannot locate the specific element so that the
    issue still gets a screenshot providing page context.  The crop is kept
    short (700px) so the card image doesn't become an enormous full-page dump.
    """
    from PIL import Image, ImageDraw

    img = Image.open(full_page_path).convert("RGB")
    iw, ih = img.size
    crop_h = min(ih, viewport_height)
    cropped = img.crop((0, 0, iw, crop_h))

    # Draw a subtle dashed bottom border so reviewers know the screenshot
    # is a fallback crop, not an element-specific highlight.
    draw = ImageDraw.Draw(cropped)
    dash_len, gap = 12, 6
    y_line = crop_h - 3
    x = 0
    while x < iw:
        draw.line([(x, y_line), (min(x + dash_len, iw), y_line)],
                  fill=(220, 38, 38, 200), width=2)
        x += dash_len + gap

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cropped.save(output_path, format="PNG", optimize=True)
    return output_path


# ---------------------------------------------------------------------------
# Main annotator
# ---------------------------------------------------------------------------


async def annotate_issues(
    shopify_url: str,
    breakpoint: int,
    issues: list[dict],
    full_page_path: str,
    output_dir: str,
    password: str | None = None,
) -> list[Optional[str]]:
    """
    For each issue, find its element on the live Shopify page, crop the
    already-captured full-page screenshot to that element, draw a red border,
    and save the annotated crop.

    When an element cannot be located via CSS selector, a fallback viewport
    crop of the full-page screenshot is saved — so every issue always has a
    screenshot (as long as full_page_path exists).

    Returns a list of absolute file paths (same length as `issues`).
    """
    if not issues or not os.path.exists(full_page_path):
        return [None] * len(issues)

    os.makedirs(output_dir, exist_ok=True)

    # Build per-issue selector lists
    issue_selectors: list[list[str]] = [
        _resolve_selectors(issue.get("element", ""))
        for issue in issues
    ]

    # ── Single Playwright session — navigate once, collect all bounding boxes ──
    bboxes: list[Optional[dict]] = [None] * len(issues)

    # Only open Playwright if at least one issue has candidate selectors
    if any(issue_selectors):
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                ctx = await browser.new_context(
                    viewport={"width": breakpoint, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                )
                await ctx.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )
                page = await ctx.new_page()

                # ── Password unlock if needed ─────────────────────────────────
                if password:
                    try:
                        from urllib.parse import urlparse as _up
                        _parsed = _up(shopify_url)
                        base = f"{_parsed.scheme}://{_parsed.netloc}"
                        await page.goto(f"{base}/password", wait_until="load", timeout=20000)
                        pwd_input = page.locator("input[type='password']")
                        if await pwd_input.is_visible(timeout=2000):
                            await pwd_input.fill(password)
                            await page.locator("button[type='submit'], input[type='submit']").click()
                            await page.wait_for_load_state("domcontentloaded")
                            await asyncio.sleep(1)
                    except Exception:
                        pass

                # ── Navigate ──────────────────────────────────────────────────
                await page.goto(shopify_url, wait_until="load", timeout=60000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass

                # ── Full-page scroll to trigger lazy-loaded elements ──────────
                pg_h = await page.evaluate("document.body.scrollHeight")
                vp_h = await page.evaluate("window.innerHeight")
                step = max(vp_h, 400)
                pos  = 0
                while pos < pg_h:
                    await page.evaluate(f"window.scrollTo(0, {pos})")
                    await asyncio.sleep(0.2)
                    pos += step
                    pg_h = await page.evaluate("document.body.scrollHeight")

                # Return to top so scrollY=0 for coordinate calculations
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(0.4)

                # ── Collect bounding boxes in absolute page coordinates ────────
                # getBoundingClientRect() gives viewport-relative coords.
                # With scrollY=0 (after scroll-to-top), r.top IS the absolute Y.
                _JS = """
                (selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 && r.height === 0) return null;
                    return {
                        x: r.left + window.scrollX,
                        y: r.top  + window.scrollY,
                        width:  r.width,
                        height: r.height
                    };
                }
                """

                for i, selectors in enumerate(issue_selectors):
                    for sel in selectors:
                        if not sel:
                            continue
                        try:
                            bbox = await page.evaluate(_JS, sel)
                            if bbox and bbox["width"] > 0 and bbox["height"] > 0:
                                bboxes[i] = bbox
                                break
                        except Exception:
                            continue

                await browser.close()

        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("issue_annotator Playwright error: %s", exc)

    # ── Annotate or fallback per issue ────────────────────────────────────────
    annotated: list[Optional[str]] = []

    for i, bbox in enumerate(bboxes):
        out = os.path.join(output_dir, f"issue_{i + 1}.png")
        if bbox is not None:
            # Found the element — crop with red border highlight
            try:
                path = _crop_and_annotate(full_page_path, bbox, out)
                annotated.append(path)
            except Exception:
                # Crop failed — fall back to page-top crop
                try:
                    path = _viewport_crop(full_page_path, out)
                    annotated.append(path)
                except Exception:
                    annotated.append(None)
        else:
            # Element not locatable — use top of page as context screenshot
            try:
                path = _viewport_crop(full_page_path, out)
                annotated.append(path)
            except Exception:
                annotated.append(None)

    return annotated
