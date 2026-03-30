# SEO Tools Checks Design Spec

**Date:** 2026-03-30
**Status:** Approved
**Approach:** Pure JavaScript Injection (Approach A)

---

## Overview

Add 4 new SEO checks to the existing SEO engine to verify the presence and proper functioning of Google Tag Manager, Google Analytics 4, Google Search Console, and Bing Webmaster Tools on Shopify storefronts.

All checks are added as JavaScript within the existing `_SEO_PERF_JS` block in `backend/app/engines/seo_engine.py`. Results appear inside the existing SEO Analysis section of the HTML report.

---

## New Checks

### Check 13: Google Tag Manager (GTM)

**Test key:** `gtm_check`
**Label:** Google Tag Manager (GTM)

**Detection logic:**
1. Check `window.google_tag_manager` object exists
2. Check `window.dataLayer` is an array
3. Look for `gtm.start` event in dataLayer entries (`dataLayer.find(e => e.event === 'gtm.start')`)
4. Check for noscript fallback: `<noscript>` containing `<iframe src="...googletagmanager.com...">` in DOM
5. Extract all GTM container IDs from script elements using regex `/GTM-[A-Z0-9]+/g`, flag if more than 1 unique ID

**Pass criteria:** GTM detected AND loading (gtm.start fires). Noscript fallback and duplicate container checks are separate sub-warnings — the main GTM check passes if GTM is active.

**Severity mapping:**
- `critical` — GTM not detected at all (no google_tag_manager object, no dataLayer)
- `major` — GTM script found but not firing (no gtm.start event in dataLayer)
- `minor` — GTM works but missing noscript fallback OR duplicate container IDs found

**Value display examples:**
- Pass: `"GTM-XXXXXX active, noscript present"`
- Fail (not found): `"(not installed)"`
- Fail (not firing): `"GTM-XXXXXX found but not firing"`
- Fail (duplicates): `"Multiple containers: GTM-AAA, GTM-BBB"`

---

### Check 14: Google Analytics 4 (GA4)

**Test key:** `ga4_check`
**Label:** Google Analytics 4 (GA4)

**Detection logic:**
1. Check for `window.gtag` function existence
2. Search script elements for URLs containing `gtag/js`
3. Extract `G-XXXXXXX` measurement ID pattern from all inline scripts on the page
4. Check `performance.getEntriesByType('resource')` for network requests to `google-analytics.com` or `googletagmanager.com/gtag`
5. Detect duplicate tracking: check if GA4 is loaded both as standalone script AND via GTM (multiple distinct `G-` IDs)

**Pass criteria:** GA4 detected AND actively sending data (network requests found). Duplicate tracking is a separate sub-check that produces an additional warning row if detected — the main GA4 check still passes.

**Severity mapping:**
- `critical` — No GA4 detected at all (no gtag function, no gtag/js scripts)
- `major` — GA4 script present but no data being sent (no matching network requests)
- `minor` — GA4 working but duplicate tracking detected (reported as additional warning, main check still passes)

**Value display examples:**
- Pass: `"GA4 active (G-XXXXXX), sending data"`
- Fail (not found): `"(not installed)"`
- Fail (not sending): `"GA4 script found (G-XXXXXX) but not sending data"`
- Fail (duplicate): `"Duplicate tracking: G-AAA, G-BBB"`

---

### Check 15: Google Search Console (GSC)

**Test key:** `gsc_check`
**Label:** Google Search Console Verification

**Detection logic:**
1. Check for `<meta name="google-site-verification" content="...">` — must exist with non-empty `content` attribute
2. Attempt `fetch('/sitemap.xml', { method: 'HEAD' })` — check if response is OK (status 200)

**Pass criteria:** Verification meta tag present with non-empty value AND sitemap.xml accessible.

**Severity mapping:**
- `major` — Verification meta tag missing or empty
- `minor` — Verification present but sitemap.xml not accessible (404 or error)

**Value display examples:**
- Pass: `"Verified, sitemap.xml accessible"`
- Fail (no tag): `"(verification tag missing)"`
- Fail (no sitemap): `"Verified, but /sitemap.xml not found"`

---

### Check 16: Bing Webmaster Tools

**Test key:** `bing_webmaster_check`
**Label:** Bing Webmaster Tools

**Detection logic:**
1. Check for `<meta name="msvalidate.01" content="...">` — must exist with non-empty `content` attribute
2. Attempt `fetch('/BingSiteAuth.xml', { method: 'HEAD' })` — check if accessible
3. Reuse the sitemap.xml result from GSC check (store in shared variable to avoid duplicate fetch)
4. Check `<meta name="robots">` content for `noindex`/`nofollow` directives that block all bots including Bing
5. Check `<meta name="bingbot">` for Bing-specific `noindex`/`nofollow` directives

**Pass criteria:** Verification tag present AND no blocking robot directives for Bing.

**Severity mapping:**
- `critical` — Bingbot explicitly blocked via `<meta name="bingbot" content="noindex">` or robots meta blocks all bots
- `major` — Verification meta tag (`msvalidate.01`) missing or empty
- `minor` — BingSiteAuth.xml not accessible

**Value display examples:**
- Pass: `"Verified, no blocking directives"`
- Fail (blocked): `"Bingbot blocked by meta robots noindex"`
- Fail (no tag): `"(verification tag missing)"`
- Fail (no auth file): `"Verified, but /BingSiteAuth.xml not found"`

---

## Technical Implementation

### JS Function Change

The `_SEO_PERF_JS` IIFE changes from synchronous to async:

```javascript
// Before
() => { ... return results; }

// After
async () => { ... return results; }
```

Playwright's `page.evaluate()` natively supports async functions — no Python-side changes needed for this.

### Shared Sitemap Fetch

The sitemap.xml fetch is performed once and its result shared between GSC (check 15) and Bing (check 16):

```javascript
let sitemapOk = false;
try {
    const resp = await fetch('/sitemap.xml', { method: 'HEAD' });
    sitemapOk = resp.ok;
} catch(e) {}
```

### BingSiteAuth Fetch

Separate fetch for Bing-specific auth file:

```javascript
let bingSiteAuthOk = false;
try {
    const resp = await fetch('/BingSiteAuth.xml', { method: 'HEAD' });
    bingSiteAuthOk = resp.ok;
} catch(e) {}
```

### Data Flow

No changes to data models or storage. The new checks produce `SeoResult` objects with the same shape as existing checks:

```
JS results.seo[] -> Python SeoResult dataclass -> seo_results DB table -> HTML report rows
```

---

## Files Changed

| File | Change Description |
|------|-------------------|
| `backend/app/engines/seo_engine.py` | Add checks 13-16 to `_SEO_PERF_JS`, convert IIFE to async |

**No changes needed to:**
- `backend/app/services/report_service.py` — already renders all SeoResult rows dynamically
- Database models/migrations — existing schema supports arbitrary test names
- Frontend — SEO results API already returns all checks dynamically

---

## Edge Cases

1. **CORS on fetch:** `/sitemap.xml` and `/BingSiteAuth.xml` are same-origin fetches on the Shopify store, so no CORS issues.
2. **Sites without any analytics:** All 4 checks fail gracefully with `(not installed)` — no errors thrown.
3. **GTM loading GA4:** If GA4 is loaded via GTM only, the GA4 check still passes because it detects network requests regardless of loading method.
4. **Password-protected stores:** The existing password bypass in `analyze_page()` runs before these checks, so cookies are set before evaluation.
5. **Fetch timeouts:** The `fetch()` calls for sitemap/BingSiteAuth use HEAD method for speed. If they hang, Playwright's overall page timeout handles cleanup.
