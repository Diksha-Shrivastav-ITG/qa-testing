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
async () => {
    const results = { seo: [], performance: {} };

    // ===================== SEO CHECKS =====================

    // 1. Title tag
    const title = document.title || '';
    results.seo.push({
        test: 'title_tag',
        label: 'Page Title',
        pass: title.length > 0 && title.length <= 60,
        value: title
            ? title + ' (' + title.length + '/60 chars)'
            : '(empty — no title tag found)',
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
        value: descContent
            ? descContent + ' (' + descContent.length + '/160 chars)'
            : '(missing — no meta description tag found)',
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
    let h1Value = '';
    if (h1s.length === 0) {
        h1Value = '(none — no H1 heading found on page)';
    } else if (h1s.length === 1) {
        h1Value = 'H1: "' + h1s[0].textContent.trim().substring(0, 100) + '"';
    } else {
        const h1Texts = Array.from(h1s).map((h, i) => 'H1 #' + (i + 1) + ': "' + h.textContent.trim().substring(0, 100) + '"');
        h1Value = h1s.length + ' H1 tags found (should be exactly 1)\\n' + h1Texts.join('\\n');
    }
    results.seo.push({
        test: 'h1_tag',
        label: 'H1 Heading',
        pass: h1s.length === 1,
        value: h1Value,
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
    let skippedFrom = '';
    let skippedTo = '';
    const headingDetails = [];
    for (const h of headings) {
        const level = parseInt(h.tagName[1]);
        const text = h.textContent.trim().substring(0, 100) || '(empty)';
        headingDetails.push('H' + level + ': ' + text);
        if (level > lastLevel + 1 && lastLevel > 0 && skippedFrom === '') {
            hierarchyOk = false;
            skippedFrom = 'H' + lastLevel;
            skippedTo = 'H' + level;
        }
        lastLevel = level;
    }
    const headingList = headingDetails.join('\\n');
    results.seo.push({
        test: 'heading_hierarchy',
        label: 'Heading Hierarchy',
        pass: hierarchyOk,
        value: hierarchyOk
            ? 'Correct order — ' + headings.length + ' heading(s) found\\n' + headingList
            : 'Skipped levels detected (' + skippedFrom + ' → ' + skippedTo + ') — ' + headings.length + ' heading(s)\\n' + headingList,
        recommendation: hierarchyOk ? null : 'Headings skip levels (' + skippedFrom + ' → ' + skippedTo + '). Use H1 → H2 → H3 in order without skipping.',
        severity: hierarchyOk ? null : 'minor',
    });

    // 5. Canonical URL
    const canonical = document.querySelector('link[rel="canonical"]');
    const canonicalHref = canonical ? (canonical.getAttribute('href') || '') : '';
    const matchesCurrent = canonicalHref && (canonicalHref === window.location.href || canonicalHref === window.location.pathname);
    results.seo.push({
        test: 'canonical_url',
        label: 'Canonical URL',
        pass: !!canonical,
        value: canonical
            ? 'Set to: ' + canonicalHref + (matchesCurrent ? ' (matches current page)' : ' (points to different URL)')
            : '(missing — no canonical link tag found)',
        recommendation: canonical ? null : 'Add a canonical URL to prevent duplicate content issues',
        severity: canonical ? null : 'major',
    });

    // 6. Meta viewport
    const viewport = document.querySelector('meta[name="viewport"]');
    results.seo.push({
        test: 'meta_viewport',
        label: 'Mobile Viewport',
        pass: !!viewport,
        value: viewport ? 'Present — ' + (viewport.getAttribute('content') || '') : '(missing — no viewport meta tag found)',
        recommendation: viewport ? null : 'Add <meta name="viewport"> for mobile-friendly pages',
        severity: viewport ? null : 'major',
    });

    // 7. Open Graph tags
    const ogTitle = document.querySelector('meta[property="og:title"]');
    const ogDesc = document.querySelector('meta[property="og:description"]');
    const ogImage = document.querySelector('meta[property="og:image"]');
    const ogCount = [ogTitle, ogDesc, ogImage].filter(Boolean).length;
    const ogDetails = [];
    if (ogTitle) ogDetails.push('og:title: ' + (ogTitle.getAttribute('content') || '').substring(0, 100));
    else ogDetails.push('og:title: (missing)');
    if (ogDesc) ogDetails.push('og:description: ' + (ogDesc.getAttribute('content') || '').substring(0, 120));
    else ogDetails.push('og:description: (missing)');
    if (ogImage) ogDetails.push('og:image: ' + (ogImage.getAttribute('content') || ''));
    else ogDetails.push('og:image: (missing)');
    results.seo.push({
        test: 'open_graph',
        label: 'Open Graph Tags',
        pass: ogCount === 3,
        value: ogCount + '/3 tags present\\n' + ogDetails.join('\\n'),
        recommendation: ogCount < 3
            ? `Missing: ${[!ogTitle && 'og:title', !ogDesc && 'og:description', !ogImage && 'og:image'].filter(Boolean).join(', ')}`
            : null,
        severity: ogCount === 0 ? 'major' : ogCount < 3 ? 'minor' : null,
    });

    // 8. Image alt text
    const imgs = Array.from(document.querySelectorAll('img'));
    const withoutAlt = imgs.filter(img => !img.alt && img.offsetWidth > 0);
    let imgAltValue = '';
    if (withoutAlt.length === 0) {
        imgAltValue = 'All ' + imgs.length + ' images have alt text';
    } else {
        const missingSrcs = withoutAlt.slice(0, 20).map((img, i) => {
            const src = img.src || img.getAttribute('data-src') || img.getAttribute('data-srcset') || '(no src)';
            const shortSrc = src.length > 100 ? '...' + src.slice(-80) : src;
            return (i + 1) + '. ' + shortSrc;
        });
        imgAltValue = withoutAlt.length + ' of ' + imgs.length + ' images missing alt text\\n' + missingSrcs.join('\\n');
        if (withoutAlt.length > 20) imgAltValue += '\\n... and ' + (withoutAlt.length - 20) + ' more';
    }
    results.seo.push({
        test: 'image_alt',
        label: 'Image Alt Text',
        pass: withoutAlt.length === 0,
        value: imgAltValue,
        recommendation: withoutAlt.length > 0 ? `Add alt text to ${withoutAlt.length} image(s) for SEO and accessibility` : null,
        severity: withoutAlt.length > 5 ? 'major' : withoutAlt.length > 0 ? 'minor' : null,
    });

    // 9. Schema / Structured data
    const schemas = document.querySelectorAll('script[type="application/ld+json"]');
    let schemaValue = '';
    if (schemas.length === 0) {
        schemaValue = '(none — no JSON-LD structured data found)';
    } else {
        const schemaTypes = [];
        schemas.forEach(s => {
            try {
                const data = JSON.parse(s.textContent);
                if (Array.isArray(data)) {
                    data.forEach(d => { if (d['@type']) schemaTypes.push(d['@type']); });
                } else if (data['@type']) {
                    schemaTypes.push(data['@type']);
                } else if (data['@graph']) {
                    data['@graph'].forEach(d => { if (d['@type']) schemaTypes.push(d['@type']); });
                }
            } catch(e) {}
        });
        schemaValue = schemas.length + ' schema(s) found';
        if (schemaTypes.length > 0) schemaValue += '\\nTypes: ' + schemaTypes.join(', ');
    }
    results.seo.push({
        test: 'structured_data',
        label: 'Structured Data (Schema.org)',
        pass: schemas.length > 0,
        value: schemaValue,
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
    let internalLinksValue = internalLinks.length + ' internal links found';
    if (internalLinks.length > 0) {
        const uniqueHrefs = [...new Set(internalLinks.map(a => a.getAttribute('href')))].slice(0, 30);
        internalLinksValue += '\\n' + uniqueHrefs.join('\\n');
        if (internalLinks.length > 30) internalLinksValue += '\\n... and more';
    }
    results.seo.push({
        test: 'internal_links',
        label: 'Internal Links',
        pass: internalLinks.length >= 3,
        value: internalLinksValue,
        recommendation: internalLinks.length < 3 ? 'Add more internal links to improve crawlability' : null,
        severity: internalLinks.length < 3 ? 'minor' : null,
    });

    // 12. HTTPS check
    results.seo.push({
        test: 'https',
        label: 'HTTPS',
        pass: window.location.protocol === 'https:',
        value: window.location.protocol === 'https:'
            ? 'Secure — site is served over HTTPS (' + window.location.origin + ')'
            : 'NOT secure — site is served over HTTP (' + window.location.origin + ')',
        recommendation: window.location.protocol !== 'https:' ? 'Switch to HTTPS — required for SEO ranking' : null,
        severity: window.location.protocol !== 'https:' ? 'critical' : null,
    });

    // 13. Google Tag Manager (GTM)
    const gtmObj = window.google_tag_manager;
    const dataLayer = window.dataLayer;
    const hasGtm = !!gtmObj && Array.isArray(dataLayer);
    const gtmStarted = hasGtm && dataLayer.some(e => e && e.event === 'gtm.start');

    // Extract all GTM container IDs from scripts
    const allScripts = Array.from(document.querySelectorAll('script'));
    const gtmIds = new Set();
    allScripts.forEach(s => {
        const matches = (s.src + (s.textContent || '')).match(/GTM-[A-Z0-9]+/g);
        if (matches) matches.forEach(id => gtmIds.add(id));
    });
    const gtmIdList = Array.from(gtmIds);
    const hasDuplicateGtm = gtmIdList.length > 1;

    // Check for noscript fallback iframe
    const noscripts = Array.from(document.querySelectorAll('noscript'));
    const hasGtmNoscript = noscripts.some(ns => ns.innerHTML.includes('googletagmanager.com'));

    // Main GTM check — passes if GTM is detected and firing
    if (!hasGtm) {
        results.seo.push({
            test: 'gtm_check', label: 'Google Tag Manager (GTM)', pass: false,
            value: '(not installed)',
            recommendation: 'Install Google Tag Manager to manage marketing tags and tracking scripts',
            severity: 'critical',
        });
    } else if (!gtmStarted) {
        results.seo.push({
            test: 'gtm_check', label: 'Google Tag Manager (GTM)', pass: false,
            value: gtmIdList.length > 0 ? gtmIdList[0] + ' found but not firing' : 'GTM found but not firing',
            recommendation: 'GTM container is present but not loading. Check the container snippet placement and ID.',
            severity: 'major',
        });
    } else {
        results.seo.push({
            test: 'gtm_check', label: 'Google Tag Manager (GTM)', pass: true,
            value: gtmIdList[0] + ' active' + (hasGtmNoscript ? ', noscript present' : ''),
            recommendation: null, severity: null,
        });
    }

    // Sub-warning: missing noscript fallback
    if (hasGtm && gtmStarted && !hasGtmNoscript) {
        results.seo.push({
            test: 'gtm_noscript', label: 'GTM Noscript Fallback', pass: false,
            value: 'Missing <noscript> iframe for GTM',
            recommendation: 'Add the GTM noscript fallback iframe after the opening <body> tag for non-JS environments',
            severity: 'minor',
        });
    }

    // Sub-warning: duplicate containers
    if (hasDuplicateGtm) {
        results.seo.push({
            test: 'gtm_duplicates', label: 'GTM Duplicate Containers', pass: false,
            value: 'Multiple containers: ' + gtmIdList.join(', '),
            recommendation: 'Multiple GTM containers detected. Use a single container to avoid conflicts and double-tracking.',
            severity: 'minor',
        });
    }

    // 14. Google Analytics 4 (GA4)
    const hasGtagFn = typeof window.gtag === 'function';
    const gtagScripts = allScripts.filter(s => s.src && s.src.includes('gtag/js'));
    const hasGtagScript = gtagScripts.length > 0;

    // Extract G-XXXXXX measurement IDs from inline scripts
    const ga4Ids = new Set();
    allScripts.forEach(s => {
        const text = s.textContent || '';
        const matches = text.match(/G-[A-Z0-9]+/g);
        if (matches) matches.forEach(id => ga4Ids.add(id));
    });
    // Also extract from script src attributes
    gtagScripts.forEach(s => {
        const srcMatch = s.src.match(/id=(G-[A-Z0-9]+)/);
        if (srcMatch) ga4Ids.add(srcMatch[1]);
    });
    const ga4IdList = Array.from(ga4Ids);

    // Check for network requests to GA endpoints
    const resourceEntries = performance.getEntriesByType('resource') || [];
    const ga4Requests = resourceEntries.filter(e =>
        e.name.includes('google-analytics.com') ||
        e.name.includes('googletagmanager.com/gtag')
    );
    const isSendingData = ga4Requests.length > 0;

    const ga4Detected = hasGtagFn || hasGtagScript || ga4IdList.length > 0;
    const hasDuplicateGa4 = ga4IdList.length > 1;

    // Main GA4 check
    if (!ga4Detected) {
        results.seo.push({
            test: 'ga4_check', label: 'Google Analytics 4 (GA4)', pass: false,
            value: '(not installed)',
            recommendation: 'Install Google Analytics 4 to track website traffic and user behavior',
            severity: 'critical',
        });
    } else if (!isSendingData) {
        results.seo.push({
            test: 'ga4_check', label: 'Google Analytics 4 (GA4)', pass: false,
            value: ga4IdList.length > 0
                ? 'GA4 script found (' + ga4IdList[0] + ') but not sending data'
                : 'GA4 script found but not sending data',
            recommendation: 'GA4 is installed but not sending data. Verify the measurement ID and gtag configuration.',
            severity: 'major',
        });
    } else {
        results.seo.push({
            test: 'ga4_check', label: 'Google Analytics 4 (GA4)', pass: true,
            value: 'GA4 active' + (ga4IdList.length > 0 ? ' (' + ga4IdList[0] + ')' : '') + ', sending data',
            recommendation: null, severity: null,
        });
    }

    // Sub-warning: duplicate tracking
    if (hasDuplicateGa4) {
        results.seo.push({
            test: 'ga4_duplicates', label: 'GA4 Duplicate Tracking', pass: false,
            value: 'Duplicate tracking: ' + ga4IdList.join(', '),
            recommendation: 'Multiple GA4 measurement IDs detected. This causes double-counted pageviews and inflated metrics.',
            severity: 'minor',
        });
    }

    // 17. Google Ads Tag
    const googleAdsIds = new Set();
    allScripts.forEach(s => {
        const text = (s.src || '') + (s.textContent || '');
        const matches = text.match(/AW-[0-9]+/g);
        if (matches) matches.forEach(id => googleAdsIds.add(id));
    });
    const adsIdList = Array.from(googleAdsIds);
    const hasGoogleAds = adsIdList.length > 0;
    const hasAdsConversion = allScripts.some(s => {
        const text = s.textContent || '';
        return text.includes("'conversion'") && text.includes('AW-');
    });

    if (!hasGoogleAds) {
        results.seo.push({
            test: 'google_ads_check', label: 'Google Ads Tag', pass: false,
            value: '(not installed)',
            recommendation: 'No Google Ads tag detected. Install Google Ads conversion tracking if running paid campaigns.',
            severity: 'minor',
        });
    } else {
        results.seo.push({
            test: 'google_ads_check', label: 'Google Ads Tag', pass: true,
            value: adsIdList.join(', ') + (hasAdsConversion ? ' — conversion tracking active' : ' — no conversion events found'),
            recommendation: hasAdsConversion ? null : 'Google Ads tag found but no conversion events detected. Set up conversion tracking to optimize campaigns.',
            severity: hasAdsConversion ? null : 'minor',
        });
    }

    // 18. Google Tag (gtag.js)
    const gtagScriptEl = allScripts.find(s => s.src && s.src.includes('gtag/js'));
    const hasGtagFunc = typeof window.gtag === 'function';
    const hasDataLayerArr = Array.isArray(window.dataLayer);
    const gtagInstalled = !!gtagScriptEl || hasGtagFunc;

    const gtagConfigIds = new Set();
    allScripts.forEach(s => {
        const text = s.textContent || '';
        const cfgIds = text.match(/['"](?:G|AW|DC)-[A-Z0-9]+['"]/g);
        if (cfgIds) {
            cfgIds.forEach(m => {
                const clean = m.replace(/['"]/g, '');
                gtagConfigIds.add(clean);
            });
        }
    });
    const gtagIdList = Array.from(gtagConfigIds);

    if (!gtagInstalled) {
        results.seo.push({
            test: 'gtag_check', label: 'Google Tag (gtag.js)', pass: false,
            value: '(not installed)',
            recommendation: 'Install Google Tag (gtag.js) to enable Google Analytics, Ads, and other Google services tracking.',
            severity: 'major',
        });
    } else {
        results.seo.push({
            test: 'gtag_check', label: 'Google Tag (gtag.js)', pass: true,
            value: 'Active' + (gtagIdList.length > 0 ? ' — Configs: ' + gtagIdList.join(', ') : '') + (hasDataLayerArr ? ', dataLayer initialized' : ''),
            recommendation: null, severity: null,
        });
    }

    // 19. Facebook/Meta Pixel
    const hasFbq = typeof window.fbq === 'function';
    const hasFbPixelScript = allScripts.some(s =>
        s.src && (s.src.includes('fbevents.js') || s.src.includes('connect.facebook.net'))
    );
    const fbPixelIds = new Set();
    allScripts.forEach(s => {
        const text = s.textContent || '';
        if (text.includes('fbq')) {
            const initMatches = text.match(/fbq *\( *['"]init['"] *, *['"]([0-9]+)['"]/g);
            if (initMatches) {
                initMatches.forEach(m => {
                    const idMatch = m.match(/['"]([0-9]{6,20})['"]/);
                    if (idMatch) fbPixelIds.add(idMatch[1]);
                });
            }
        }
    });
    const fbIdList = Array.from(fbPixelIds);
    const fbDetected = hasFbq || hasFbPixelScript || fbIdList.length > 0;
    const hasFbNoscript = noscripts.some(ns => ns.innerHTML.includes('facebook.com/tr'));
    const hasFbPageView = allScripts.some(s => {
        const text = s.textContent || '';
        return text.includes('fbq') && text.includes('PageView');
    });

    if (!fbDetected) {
        results.seo.push({
            test: 'fb_pixel_check', label: 'Facebook/Meta Pixel', pass: false,
            value: '(not installed)',
            recommendation: 'Install Facebook/Meta Pixel to track conversions and build audiences for Facebook & Instagram ads.',
            severity: 'minor',
        });
    } else if (!hasFbPageView) {
        results.seo.push({
            test: 'fb_pixel_check', label: 'Facebook/Meta Pixel', pass: false,
            value: fbIdList.length > 0 ? 'Pixel ' + fbIdList[0] + ' found but PageView not tracking' : 'Pixel found but PageView not tracking',
            recommendation: 'Facebook Pixel is installed but PageView event is not firing. Verify fbq("track", "PageView") is called.',
            severity: 'major',
        });
    } else {
        results.seo.push({
            test: 'fb_pixel_check', label: 'Facebook/Meta Pixel', pass: true,
            value: (fbIdList.length > 0 ? 'Pixel ' + fbIdList[0] : 'Pixel active') + ', PageView tracking' + (hasFbNoscript ? ', noscript present' : ''),
            recommendation: null, severity: null,
        });
    }

    // Sub-warning: multiple Facebook pixels
    if (fbIdList.length > 1) {
        results.seo.push({
            test: 'fb_pixel_duplicates', label: 'Facebook Pixel Duplicates', pass: false,
            value: 'Multiple pixels: ' + fbIdList.join(', '),
            recommendation: 'Multiple Facebook Pixels detected. Use a single pixel to avoid double-counting conversion events.',
            severity: 'minor',
        });
    }

    // Sub-warning: missing Facebook noscript fallback
    if (fbDetected && !hasFbNoscript) {
        results.seo.push({
            test: 'fb_pixel_noscript', label: 'Facebook Pixel Noscript', pass: false,
            value: 'Missing <noscript> fallback for Facebook Pixel',
            recommendation: 'Add the Facebook Pixel noscript <img> tag for tracking in non-JavaScript environments.',
            severity: 'minor',
        });
    }

    // ===================== ASYNC RESOURCE CHECKS =====================

    let sitemapOk = false;
    let sitemapUrls = [];
    let sitemapSubFiles = [];
    try {
        const sitemapAc = new AbortController();
        const sitemapTimer = setTimeout(() => sitemapAc.abort(), 8000);
        const sitemapResp = await fetch('/sitemap.xml', { signal: sitemapAc.signal });
        clearTimeout(sitemapTimer);
        sitemapOk = sitemapResp.ok;
        if (sitemapOk) {
            const sitemapText = await sitemapResp.text();
            const isSitemapIndex = sitemapText.includes('<sitemapindex');
            if (isSitemapIndex) {
                const indexLocs = sitemapText.match(/<loc>([\\s\\S]*?)<\\/loc>/gi) || [];
                sitemapSubFiles = indexLocs.map(m => m.replace(/<\\/?loc>/gi, '').trim());
                const fetchPromises = sitemapSubFiles.slice(0, 10).map(async (subUrl) => {
                    try {
                        const ac = new AbortController();
                        const t = setTimeout(() => ac.abort(), 5000);
                        const r = await fetch(subUrl, { signal: ac.signal });
                        clearTimeout(t);
                        if (r.ok) {
                            const txt = await r.text();
                            return (txt.match(/<loc>([\\s\\S]*?)<\\/loc>/gi) || []).map(m => m.replace(/<\\/?loc>/gi, '').trim());
                        }
                    } catch(e) {}
                    return [];
                });
                const allResults = await Promise.all(fetchPromises);
                allResults.forEach(urls => { sitemapUrls.push(...urls); });
            } else {
                const locMatches = sitemapText.match(/<loc>([\\s\\S]*?)<\\/loc>/gi) || [];
                sitemapUrls = locMatches.map(m => m.replace(/<\\/?loc>/gi, '').trim());
            }
        }
    } catch(e) {}

    let bingSiteAuthOk = false;
    try {
        const bingAc = new AbortController();
        const bingTimer = setTimeout(() => bingAc.abort(), 5000);
        const bingAuthResp = await fetch('/BingSiteAuth.xml', { method: 'HEAD', signal: bingAc.signal });
        clearTimeout(bingTimer);
        bingSiteAuthOk = bingAuthResp.ok;
    } catch(e) {}

    let robotsTxtOk = false;
    let robotsTxtContent = '';
    try {
        const robotsAc = new AbortController();
        const robotsTimer = setTimeout(() => robotsAc.abort(), 5000);
        const robotsResp = await fetch('/robots.txt', { signal: robotsAc.signal });
        clearTimeout(robotsTimer);
        robotsTxtOk = robotsResp.ok;
        if (robotsTxtOk) {
            robotsTxtContent = (await robotsResp.text()).substring(0, 2000);
        }
    } catch(e) {}

    // 15. Google Search Console (GSC)
    const gscMeta = document.querySelector('meta[name="google-site-verification"]');
    const gscContent = gscMeta ? (gscMeta.getAttribute('content') || '').trim() : '';
    const hasGscVerification = gscContent.length > 0;

    if (!hasGscVerification && !sitemapOk) {
        results.seo.push({
            test: 'gsc_check', label: 'Google Search Console Verification', pass: false,
            value: '(verification tag missing)',
            recommendation: 'Add <meta name="google-site-verification"> tag and ensure /sitemap.xml is accessible for Google Search Console',
            severity: 'major',
        });
    } else if (!hasGscVerification) {
        results.seo.push({
            test: 'gsc_check', label: 'Google Search Console Verification', pass: false,
            value: '(verification tag missing, sitemap.xml accessible)',
            recommendation: 'Add <meta name="google-site-verification"> tag to verify site ownership in Google Search Console',
            severity: 'major',
        });
    } else if (!sitemapOk) {
        results.seo.push({
            test: 'gsc_check', label: 'Google Search Console Verification', pass: false,
            value: 'Verified, but /sitemap.xml not found',
            recommendation: 'Sitemap.xml is missing or inaccessible. Submit a sitemap in Google Search Console for better indexing.',
            severity: 'minor',
        });
    } else {
        results.seo.push({
            test: 'gsc_check', label: 'Google Search Console Verification', pass: true,
            value: 'Verified, sitemap.xml accessible',
            recommendation: null, severity: null,
        });
    }

    // 16. Bing Webmaster Tools
    const bingMeta = document.querySelector('meta[name="msvalidate.01"]');
    const bingContent = bingMeta ? (bingMeta.getAttribute('content') || '').trim() : '';
    const hasBingVerification = bingContent.length > 0;

    // Check for bingbot-blocking directives (reuse robotsMeta from check 10)
    const bingRobotsContent = robotsMeta ? (robotsMeta.getAttribute('content') || '').toLowerCase() : '';
    const bingbotMeta = document.querySelector('meta[name="bingbot"]');
    const bingbotContent = bingbotMeta ? (bingbotMeta.getAttribute('content') || '').toLowerCase() : '';
    const bingbotBlocked = bingbotContent.includes('noindex') ||
        (bingRobotsContent.includes('noindex') && !bingbotContent);

    // Main Bing check
    if (bingbotBlocked) {
        results.seo.push({
            test: 'bing_webmaster_check', label: 'Bing Webmaster Tools', pass: false,
            value: bingbotContent.includes('noindex')
                ? 'Bingbot blocked by <meta name="bingbot"> noindex'
                : 'Bingbot blocked by <meta name="robots"> noindex',
            recommendation: 'Bing is blocked from indexing this page. Remove the noindex directive if this is unintended.',
            severity: 'critical',
        });
    } else if (!hasBingVerification) {
        results.seo.push({
            test: 'bing_webmaster_check', label: 'Bing Webmaster Tools', pass: false,
            value: '(verification tag missing)',
            recommendation: 'Add <meta name="msvalidate.01"> tag to verify site ownership in Bing Webmaster Tools',
            severity: 'major',
        });
    } else {
        results.seo.push({
            test: 'bing_webmaster_check', label: 'Bing Webmaster Tools', pass: true,
            value: 'Verified, no blocking directives',
            recommendation: null, severity: null,
        });
    }

    // Sub-warning: BingSiteAuth.xml missing
    if (hasBingVerification && !bingSiteAuthOk) {
        results.seo.push({
            test: 'bing_siteauth', label: 'Bing Site Auth File', pass: false,
            value: 'Verified, but /BingSiteAuth.xml not found',
            recommendation: 'Add a BingSiteAuth.xml file to the site root as an alternative verification method for Bing',
            severity: 'minor',
        });
    }

    // 20. Tracking Tags Overview
    const trackingTags = [];
    if (hasGtm) trackingTags.push('GTM' + (gtmIdList.length > 0 ? ' (' + gtmIdList[0] + ')' : ''));
    if (ga4Detected) trackingTags.push('GA4' + (ga4IdList.length > 0 ? ' (' + ga4IdList[0] + ')' : ''));
    if (hasGoogleAds) trackingTags.push('Google Ads (' + adsIdList[0] + ')');
    if (gtagInstalled) trackingTags.push('gtag.js');
    if (fbDetected) trackingTags.push('FB Pixel' + (fbIdList.length > 0 ? ' (' + fbIdList[0] + ')' : ''));

    const hasHotjar = allScripts.some(s => (s.src || '').includes('hotjar.com') || (s.textContent || '').includes('hotjar'));
    if (hasHotjar) trackingTags.push('Hotjar');
    const hasClarity = allScripts.some(s => (s.src || '').includes('clarity.ms'));
    if (hasClarity) trackingTags.push('Microsoft Clarity');
    const hasPinterest = allScripts.some(s => (s.textContent || '').includes('pintrk') || (s.src || '').includes('pinimg.com'));
    if (hasPinterest) trackingTags.push('Pinterest Tag');
    const hasTikTok = allScripts.some(s => (s.textContent || '').includes('ttq.load') || (s.src || '').includes('tiktok.com'));
    if (hasTikTok) trackingTags.push('TikTok Pixel');
    const hasSnapchat = allScripts.some(s => (s.textContent || '').includes('snaptr') || (s.src || '').includes('sc-static.net'));
    if (hasSnapchat) trackingTags.push('Snapchat Pixel');
    const hasLinkedIn = allScripts.some(s => (s.src || '').includes('snap.licdn.com') || (s.textContent || '').includes('_linkedin_partner_id'));
    if (hasLinkedIn) trackingTags.push('LinkedIn Insight');
    const hasTwitter = allScripts.some(s => (s.src || '').includes('static.ads-twitter.com') || (s.textContent || '').includes('twq('));
    if (hasTwitter) trackingTags.push('Twitter/X Pixel');
    const hasKlaviyo = allScripts.some(s => (s.src || '').includes('klaviyo.com'));
    if (hasKlaviyo) trackingTags.push('Klaviyo');

    results.seo.push({
        test: 'tracking_tags_overview', label: 'Tracking Tags Overview',
        pass: trackingTags.length > 0,
        value: trackingTags.length > 0
            ? trackingTags.length + ' tag(s): ' + trackingTags.join(' | ')
            : '(no tracking tags detected)',
        recommendation: trackingTags.length === 0
            ? 'No tracking tags found. Install Google Analytics and a marketing pixel at minimum for analytics.'
            : null,
        severity: trackingTags.length === 0 ? 'critical' : null,
    });

    // 21. Sitemap Status
    if (!sitemapOk) {
        results.seo.push({
            test: 'sitemap_status', label: 'Sitemap (sitemap.xml)', pass: false,
            value: '/sitemap.xml not found or inaccessible',
            recommendation: 'Create and submit a sitemap.xml to help search engines discover and index all your pages.',
            severity: 'major',
        });
    } else {
        let sitemapDetail = '/sitemap.xml is accessible — ' + sitemapUrls.length + ' URL(s) found';
        if (sitemapSubFiles.length > 0) {
            sitemapDetail += ' across ' + sitemapSubFiles.length + ' sub-sitemap(s)';
        }
        const urlsToShow = sitemapUrls.slice(0, 500);
        if (urlsToShow.length > 0) {
            sitemapDetail += '\\n' + urlsToShow.join('\\n');
        }
        if (sitemapUrls.length > 500) {
            sitemapDetail += '\\n... and ' + (sitemapUrls.length - 500) + ' more URLs';
        }
        results.seo.push({
            test: 'sitemap_status', label: 'Sitemap (sitemap.xml)', pass: true,
            value: sitemapDetail,
            recommendation: null, severity: null,
        });
    }

    // 22. robots.txt Status
    if (!robotsTxtOk) {
        results.seo.push({
            test: 'robots_txt_status', label: 'robots.txt', pass: false,
            value: '/robots.txt not found or inaccessible',
            recommendation: 'Create a robots.txt file to control search engine crawling and include a Sitemap directive.',
            severity: 'major',
        });
    } else {
        const rtLower = robotsTxtContent.toLowerCase();
        const hasSitemapDir = rtLower.includes('sitemap:');
        const robotsLines = robotsTxtContent.split('\\n');
        const hasDisallowAll = robotsLines.some(function(line) {
            var parts = line.trim().split(':');
            if (parts.length < 2) return false;
            return parts[0].trim().toLowerCase() === 'disallow' && parts.slice(1).join(':').trim() === '/';
        });

        if (hasDisallowAll) {
            results.seo.push({
                test: 'robots_txt_status', label: 'robots.txt', pass: false,
                value: 'WARNING: "Disallow: /" blocks all search engine crawling\\n' + robotsTxtContent.substring(0, 1000),
                recommendation: 'Your robots.txt blocks all crawling. Remove "Disallow: /" unless this is intentional for a staging site.',
                severity: 'critical',
            });
        } else {
            let robotsDetail = 'Accessible' + (hasSitemapDir ? ', includes Sitemap directive' : ', no Sitemap directive');
            robotsDetail += '\\n' + robotsTxtContent.substring(0, 1000);
            results.seo.push({
                test: 'robots_txt_status', label: 'robots.txt', pass: true,
                value: robotsDetail,
                recommendation: hasSitemapDir ? null : 'Add a "Sitemap:" directive to robots.txt pointing to your sitemap.xml for better discoverability.',
                severity: hasSitemapDir ? null : 'minor',
            });
        }
    }

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
