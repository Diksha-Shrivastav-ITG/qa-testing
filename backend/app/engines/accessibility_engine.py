from __future__ import annotations

import asyncio
from dataclasses import dataclass

AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js"

_BROWSER_ARGS = ["--disable-blink-features=AutomationControlled"]
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_WEBDRIVER_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)

# Manual WCAG checks that run as JS inside the browser
_MANUAL_CHECKS_JS = """
() => {
    const issues = [];

    // 1.1.1 — Images without alt text
    const missingAlt = document.querySelectorAll('img:not([alt])');
    if (missingAlt.length > 0)
        issues.push({ id: 'image-alt', impact: 'serious', wcag: '1.1.1',
            desc: `${missingAlt.length} image(s) are missing an alt attribute.`,
            help: 'Add descriptive alt text so screen readers can convey the image content.' });

    // 4.1.2 — Buttons without accessible name
    const badBtns = Array.from(document.querySelectorAll('button,[role="button"]')).filter(b => {
        const txt = (b.textContent||'').trim();
        const aria = b.getAttribute('aria-label')||'';
        const title = b.getAttribute('title')||'';
        const ariaLbl = b.getAttribute('aria-labelledby')||'';
        return !txt && !aria && !title && !ariaLbl;
    });
    if (badBtns.length > 0)
        issues.push({ id: 'button-name', impact: 'critical', wcag: '4.1.2',
            desc: `${badBtns.length} button(s) have no accessible name (no text, aria-label, or title).`,
            help: 'Add visible text or an aria-label attribute to every button.' });

    // 1.3.1 — Form inputs without associated labels
    const unlabelledInputs = Array.from(
        document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"])')
    ).filter(inp => {
        const id = inp.id;
        const ariaLabel = inp.getAttribute('aria-label')||'';
        const ariaLabelledBy = inp.getAttribute('aria-labelledby')||'';
        const label = id ? document.querySelector('label[for="'+id+'"]') : null;
        const wrappingLabel = inp.closest('label');
        return !label && !wrappingLabel && !ariaLabel && !ariaLabelledBy;
    });
    if (unlabelledInputs.length > 0)
        issues.push({ id: 'label', impact: 'serious', wcag: '1.3.1',
            desc: `${unlabelledInputs.length} form input(s) have no associated label.`,
            help: 'Use <label for="inputId"> or aria-label on every visible input.' });

    // 3.1.1 — HTML element missing lang attribute
    if (!document.documentElement.getAttribute('lang'))
        issues.push({ id: 'html-has-lang', impact: 'serious', wcag: '3.1.1',
            desc: 'The <html> element is missing a lang attribute.',
            help: 'Add lang="en" (or appropriate language code) to the <html> tag.' });

    // 2.4.2 — Missing page title
    if (!document.title || !document.title.trim())
        issues.push({ id: 'document-title', impact: 'serious', wcag: '2.4.2',
            desc: 'Page is missing a <title> element.',
            help: 'Add a descriptive <title> tag inside <head>.' });

    // 2.4.4 — Empty anchor links
    const emptyLinks = Array.from(document.querySelectorAll('a[href]')).filter(a => {
        const txt = (a.textContent||'').trim();
        const aria = a.getAttribute('aria-label')||'';
        const title = a.getAttribute('title')||'';
        const imgWithAlt = a.querySelector('img[alt]');
        return !txt && !aria && !title && !imgWithAlt;
    });
    if (emptyLinks.length > 0)
        issues.push({ id: 'link-name', impact: 'serious', wcag: '2.4.4',
            desc: `${emptyLinks.length} link(s) have no descriptive text, aria-label, or title.`,
            help: 'Provide descriptive link text or an aria-label so users understand the destination.' });

    // 1.3.1 — Heading hierarchy (skipped levels)
    const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'));
    let prevLevel = 0, skipped = 0;
    headings.forEach(h => {
        const lvl = parseInt(h.tagName[1]);
        if (prevLevel > 0 && lvl > prevLevel + 1) skipped++;
        prevLevel = lvl;
    });
    if (skipped > 0)
        issues.push({ id: 'heading-order', impact: 'moderate', wcag: '1.3.1',
            desc: `Heading hierarchy skips levels in ${skipped} place(s). Found: ${headings.map(h=>h.tagName).join(', ')}.`,
            help: 'Use headings in order: h1 → h2 → h3. Do not skip levels.' });

    // 1.1.1 — Images with empty alt (decorative OK, but flagged as info)
    const emptyAlt = Array.from(document.querySelectorAll('img[alt=""]')).filter(img => {
        const role = img.getAttribute('role')||'';
        return role !== 'presentation' && role !== 'none';
    });
    if (emptyAlt.length > 0)
        issues.push({ id: 'image-empty-alt', impact: 'minor', wcag: '1.1.1',
            desc: `${emptyAlt.length} image(s) have empty alt="" and are not marked as decorative (role="presentation").`,
            help: 'If the image is decorative, add role="presentation". If meaningful, provide descriptive alt text.' });

    // 3.2.2 — Links that open in new tab without warning
    const newTabLinks = Array.from(document.querySelectorAll('a[target="_blank"]')).filter(a => {
        const aria = (a.getAttribute('aria-label')||'').toLowerCase();
        const title = (a.getAttribute('title')||'').toLowerCase();
        return !aria.includes('new') && !aria.includes('tab') && !title.includes('new') && !title.includes('tab');
    });
    if (newTabLinks.length > 0)
        issues.push({ id: 'link-in-new-tab', impact: 'minor', wcag: '3.2.2',
            desc: `${newTabLinks.length} link(s) open in a new tab/window without warning the user.`,
            help: 'Add aria-label="... (opens in new tab)" or a visible icon to links with target="_blank".' });

    return issues;
}
"""


@dataclass
class AccessibilityResult:
    test_name: str
    severity: str  # "critical", "major", "minor"
    description: str
    wcag: str | None = None
    element: str | None = None
    help_text: str | None = None


class AccessibilityEngine:
    """Runs ADA/WCAG accessibility checks via axe-core + manual JS checks."""

    async def run_checks(
        self, page_url: str, password: str | None = None
    ) -> list[AccessibilityResult]:
        from playwright.async_api import async_playwright

        results: list[AccessibilityResult] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True, args=_BROWSER_ARGS
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=_USER_AGENT,
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            await context.add_init_script(_WEBDRIVER_SCRIPT)
            page = await context.new_page()

            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(page_url)
            base_store = f"{parsed.scheme}://{parsed.netloc}"

            # Handle password-protected stores
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

            # Set preview_theme_id cookie for unpublished theme previews
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

            # Try axe-core first
            axe_succeeded = False
            try:
                await page.add_script_tag(url=AXE_CDN)
                await asyncio.sleep(2)

                axe_raw = await page.evaluate(
                    """async () => {
                        return await new Promise((resolve) => {
                            if (typeof axe === 'undefined') { resolve({violations:[]}); return; }
                            axe.run(
                                { runOnly: { type:'tag', values:['wcag2a','wcag2aa','wcag21a','wcag21aa','best-practice'] } },
                                (err, r) => { if (err) resolve({violations:[]}); else resolve(r); }
                            );
                        });
                    }"""
                )

                _impact_to_sev = {
                    "critical": "critical",
                    "serious": "major",
                    "moderate": "minor",
                    "minor": "minor",
                }

                for v in axe_raw.get("violations", []):
                    impact = v.get("impact", "minor")
                    sev = _impact_to_sev.get(impact, "minor")
                    nodes = v.get("nodes", [])
                    count = len(nodes)
                    first_html = nodes[0].get("html", "")[:120] if nodes else ""
                    tags = ", ".join(v.get("tags", []))
                    desc = (
                        f"{v.get('description', v.get('id', 'Unknown issue'))} "
                        f"({count} element{'s' if count != 1 else ''} affected)"
                    )
                    results.append(
                        AccessibilityResult(
                            test_name=v.get("id", "unknown"),
                            severity=sev,
                            description=desc,
                            wcag=tags,
                            element=first_html or None,
                            help_text=v.get("help"),
                        )
                    )
                axe_succeeded = True
            except Exception:
                axe_succeeded = False

            # Always run manual checks too (they catch things axe might miss)
            try:
                manual_items = await page.evaluate(_MANUAL_CHECKS_JS)
                _i_to_sev = {
                    "critical": "critical",
                    "serious": "major",
                    "moderate": "minor",
                    "minor": "minor",
                }
                # Deduplicate with axe results by test_name
                existing_names = {r.test_name for r in results}
                for item in manual_items:
                    tid = item.get("id", "unknown")
                    if axe_succeeded and tid in existing_names:
                        continue
                    sev = _i_to_sev.get(item.get("impact", "minor"), "minor")
                    results.append(
                        AccessibilityResult(
                            test_name=tid,
                            severity=sev,
                            description=item.get("desc", ""),
                            wcag=item.get("wcag"),
                            help_text=item.get("help"),
                        )
                    )
            except Exception:
                pass

            await browser.close()

        return results
