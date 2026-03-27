"""SEO & Performance analysis engine.

Runs inside Playwright — checks meta tags, headings, schema markup,
page speed metrics, and resource optimization.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

_BROWSER_ARGS = ["--disable-blink-features=AutomationControlled"]
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# JavaScript that runs SEO + Performance checks
# ---------------------------------------------------------------------------

_SEO_PERF_JS = """
() => {
    const results = { seo: [], performance: {} };

    // ===================== SEO CHECKS =====================

    // 1. Title tag
    const title = document.title || '';
    results.seo.push({
        test: 'title_tag',
        label: 'Page Title',
        pass: title.length > 0 && title.length <= 60,
        value: title || '(empty)',
        recommendation: title.length === 0
            ? 'Add a <title> tag — essential for SEO'
            : title.length > 60
            ? `Title is ${title.length} chars — keep under 60 for search results`
            : null,
        severity: title.length === 0 ? 'critical' : title.length > 60 ? 'minor' : null,
    });

    // 2. Meta description
    const metaDesc = document.querySelector('meta[name="description"]');
    const descContent = metaDesc ? (metaDesc.getAttribute('content') || '') : '';
    results.seo.push({
        test: 'meta_description',
        label: 'Meta Description',
        pass: descContent.length >= 50 && descContent.length <= 160,
        value: descContent ? descContent.substring(0, 80) + (descContent.length > 80 ? '...' : '') : '(missing)',
        recommendation: !descContent
            ? 'Add a meta description — important for click-through rates'
            : descContent.length < 50
            ? `Description is only ${descContent.length} chars — aim for 50-160`
            : descContent.length > 160
            ? `Description is ${descContent.length} chars — keep under 160`
            : null,
        severity: !descContent ? 'major' : (descContent.length < 50 || descContent.length > 160) ? 'minor' : null,
    });

    // 3. H1 tag
    const h1s = document.querySelectorAll('h1');
    results.seo.push({
        test: 'h1_tag',
        label: 'H1 Heading',
        pass: h1s.length === 1,
        value: h1s.length === 0 ? '(none)' : h1s.length === 1 ? h1s[0].textContent.trim().substring(0, 60) : `${h1s.length} H1 tags found`,
        recommendation: h1s.length === 0
            ? 'Add an H1 heading — critical for SEO'
            : h1s.length > 1
            ? `Found ${h1s.length} H1 tags — use exactly 1 per page`
            : null,
        severity: h1s.length === 0 ? 'major' : h1s.length > 1 ? 'minor' : null,
    });

    // 4. Heading hierarchy (H1 → H2 → H3)
    const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'));
    let hierarchyOk = true;
    let lastLevel = 0;
    for (const h of headings) {
        const level = parseInt(h.tagName[1]);
        if (level > lastLevel + 1 && lastLevel > 0) { hierarchyOk = false; break; }
        lastLevel = level;
    }
    results.seo.push({
        test: 'heading_hierarchy',
        label: 'Heading Hierarchy',
        pass: hierarchyOk,
        value: hierarchyOk ? 'Correct order' : 'Skipped levels detected',
        recommendation: hierarchyOk ? null : 'Headings skip levels (e.g. H1 → H3). Use H1 → H2 → H3 in order',
        severity: hierarchyOk ? null : 'minor',
    });

    // 5. Canonical URL
    const canonical = document.querySelector('link[rel="canonical"]');
    results.seo.push({
        test: 'canonical_url',
        label: 'Canonical URL',
        pass: !!canonical,
        value: canonical ? canonical.getAttribute('href') : '(missing)',
        recommendation: canonical ? null : 'Add a canonical URL to prevent duplicate content issues',
        severity: canonical ? null : 'major',
    });

    // 6. Meta viewport
    const viewport = document.querySelector('meta[name="viewport"]');
    results.seo.push({
        test: 'meta_viewport',
        label: 'Mobile Viewport',
        pass: !!viewport,
        value: viewport ? 'Present' : '(missing)',
        recommendation: viewport ? null : 'Add <meta name="viewport"> for mobile-friendly pages',
        severity: viewport ? null : 'major',
    });

    // 7. Open Graph tags
    const ogTitle = document.querySelector('meta[property="og:title"]');
    const ogDesc = document.querySelector('meta[property="og:description"]');
    const ogImage = document.querySelector('meta[property="og:image"]');
    const ogCount = [ogTitle, ogDesc, ogImage].filter(Boolean).length;
    results.seo.push({
        test: 'open_graph',
        label: 'Open Graph Tags',
        pass: ogCount === 3,
        value: `${ogCount}/3 tags present`,
        recommendation: ogCount < 3
            ? `Missing: ${[!ogTitle && 'og:title', !ogDesc && 'og:description', !ogImage && 'og:image'].filter(Boolean).join(', ')}`
            : null,
        severity: ogCount === 0 ? 'major' : ogCount < 3 ? 'minor' : null,
    });

    // 8. Image alt text
    const imgs = Array.from(document.querySelectorAll('img'));
    const withoutAlt = imgs.filter(img => !img.alt && img.offsetWidth > 0);
    results.seo.push({
        test: 'image_alt',
        label: 'Image Alt Text',
        pass: withoutAlt.length === 0,
        value: withoutAlt.length === 0 ? `All ${imgs.length} images have alt` : `${withoutAlt.length} of ${imgs.length} missing alt`,
        recommendation: withoutAlt.length > 0 ? `Add alt text to ${withoutAlt.length} image(s) for SEO and accessibility` : null,
        severity: withoutAlt.length > 5 ? 'major' : withoutAlt.length > 0 ? 'minor' : null,
    });

    // 9. Schema / Structured data
    const schemas = document.querySelectorAll('script[type="application/ld+json"]');
    results.seo.push({
        test: 'structured_data',
        label: 'Structured Data (Schema.org)',
        pass: schemas.length > 0,
        value: schemas.length > 0 ? `${schemas.length} schema(s) found` : '(none)',
        recommendation: schemas.length === 0 ? 'Add JSON-LD structured data for rich search results' : null,
        severity: schemas.length === 0 ? 'minor' : null,
    });

    // 10. Robots meta
    const robotsMeta = document.querySelector('meta[name="robots"]');
    const isNoindex = robotsMeta && (robotsMeta.getAttribute('content') || '').includes('noindex');
    results.seo.push({
        test: 'robots_meta',
        label: 'Robots Meta',
        pass: !isNoindex,
        value: isNoindex ? 'NOINDEX set — page hidden from search' : robotsMeta ? robotsMeta.getAttribute('content') : 'Not set (default: index)',
        recommendation: isNoindex ? 'Page has noindex — it will NOT appear in search results. Remove if unintended.' : null,
        severity: isNoindex ? 'critical' : null,
    });

    // 11. Internal links
    const internalLinks = Array.from(document.querySelectorAll('a[href]')).filter(a => {
        const href = a.getAttribute('href') || '';
        return href.startsWith('/') || href.includes(window.location.hostname);
    });
    results.seo.push({
        test: 'internal_links',
        label: 'Internal Links',
        pass: internalLinks.length >= 3,
        value: `${internalLinks.length} internal links`,
        recommendation: internalLinks.length < 3 ? 'Add more internal links to improve crawlability' : null,
        severity: internalLinks.length < 3 ? 'minor' : null,
    });

    // 12. HTTPS check
    results.seo.push({
        test: 'https',
        label: 'HTTPS',
        pass: window.location.protocol === 'https:',
        value: window.location.protocol === 'https:' ? 'Secure' : 'NOT secure',
        recommendation: window.location.protocol !== 'https:' ? 'Switch to HTTPS — required for SEO ranking' : null,
        severity: window.location.protocol !== 'https:' ? 'critical' : null,
    });

    // ===================== PERFORMANCE CHECKS =====================

    const perf = window.performance;
    const timing = perf.timing || {};
    const entries = perf.getEntriesByType('resource') || [];

    // Page load time
    const loadTime = timing.loadEventEnd && timing.navigationStart
        ? timing.loadEventEnd - timing.navigationStart : 0;

    // DOM content loaded
    const domReady = timing.domContentLoadedEventEnd && timing.navigationStart
        ? timing.domContentLoadedEventEnd - timing.navigationStart : 0;

    // First byte (TTFB)
    const ttfb = timing.responseStart && timing.requestStart
        ? timing.responseStart - timing.requestStart : 0;

    // Resources
    const totalResources = entries.length;
    const totalSize = entries.reduce((sum, e) => sum + (e.transferSize || 0), 0);
    const jsFiles = entries.filter(e => e.initiatorType === 'script');
    const cssFiles = entries.filter(e => e.initiatorType === 'css' || e.initiatorType === 'link');
    const imgFiles = entries.filter(e => e.initiatorType === 'img');
    const jsSize = jsFiles.reduce((sum, e) => sum + (e.transferSize || 0), 0);
    const cssSize = cssFiles.reduce((sum, e) => sum + (e.transferSize || 0), 0);
    const imgSize = imgFiles.reduce((sum, e) => sum + (e.transferSize || 0), 0);

    // DOM size
    const domNodes = document.querySelectorAll('*').length;

    results.performance = {
        load_time_ms: loadTime,
        dom_ready_ms: domReady,
        ttfb_ms: ttfb,
        total_resources: totalResources,
        total_size_bytes: totalSize,
        js_count: jsFiles.length,
        js_size_bytes: jsSize,
        css_count: cssFiles.length,
        css_size_bytes: cssSize,
        img_count: imgFiles.length,
        img_size_bytes: imgSize,
        dom_nodes: domNodes,
    };

    // Performance issues
    const perfIssues = [];

    if (loadTime > 5000) {
        perfIssues.push({ test: 'page_load', label: 'Page Load Time', severity: loadTime > 10000 ? 'critical' : 'major',
            value: (loadTime / 1000).toFixed(1) + 's', recommendation: 'Page takes too long to load. Optimize images, reduce JS, enable caching.' });
    }
    if (ttfb > 600) {
        perfIssues.push({ test: 'ttfb', label: 'Time to First Byte', severity: ttfb > 1500 ? 'major' : 'minor',
            value: ttfb + 'ms', recommendation: 'TTFB is slow. Check server response time, enable CDN.' });
    }
    if (totalSize > 5 * 1024 * 1024) {
        perfIssues.push({ test: 'page_size', label: 'Total Page Size', severity: totalSize > 10 * 1024 * 1024 ? 'critical' : 'major',
            value: (totalSize / 1024 / 1024).toFixed(1) + ' MB', recommendation: 'Page is too large. Compress images, minify CSS/JS, lazy-load resources.' });
    }
    if (jsSize > 1 * 1024 * 1024) {
        perfIssues.push({ test: 'js_size', label: 'JavaScript Size', severity: 'major',
            value: (jsSize / 1024).toFixed(0) + ' KB', recommendation: 'Too much JavaScript. Code-split, tree-shake, defer non-critical scripts.' });
    }
    if (imgSize > 3 * 1024 * 1024) {
        perfIssues.push({ test: 'img_size', label: 'Image Size', severity: 'major',
            value: (imgSize / 1024 / 1024).toFixed(1) + ' MB', recommendation: 'Images are too large. Use WebP format, compress images, add lazy loading.' });
    }
    if (domNodes > 1500) {
        perfIssues.push({ test: 'dom_size', label: 'DOM Size', severity: domNodes > 3000 ? 'major' : 'minor',
            value: domNodes + ' nodes', recommendation: 'DOM is too large. Reduce unnecessary HTML elements, simplify layout.' });
    }
    if (totalResources > 80) {
        perfIssues.push({ test: 'resource_count', label: 'Resource Count', severity: 'minor',
            value: totalResources + ' resources', recommendation: 'Too many HTTP requests. Combine files, use sprites, inline critical CSS.' });
    }

    results.performance.issues = perfIssues;
    return results;
}
""";


@dataclass
class SeoResult:
    test: str
    label: str
    passed: bool
    value: str
    recommendation: str | None = None
    severity: str | None = None


@dataclass
class PerformanceMetrics:
    load_time_ms: int = 0
    dom_ready_ms: int = 0
    ttfb_ms: int = 0
    total_resources: int = 0
    total_size_bytes: int = 0
    js_count: int = 0
    js_size_bytes: int = 0
    css_count: int = 0
    css_size_bytes: int = 0
    img_count: int = 0
    img_size_bytes: int = 0
    dom_nodes: int = 0
    issues: list = field(default_factory=list)


@dataclass
class SeoPerformanceResult:
    page: str
    seo_checks: list[SeoResult] = field(default_factory=list)
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)


class SeoPerformanceEngine:
    """Runs SEO and performance analysis on a page using Playwright."""

    async def analyze_page(
        self,
        page_url: str,
        password: str | None = None,
    ) -> SeoPerformanceResult:
        from playwright.async_api import async_playwright
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(page_url)
        base_store = f"{parsed.scheme}://{parsed.netloc}"
        page_name = parsed.path.strip("/") or "home"

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=_BROWSER_ARGS)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=_USER_AGENT,
            )
            page = await context.new_page()

            if password:
                try:
                    await page.goto(f"{base_store}/password", wait_until="domcontentloaded", timeout=30000)
                    pwd_input = page.locator("input[type='password']")
                    if await pwd_input.is_visible(timeout=3000):
                        await pwd_input.fill(password)
                        await page.locator("button[type='submit'], input[type='submit']").click()
                        await page.wait_for_load_state("domcontentloaded")
                except Exception:
                    pass

            preview_id = parse_qs(parsed.query).get("preview_theme_id", [None])[0]
            if preview_id:
                await context.add_cookies([{
                    "name": "preview_theme_id",
                    "value": preview_id,
                    "domain": parsed.netloc,
                    "path": "/",
                }])

            await page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)

            try:
                raw = await page.evaluate(_SEO_PERF_JS)
            except Exception:
                raw = {"seo": [], "performance": {}}

            await browser.close()

        seo_checks = []
        for item in raw.get("seo", []):
            seo_checks.append(SeoResult(
                test=item.get("test", ""),
                label=item.get("label", ""),
                passed=item.get("pass", False),
                value=str(item.get("value", "")),
                recommendation=item.get("recommendation"),
                severity=item.get("severity"),
            ))

        perf_data = raw.get("performance", {})
        perf = PerformanceMetrics(
            load_time_ms=perf_data.get("load_time_ms", 0),
            dom_ready_ms=perf_data.get("dom_ready_ms", 0),
            ttfb_ms=perf_data.get("ttfb_ms", 0),
            total_resources=perf_data.get("total_resources", 0),
            total_size_bytes=perf_data.get("total_size_bytes", 0),
            js_count=perf_data.get("js_count", 0),
            js_size_bytes=perf_data.get("js_size_bytes", 0),
            css_count=perf_data.get("css_count", 0),
            css_size_bytes=perf_data.get("css_size_bytes", 0),
            img_count=perf_data.get("img_count", 0),
            img_size_bytes=perf_data.get("img_size_bytes", 0),
            dom_nodes=perf_data.get("dom_nodes", 0),
            issues=perf_data.get("issues", []),
        )

        return SeoPerformanceResult(page=page_name, seo_checks=seo_checks, performance=perf)
