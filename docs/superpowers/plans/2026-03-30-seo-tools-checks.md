# SEO Tools Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4 deep SEO checks (GTM, GA4, GSC, Bing Webmaster) to the existing SEO engine as JavaScript injections, with sub-warnings for misconfigurations.

**Architecture:** Extend the `_SEO_PERF_JS` JavaScript block in `seo_engine.py` with 4 new check sections. Convert the IIFE from sync to async to support `fetch()` calls for sitemap/BingSiteAuth verification. No other files change — the report and database already render all SEO results dynamically.

**Tech Stack:** Playwright (page.evaluate), vanilla JavaScript (DOM APIs, fetch, performance API)

**Spec:** `docs/superpowers/specs/2026-03-30-seo-tools-checks-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/engines/seo_engine.py` | Modify (lines 22-272) | Add checks 13-16 to `_SEO_PERF_JS`, convert IIFE to async |

No new files. No other files modified.

---

### Task 1: Convert IIFE to Async

**Files:**
- Modify: `backend/app/engines/seo_engine.py:23` (opening of JS string)

- [ ] **Step 1: Change the JS function signature from sync to async**

In `backend/app/engines/seo_engine.py`, change line 23 from:

```python
_SEO_PERF_JS = """
() => {
```

to:

```python
_SEO_PERF_JS = """
async () => {
```

This is a one-character change. Playwright's `page.evaluate()` natively supports async functions — no Python changes needed.

- [ ] **Step 2: Verify no Python-side changes are needed**

Confirm that `page.evaluate(_SEO_PERF_JS)` on line 356 already uses `await`, which it does:
```python
raw = await page.evaluate(_SEO_PERF_JS)
```

No changes needed on the Python side.

- [ ] **Step 3: Commit**

```bash
git add backend/app/engines/seo_engine.py
git commit -m "refactor: convert SEO JS IIFE to async for fetch support"
```

---

### Task 2: Add GTM Check (Check 13)

**Files:**
- Modify: `backend/app/engines/seo_engine.py` (insert after check 12 HTTPS block, before performance section)

- [ ] **Step 1: Add GTM check JavaScript**

Insert the following after the HTTPS check (after line 189, before the `// ===================== PERFORMANCE CHECKS =====================` comment):

```javascript
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/engines/seo_engine.py
git commit -m "feat: add GTM deep check with noscript and duplicate detection"
```

---

### Task 3: Add GA4 Check (Check 14)

**Files:**
- Modify: `backend/app/engines/seo_engine.py` (insert after GTM check block)

- [ ] **Step 1: Add GA4 check JavaScript**

Insert immediately after the GTM duplicate containers block:

```javascript
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/engines/seo_engine.py
git commit -m "feat: add GA4 deep check with data sending and duplicate detection"
```

---

### Task 4: Add GSC Check (Check 15)

**Files:**
- Modify: `backend/app/engines/seo_engine.py` (insert after GA4 check block)

- [ ] **Step 1: Add GSC check JavaScript**

Insert immediately after the GA4 duplicate tracking block. The async fetch block goes here — right before the GSC check — so `sitemapOk` and `bingSiteAuthOk` are available for both GSC and Bing checks.

```javascript
    // ===================== ASYNC RESOURCE CHECKS =====================

    let sitemapOk = false;
    try {
        const sitemapResp = await fetch('/sitemap.xml', { method: 'HEAD' });
        sitemapOk = sitemapResp.ok;
    } catch(e) {}

    let bingSiteAuthOk = false;
    try {
        const bingAuthResp = await fetch('/BingSiteAuth.xml', { method: 'HEAD' });
        bingSiteAuthOk = bingAuthResp.ok;
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/engines/seo_engine.py
git commit -m "feat: add Google Search Console verification and sitemap check"
```

---

### Task 5: Add Bing Webmaster Check (Check 16)

**Files:**
- Modify: `backend/app/engines/seo_engine.py` (insert after GSC check block)

- [ ] **Step 1: Add Bing Webmaster check JavaScript**

Insert immediately after the GSC check block:

```javascript
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/engines/seo_engine.py
git commit -m "feat: add Bing Webmaster Tools verification and bingbot directive check"
```

---

### Task 6: Final Integration Verification

**Files:**
- Read: `backend/app/engines/seo_engine.py` (full file)

- [ ] **Step 1: Read the full file and verify structure**

Read `backend/app/engines/seo_engine.py` end-to-end and verify:
1. The IIFE is `async () => {`
2. Checks 1-12 are unchanged
3. Checks 13-16 appear after check 12 and before the performance section
4. The async fetch block (sitemap + BingSiteAuth) appears before checks 15-16
5. The `return results;` is still at the end
6. No syntax errors in the JS string

- [ ] **Step 2: Verify the report service needs no changes**

Read `backend/app/services/report_service.py` lines 482-527 (SEO report section) and confirm it dynamically renders all `SeoResult` rows without hardcoded test names. The new checks should appear automatically.

- [ ] **Step 3: Final commit if any fixups needed**

```bash
git add backend/app/engines/seo_engine.py
git commit -m "fix: final integration cleanup for SEO tools checks"
```

Only commit if changes were made in this step.
