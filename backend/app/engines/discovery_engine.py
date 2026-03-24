from __future__ import annotations

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
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        if password:
            await page.goto(url, wait_until="networkidle")
            try:
                await page.fill("input[type='password']", password)
                await page.click("button[type='submit'], input[type='submit']")
                await page.wait_for_load_state("networkidle")
            except Exception:
                pass

        await page.goto(url, wait_until="networkidle")
        return page

    # ------------------------------------------------------------------
    # JS snippet used to harvest internal links
    # ------------------------------------------------------------------

    _LINK_JS = """
    () => {
        const origin = window.location.origin;
        return Array.from(document.querySelectorAll('a[href]'))
            .map(a => ({ href: a.href, text: (a.innerText || a.textContent || '').trim() }))
            .filter(l => l.href.startsWith(origin));
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

        Returns a de-duplicated list of ``{path, name}`` dicts, excluding
        paths that match :data:`SHOPIFY_SKIP_PREFIXES`.
        """
        page = await self._create_page(shopify_url, password=password)
        raw_links: list[dict] = await page.evaluate(self._LINK_JS)

        seen: set[str] = set()
        results: list[dict] = []

        for link in raw_links:
            href = link.get("href", "")
            text = (link.get("text") or "").strip()

            parsed = urlparse(href)
            path = parsed.path or "/"

            # Skip unwanted Shopify paths
            if any(path.startswith(prefix) for prefix in SHOPIFY_SKIP_PREFIXES):
                continue

            if path in seen:
                continue
            seen.add(path)

            results.append({"path": path, "name": text})

        return results

    async def discover_framer_pages(self, framer_url: str) -> list[dict]:
        """Discover internal pages of a Framer site.

        Same approach as :meth:`discover_pages` but without Shopify-specific
        path filtering.
        """
        page = await self._create_page(framer_url)
        raw_links: list[dict] = await page.evaluate(self._LINK_JS)

        seen: set[str] = set()
        results: list[dict] = []

        for link in raw_links:
            href = link.get("href", "")
            text = (link.get("text") or "").strip()

            parsed = urlparse(href)
            path = parsed.path or "/"

            if path in seen:
                continue
            seen.add(path)

            results.append({"path": path, "name": text})

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
