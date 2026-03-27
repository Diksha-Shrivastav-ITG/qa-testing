from __future__ import annotations

import asyncio
import difflib
from urllib.parse import urlparse

from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# Paths to skip when discovering Shopify pages
# ---------------------------------------------------------------------------

SHOPIFY_SKIP_PREFIXES = (
    "/account",
    "/cart",
    "/search",
    "/policies",
    "/password",
)


class DiscoveryEngine:
    """Auto-discovers pages from a Shopify or Framer site and maps them together."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _create_page(self, url: str, password: str | None = None):
        """Launch Playwright, navigate to *url*, and return the page object.

        The caller is responsible for closing the browser after use.
        For testing purposes this method is kept minimal so it can be
        patched with AsyncMock easily.
        """
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        base_store = f"{parsed.scheme}://{parsed.netloc}"

        if password:
            try:
                await page.goto(f"{base_store}/password", wait_until="networkidle", timeout=20000)
                pwd_input = page.locator("input[type='password']")
                if await pwd_input.is_visible(timeout=3000):
                    await pwd_input.fill(password)
                    await page.locator("button[type='submit'], input[type='submit']").click()
                    await page.wait_for_load_state("networkidle")
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

        await page.goto(url, wait_until="networkidle", timeout=15000)
        return page

    # ------------------------------------------------------------------
    # JS snippet used to harvest internal links
    # Collects: <a href>, data-href/data-url attributes, onclick patterns
    # Deduplication by path is done inside JS — returns [{path, name}]
    # ------------------------------------------------------------------

    _LINK_JS = """
    () => {
        const origin = window.location.origin;
        const seen = new Set();
        const results = [];

        function add(href, text) {
            if (!href) return;
            try {
                // Resolve relative URLs
                const url = new URL(href, origin);
                if (url.origin !== origin) return;
                // Normalize: strip trailing slash (except root), ignore query/hash
                const path = url.pathname.replace(/\\/$/, '') || '/';
                if (seen.has(path)) return;
                seen.add(path);
                results.push({ path, name: (text || '').trim().substring(0, 80) });
            } catch (e) {}
        }

        // 1. All <a href> links — covers nav, product cards, banners, footer
        document.querySelectorAll('a[href]').forEach(a => {
            add(a.href, a.innerText || a.textContent || '');
        });

        // 2. data-href / data-url — common in Shopify section blocks and app embeds
        document.querySelectorAll('[data-href],[data-url]').forEach(el => {
            const href = el.getAttribute('data-href') || el.getAttribute('data-url');
            add(href, el.innerText || el.textContent || '');
        });

        // 3. onclick="window.location='...'" or "location.href='...'" — buttons, divs
        document.querySelectorAll('[onclick]').forEach(el => {
            const oc = el.getAttribute('onclick') || '';
            const m = oc.match(/(?:window\\.location(?:\\.href)?\\s*=\\s*|location\\.href\\s*=\\s*)['"]([^'"]+)['"]/);
            if (m) add(m[1], el.innerText || el.textContent || '');
        });

        // 4. <form action="..."> — search forms, login redirects
        document.querySelectorAll('form[action]').forEach(f => {
            add(f.getAttribute('action'), f.getAttribute('aria-label') || '');
        });

        return results;
    }
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def discover_pages(
        self,
        shopify_url: str,
        password: str | None = None,
    ) -> list[dict]:
        """Discover internal pages of a Shopify store.

        Scrolls the full homepage to trigger lazy-loaded content (product grids,
        section blocks, etc.) before collecting links.

        Returns a de-duplicated list of ``{path, name}`` dicts, excluding
        paths that match :data:`SHOPIFY_SKIP_PREFIXES`.
        """
        page = await self._create_page(shopify_url, password=password)

        # Scroll the full page to trigger lazy-loaded product cards and section blocks
        try:
            await page.evaluate("""
                async () => {
                    await new Promise(resolve => {
                        let scrolled = 0;
                        const step = 500;
                        const timer = setInterval(() => {
                            window.scrollBy(0, step);
                            scrolled += step;
                            if (scrolled >= document.body.scrollHeight) {
                                clearInterval(timer);
                                window.scrollTo(0, 0);
                                resolve();
                            }
                        }, 80);
                    });
                }
            """)
            await asyncio.sleep(1)
        except Exception:
            pass

        # _LINK_JS returns [{path, name}] already deduplicated by path
        raw_links: list[dict] = await page.evaluate(self._LINK_JS)

        results: list[dict] = []
        for link in raw_links:
            path = link.get("path", "") or "/"
            name = (link.get("name") or "").strip()

            # Skip unwanted Shopify paths
            if any(path.startswith(prefix) for prefix in SHOPIFY_SKIP_PREFIXES):
                continue

            results.append({"path": path, "name": name})

        return results

    async def discover_framer_pages(self, framer_url: str) -> list[dict]:
        """Discover internal pages of a Framer site.

        Same approach as :meth:`discover_pages` but without Shopify-specific
        path filtering.
        """
        page = await self._create_page(framer_url)

        try:
            await page.evaluate("""
                async () => {
                    await new Promise(resolve => {
                        let scrolled = 0;
                        const step = 500;
                        const timer = setInterval(() => {
                            window.scrollBy(0, step);
                            scrolled += step;
                            if (scrolled >= document.body.scrollHeight) {
                                clearInterval(timer);
                                window.scrollTo(0, 0);
                                resolve();
                            }
                        }, 80);
                    });
                }
            """)
            await asyncio.sleep(1)
        except Exception:
            pass

        # _LINK_JS returns [{path, name}] already deduplicated by path
        raw_links: list[dict] = await page.evaluate(self._LINK_JS)

        results: list[dict] = []
        for link in raw_links:
            path = link.get("path", "") or "/"
            name = (link.get("name") or "").strip()
            results.append({"path": path, "name": name})

        return results

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def auto_map(
        self,
        shopify_pages: list[dict],
        source_pages: list[dict],
    ) -> dict[str, str]:
        """Map Shopify paths to source (e.g. Framer) paths.

        Strategy:
        1. Exact path match.
        2. Fuzzy match by name/path similarity using
           :class:`difflib.SequenceMatcher` (threshold ≥ 0.5).

        Returns a ``{shopify_path: source_path}`` dict.  Shopify paths with
        no match above the threshold are omitted from the result.
        """
        source_path_set = {p["path"] for p in source_pages}
        source_by_path = {p["path"]: p for p in source_pages}

        mapping: dict[str, str] = {}

        for sp in shopify_pages:
            s_path = sp["path"]
            s_name = (sp.get("name") or "").strip().lower()

            # 1. Exact path match
            if s_path in source_path_set:
                mapping[s_path] = s_path
                continue

            # 2. Fuzzy match — score each source page and pick the best
            best_score = 0.0
            best_source_path: str | None = None

            for tp in source_pages:
                t_path = tp["path"]
                t_name = (tp.get("name") or "").strip().lower()

                # Compare by name
                name_score = difflib.SequenceMatcher(None, s_name, t_name).ratio()
                # Compare by path tokens (strip leading slashes, replace - with space)
                s_path_tok = s_path.lstrip("/").replace("-", " ").replace("/", " ")
                t_path_tok = t_path.lstrip("/").replace("-", " ").replace("/", " ")
                path_score = difflib.SequenceMatcher(None, s_path_tok, t_path_tok).ratio()

                score = max(name_score, path_score)

                if score > best_score:
                    best_score = score
                    best_source_path = t_path

            if best_score >= 0.5 and best_source_path is not None:
                mapping[s_path] = best_source_path

        return mapping
