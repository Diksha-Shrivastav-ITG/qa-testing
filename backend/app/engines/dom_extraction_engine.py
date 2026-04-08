"""Deep DOM style extraction from any webpage using Playwright.

Captures every meaningful element on the page with its full computed CSS:
  - Global: body typography, background, container dimensions
  - Header / Navigation: height, background, font, logo size, item count
  - Footer: height, background, text color, font size
  - Per-section (up to 10):
      headings (h1-h4):   font-family, font-size, font-weight, line-height,
                          letter-spacing, color, text-transform, text-align, dimensions
      paragraphs/text:    same typography stack + dimensions
      images/media:       rendered width, height, object-fit, object-position
      buttons/CTAs:       background, color, border, border-radius, padding,
                          font-family, font-size, font-weight, min-width, dimensions
      icons (SVG/img):    rendered width, height
  - Section container:   padding (all 4), margin (all 4), background,
                          width, height, max-width

This profile feeds DomComparisonEngine which reports every property that
differs between the reference URL and the Shopify implementation.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deep extraction JavaScript
# ---------------------------------------------------------------------------

_EXTRACT_SCRIPT = r"""
(function () {
  /* ── helpers ──────────────────────────────────────────────────── */
  function css(el, prop) {
    try { return window.getComputedStyle(el).getPropertyValue(prop) || ""; }
    catch { return ""; }
  }
  function px(el, prop) {
    const v = css(el, prop);
    const m = v && v.match(/^([\d.]+)px/);
    return m ? parseFloat(m[1]) : null;
  }
  function rect(el) {
    try {
      const r = el.getBoundingClientRect();
      return { width: Math.round(r.width), height: Math.round(r.height) };
    } catch { return { width: null, height: null }; }
  }
  function firstOf(selectors) {
    for (const s of selectors) {
      try {
        const el = document.querySelector(s);
        if (el) return el;
      } catch {}
    }
    return null;
  }

  /* ── full typography for any element ──────────────────────────── */
  function typo(el) {
    if (!el) return null;
    return {
      fontFamily:    css(el, "font-family").split(",")[0].trim().replace(/['"]/g, ""),
      fontSize:      css(el, "font-size"),
      fontWeight:    css(el, "font-weight"),
      lineHeight:    css(el, "line-height"),
      letterSpacing: css(el, "letter-spacing"),
      color:         css(el, "color"),
      textTransform: css(el, "text-transform"),
      textAlign:     css(el, "text-align"),
    };
  }

  /* ── full spacing (padding + margin) for any element ──────────── */
  function spacing(el) {
    if (!el) return null;
    return {
      paddingTop:    css(el, "padding-top"),
      paddingRight:  css(el, "padding-right"),
      paddingBottom: css(el, "padding-bottom"),
      paddingLeft:   css(el, "padding-left"),
      marginTop:     css(el, "margin-top"),
      marginRight:   css(el, "margin-right"),
      marginBottom:  css(el, "margin-bottom"),
      marginLeft:    css(el, "margin-left"),
    };
  }

  /* ── background ────────────────────────────────────────────────── */
  function bg(el) {
    if (!el) return null;
    return {
      backgroundColor: css(el, "background-color"),
      backgroundSize:  css(el, "background-size"),
    };
  }

  /* ── section detection — finds visible content blocks ────────── */
  function findSections() {
    // Broad set of selectors that covers Shopify sections, Framer blocks,
    // Webflow sections, and generic landing pages.
    const candidates = Array.from(document.querySelectorAll(
      "section," +
      "[class*='section']," +
      "[class*='block']," +
      "[class*='row']," +
      "[class*='panel']," +
      "[class*='stripe']," +
      "[data-section-type]," +
      "main > div," +
      "main > article," +
      "#main > div," +
      ".main-content > div"
    ));

    // Filter: must be at least 80px tall, 200px wide, and not nested inside
    // another candidate (to avoid double-counting).
    const seen = new Set();
    return candidates.filter(el => {
      const r = el.getBoundingClientRect();
      if (r.height < 80 || r.width < 200) return false;
      // skip if an ancestor is already in the list
      let parent = el.parentElement;
      while (parent) {
        if (seen.has(parent)) return false;
        parent = parent.parentElement;
      }
      seen.add(el);
      return true;
    });
  }

  /* ── extract one section ──────────────────────────────────────── */
  function extractSection(sec, idx) {
    const r = rect(sec);

    /* headings — direct children first, then any descendant */
    const headings = Array.from(sec.querySelectorAll("h1,h2,h3,h4")).slice(0, 5).map(h => ({
      tag:  h.tagName.toLowerCase(),
      text: h.textContent.trim().slice(0, 100),
      ...typo(h),
      ...rect(h),
    }));

    /* body text / paragraphs — exclude headings, navs, buttons */
    const paragraphs = Array.from(sec.querySelectorAll(
      "p, [class*='body-text'], [class*='bodyText'], [class*='description'], [class*='subtitle']"
    ))
      .filter(el =>
        el.textContent.trim().length > 10 &&
        !el.closest("h1,h2,h3,h4,nav,button,a")
      )
      .slice(0, 4)
      .map(p => ({ ...typo(p), ...rect(p) }));

    /* images — rendered src images only (exclude icons < 32px) */
    const images = Array.from(sec.querySelectorAll(
      "img, picture > img, [class*='image'] > img, [class*='img'] img"
    ))
      .filter(img => {
        const ir = img.getBoundingClientRect();
        return ir.width > 32 && ir.height > 32;
      })
      .slice(0, 6)
      .map(img => ({
        ...rect(img),
        naturalWidth:   img.naturalWidth  || null,
        naturalHeight:  img.naturalHeight || null,
        objectFit:      css(img, "object-fit"),
        objectPosition: css(img, "object-position"),
      }));

    /* buttons / CTAs */
    const buttons = Array.from(sec.querySelectorAll(
      "a[class*='btn'], a[class*='button'], button, " +
      ".btn, .button, [class*='cta'], [class*='call-to-action']," +
      "[role='button']"
    ))
      .filter(el => el.textContent.trim().length > 0)
      .slice(0, 4)
      .map(btn => ({
        text:            btn.textContent.trim().slice(0, 60),
        ...typo(btn),
        ...rect(btn),
        backgroundColor: css(btn, "background-color"),
        borderRadius:    css(btn, "border-radius"),
        border:          css(btn, "border"),
        paddingTop:      css(btn, "padding-top"),
        paddingRight:    css(btn, "padding-right"),
        paddingBottom:   css(btn, "padding-bottom"),
        paddingLeft:     css(btn, "padding-left"),
        minWidth:        css(btn, "min-width"),
      }));

    /* icons (SVG only, between 12px and 96px) */
    const icons = Array.from(sec.querySelectorAll("svg"))
      .filter(s => {
        const ir = s.getBoundingClientRect();
        return ir.width >= 12 && ir.width <= 96;
      })
      .slice(0, 12)
      .map(icon => ({ tag: "svg", ...rect(icon) }));

    /* inner wrapper max-width */
    const inner = sec.querySelector(
      ".container, .wrapper, .page-width, [class*='container'], [class*='wrapper'], div"
    );
    const container = inner ? {
      maxWidth: css(inner, "max-width"),
      width:    Math.round(inner.getBoundingClientRect().width),
    } : null;

    return {
      index: idx,
      ...r,
      ...spacing(sec),
      ...bg(sec),
      container,
      headings,
      paragraphs,
      images,
      buttons,
      icons,
    };
  }

  /* ── top-level elements ───────────────────────────────────────── */
  const headerEl  = firstOf(["header", ".header", "#header", "[role='banner']", ".site-header"]);
  const navEl     = firstOf(["nav", "header nav", ".nav", "#nav", "[role='navigation']", ".navigation"]);
  const footerEl  = firstOf(["footer", ".footer", "#footer", "[role='contentinfo']", ".site-footer"]);
  const logoEl    = headerEl && firstOf(
    [".logo img", ".logo svg", "header img", "header svg", "[class*='logo']", ".brand img"]
  );
  const containerEl = firstOf([
    ".container", ".page-width", ".wrapper", ".site-content",
    "main", "[class*='container']",
  ]);

  const header = headerEl ? {
    ...rect(headerEl),
    ...spacing(headerEl),
    backgroundColor: css(headerEl, "background-color"),
    nav: navEl ? {
      ...rect(navEl),
      backgroundColor: css(navEl, "background-color"),
      fontSize:        css(navEl, "font-size"),
      fontFamily:      css(navEl, "font-family").split(",")[0].trim().replace(/['"]/g, ""),
      fontWeight:      css(navEl, "font-weight"),
      color:           css(navEl, "color"),
      itemCount:       navEl.querySelectorAll("a").length,
    } : null,
    logo: logoEl ? { ...rect(logoEl) } : null,
  } : null;

  const footer = footerEl ? {
    ...rect(footerEl),
    ...spacing(footerEl),
    backgroundColor: css(footerEl, "background-color"),
    color:           css(footerEl, "color"),
    fontSize:        css(footerEl, "font-size"),
    fontFamily:      css(footerEl, "font-family").split(",")[0].trim().replace(/['"]/g, ""),
  } : null;

  /* ── sections ─────────────────────────────────────────────────── */
  const sections = findSections().slice(0, 10).map((el, i) => extractSection(el, i));

  /* ── global ───────────────────────────────────────────────────── */
  const globalH1  = document.querySelector("h1");
  const globalH2  = document.querySelector("h2");
  const globalBtn = firstOf([
    ".btn-primary", ".button--primary", "button[type='submit']",
    "a.button", ".cta-button", "button.btn", "a[class*='btn']",
  ]);

  return {
    viewport: {
      width:          window.innerWidth,
      height:         window.innerHeight,
      documentHeight: document.documentElement.scrollHeight,
    },
    global: {
      body: {
        ...typo(document.body),
        backgroundColor: css(document.body, "background-color"),
      },
      h1: globalH1 ? { ...typo(globalH1), ...rect(globalH1) } : null,
      h2: globalH2 ? { ...typo(globalH2), ...rect(globalH2) } : null,
      container: containerEl ? {
        maxWidth: css(containerEl, "max-width"),
        width:    Math.round(containerEl.getBoundingClientRect().width),
      } : null,
      primaryButton: globalBtn ? {
        ...typo(globalBtn),
        ...rect(globalBtn),
        backgroundColor: css(globalBtn, "background-color"),
        borderRadius:    css(globalBtn, "border-radius"),
        border:          css(globalBtn, "border"),
        paddingTop:      css(globalBtn, "padding-top"),
        paddingRight:    css(globalBtn, "padding-right"),
        paddingBottom:   css(globalBtn, "padding-bottom"),
        paddingLeft:     css(globalBtn, "padding-left"),
        minWidth:        css(globalBtn, "min-width"),
      } : null,
    },
    header,
    footer,
    sections,
  };
})()
"""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class DomProfile:
    """Deep style + structure profile of a single web page."""

    url: str
    viewport: dict = field(default_factory=dict)       # { width, height, documentHeight }
    global_styles: dict = field(default_factory=dict)  # body, h1, h2, container, primaryButton
    header: dict | None = None                         # nav, logo, height, bg
    footer: dict | None = None                         # height, bg, text
    sections: list = field(default_factory=list)       # per-section deep data
    viewport_width: int = 1440


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class DomExtractionEngine:
    """Extract a deep DomProfile from any publicly accessible URL via Playwright."""

    async def extract(
        self,
        url: str,
        password: str | None = None,
        timeout: int = 35_000,
        viewport_width: int = 1440,
    ) -> DomProfile:
        """Navigate to *url* at *viewport_width*, stabilise the page, return DomProfile."""
        vp_height = 812 if viewport_width <= 375 else (1024 if viewport_width <= 768 else 900)

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                ctx = await browser.new_context(
                    viewport={"width": viewport_width, "height": vp_height},
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

                # Handle password-protected stores
                if password:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        base = f"{parsed.scheme}://{parsed.netloc}"
                        await page.goto(f"{base}/password", wait_until="domcontentloaded", timeout=15_000)
                        pwd = page.locator("input[type='password']")
                        if await pwd.is_visible(timeout=3_000):
                            await pwd.fill(password)
                            await page.locator("button[type='submit'], input[type='submit']").click()
                            await page.wait_for_load_state("domcontentloaded")
                    except Exception:
                        pass

                await page.goto(url, wait_until="networkidle", timeout=timeout)

                # Scroll to trigger lazy-loaded fonts/images, then back to top
                await page.evaluate("window.scrollTo(0, Math.min(document.body.scrollHeight, 3000))")
                await asyncio.sleep(1.2)
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(0.6)

                raw: dict = await page.evaluate(_EXTRACT_SCRIPT)
                await browser.close()

                return DomProfile(
                    url=url,
                    viewport=raw.get("viewport", {}),
                    global_styles=raw.get("global", {}),
                    header=raw.get("header"),
                    footer=raw.get("footer"),
                    sections=raw.get("sections", []),
                    viewport_width=viewport_width,
                )

        except Exception as exc:
            logger.warning("DOM extraction failed for %s: %s", url, exc)
            return DomProfile(url=url, viewport_width=viewport_width)
