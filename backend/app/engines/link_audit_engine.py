from __future__ import annotations

import asyncio
from dataclasses import dataclass

_BROWSER_ARGS = ["--disable-blink-features=AutomationControlled"]
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_WEBDRIVER_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)

_AUDIT_JS = """
() => {
    const hostname = window.location.hostname;
    const items = [];

    // ── Audit all <a> tags ──────────────────────────────────────────
    document.querySelectorAll('a').forEach(a => {
        const href = (a.getAttribute('href') || '').trim();
        const text = (a.textContent || '').replace(/\\s+/g, ' ').trim().substring(0, 120);
        const ariaLabel = a.getAttribute('aria-label') || '';
        const title = a.getAttribute('title') || '';
        const hasImgWithAlt = !!(a.querySelector('img[alt]'));
        const displayText = text || ariaLabel || title || (hasImgWithAlt ? '[image link]' : '');

        const isPlaceholder = !href || href === '#' || href.startsWith('javascript:');
        const isExternal = href.startsWith('http') && !href.includes(hostname);
        const isMailOrTel = href.startsWith('mailto:') || href.startsWith('tel:');

        let issue = null;
        if (isPlaceholder) {
            issue = 'missing_href';
        } else if (!displayText) {
            issue = 'empty_text';
        }

        // Determine destination label
        let destination = null;
        if (href.startsWith('http')) destination = href;
        else if (href.startsWith('mailto:')) destination = href;
        else if (href.startsWith('tel:')) destination = href;
        else if (href.startsWith('#')) destination = 'Same page anchor: ' + href;
        else if (href.startsWith('/')) destination = 'Internal: ' + href;
        else if (href && !isPlaceholder) destination = href;

        items.push({
            element_type: 'a',
            text: displayText || '[no text]',
            href: href || null,
            destination: destination,
            is_external: isExternal,
            is_mail_or_tel: isMailOrTel,
            has_href: !isPlaceholder,
            issue: issue,
            aria_label: ariaLabel || null,
        });
    });

    // ── Audit all <button> tags ──────────────────────────────────────
    document.querySelectorAll('button').forEach(btn => {
        const text = (btn.textContent || '').replace(/\\s+/g, ' ').trim().substring(0, 120);
        const ariaLabel = btn.getAttribute('aria-label') || '';
        const title = btn.getAttribute('title') || '';
        const type = btn.getAttribute('type') || 'submit';
        const hasIcon = !!(btn.querySelector('svg,img,i,.icon'));
        const displayText = text || ariaLabel || title || (hasIcon ? '[icon button]' : '');

        // Determine what this button does
        let destination = null;
        const form = btn.closest('form');
        if (type === 'submit' && form) {
            const action = form.getAttribute('action');
            destination = action ? 'Submits form to: ' + action : 'Submits form';
        } else if (type === 'reset') {
            destination = 'Resets form';
        } else {
            destination = 'JavaScript action';
        }

        let issue = null;
        if (!displayText) issue = 'no_accessible_name';

        items.push({
            element_type: 'button',
            text: displayText || '[no accessible name]',
            href: null,
            destination: destination,
            is_external: false,
            is_mail_or_tel: false,
            has_href: false,
            issue: issue,
            aria_label: ariaLabel || null,
        });
    });

    return items;
}
"""


@dataclass
class LinkAuditItem:
    element_type: str  # "a" or "button"
    text: str
    href: str | None
    destination: str | None
    is_external: bool
    has_href: bool
    issue: str | None  # "missing_href", "empty_text", "no_accessible_name", None
    aria_label: str | None = None
    is_mail_or_tel: bool = False


class LinkAuditEngine:
    """Audits all <a> and <button> elements on a Shopify page (Shopify only — not Framer)."""

    async def audit_page(
        self, page_url: str, password: str | None = None
    ) -> list[LinkAuditItem]:
        from playwright.async_api import async_playwright

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

            if password:
                try:
                    await page.goto(page_url, wait_until="networkidle")
                    await page.fill("input[type='password']", password)
                    await page.click("button[type='submit'], input[type='submit']")
                    await page.wait_for_load_state("networkidle")
                except Exception:
                    pass

            await page.goto(page_url, wait_until="networkidle")
            await asyncio.sleep(1)

            try:
                raw = await page.evaluate(_AUDIT_JS)
            except Exception:
                raw = []

            await browser.close()

        return [
            LinkAuditItem(
                element_type=item["element_type"],
                text=item["text"],
                href=item["href"],
                destination=item["destination"],
                is_external=item["is_external"],
                has_href=item["has_href"],
                issue=item["issue"],
                aria_label=item["aria_label"],
                is_mail_or_tel=item.get("is_mail_or_tel", False),
            )
            for item in raw
        ]
