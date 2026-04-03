from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.discovery_engine import DiscoveryEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_page(links: list[dict]) -> AsyncMock:
    """Return a mock Playwright page whose evaluate() resolves to *links* on the
    second call (the first call is the scroll JS whose return value is discarded).
    *links* should be a list of {path, name} dicts as produced by _LINK_JS.
    """
    page = AsyncMock()
    # First evaluate call = scroll JS (return value ignored); second = _LINK_JS
    page.evaluate = AsyncMock(side_effect=[None, links])
    return page


# ---------------------------------------------------------------------------
# test_discover_shopify_pages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_shopify_pages():
    """discover_pages should return filtered internal links as {path, name} dicts."""
    engine = DiscoveryEngine()

    raw_links = [
        {"path": "/", "name": "Home"},
        {"path": "/collections/all", "name": "Shop"},
        {"path": "/pages/about", "name": "About"},
        # These should be filtered out:
        {"path": "/cart", "name": "Cart"},
        {"path": "/account/login", "name": "Login"},
        {"path": "/search", "name": "Search"},
        {"path": "/policies/privacy-policy", "name": "Privacy"},
        {"path": "/password", "name": "Password"},
    ]

    mock_page = _make_mock_page(raw_links)

    with patch.object(engine, "_create_page", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_page

        pages = await engine.discover_pages("https://example.myshopify.com")

    # Only 3 links should survive filtering
    assert len(pages) == 3

    paths = [p["path"] for p in pages]
    assert "/" in paths
    assert "/collections/all" in paths
    assert "/pages/about" in paths

    # Filtered paths must not appear
    for blocked in ["/cart", "/account/login", "/search", "/policies/privacy-policy", "/password"]:
        assert blocked not in paths

    # Each item has both keys
    for page in pages:
        assert "path" in page
        assert "name" in page


@pytest.mark.asyncio
async def test_discover_shopify_pages_with_password():
    """discover_pages should pass the password argument to _create_page."""
    engine = DiscoveryEngine()

    mock_page = _make_mock_page([
        {"path": "/", "name": "Home"},
    ])

    with patch.object(engine, "_create_page", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_page

        await engine.discover_pages("https://example.myshopify.com", password="secret")

    mock_create.assert_awaited_once()
    _args, kwargs = mock_create.call_args
    assert kwargs.get("password") == "secret" or _args[1] == "secret"


@pytest.mark.asyncio
async def test_discover_source_pages():
    """discover_source_pages should return internal links as {path, name} dicts for any URL."""
    engine = DiscoveryEngine()

    raw_links = [
        {"path": "/", "name": "Home"},
        {"path": "/about", "name": "About"},
        {"path": "/contact", "name": "Contact"},
    ]

    mock_page = _make_mock_page(raw_links)

    with patch.object(engine, "_create_page", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_page

        pages = await engine.discover_source_pages("https://mysite.vercel.app")

    assert len(pages) == 3
    paths = [p["path"] for p in pages]
    assert "/" in paths
    assert "/about" in paths
    assert "/contact" in paths


# ---------------------------------------------------------------------------
# test_auto_map_pages_by_path
# ---------------------------------------------------------------------------


def test_auto_map_exact_path_match():
    """auto_map should prefer exact path matches over fuzzy matching."""
    engine = DiscoveryEngine()

    shopify_pages = [
        {"path": "/", "name": "Home"},
        {"path": "/collections/all", "name": "All Collections"},
        {"path": "/pages/about", "name": "About"},
    ]
    source_pages = [
        {"path": "/", "name": "Home"},
        {"path": "/collections/all", "name": "All Collections"},
        {"path": "/pages/about", "name": "About"},
    ]

    mapping = engine.auto_map(shopify_pages, source_pages)

    assert mapping["/"] == "/"
    assert mapping["/collections/all"] == "/collections/all"
    assert mapping["/pages/about"] == "/pages/about"


def test_auto_map_fuzzy_name_match():
    """auto_map should fuzzy-match by name when exact path match fails."""
    engine = DiscoveryEngine()

    shopify_pages = [
        {"path": "/pages/about", "name": "About"},
        {"path": "/pages/contact", "name": "Contact"},
    ]
    source_pages = [
        {"path": "/about-us", "name": "About Us"},
        {"path": "/contact-us", "name": "Contact Us"},
    ]

    mapping = engine.auto_map(shopify_pages, source_pages)

    # "About" should fuzzy-match "About Us"
    assert mapping["/pages/about"] == "/about-us"
    # "Contact" should fuzzy-match "Contact Us"
    assert mapping["/pages/contact"] == "/contact-us"


def test_auto_map_returns_only_shopify_paths_as_keys():
    """auto_map result keys should always be shopify paths."""
    engine = DiscoveryEngine()

    shopify_pages = [{"path": "/home", "name": "Home"}]
    source_pages = [{"path": "/", "name": "Home"}]

    mapping = engine.auto_map(shopify_pages, source_pages)

    assert list(mapping.keys()) == ["/home"]


def test_auto_map_no_match_below_threshold():
    """auto_map should not include an entry when similarity is below threshold."""
    engine = DiscoveryEngine()

    shopify_pages = [{"path": "/xyz-totally-different", "name": "XYZ Totally Different"}]
    source_pages = [{"path": "/aaa", "name": "AAA"}]

    mapping = engine.auto_map(shopify_pages, source_pages)

    # No match should be found; shopify path not in mapping (or mapped to None/empty)
    assert mapping.get("/xyz-totally-different") is None or "/xyz-totally-different" not in mapping


def test_auto_map_mixed_exact_and_fuzzy():
    """auto_map handles a mix of exact and fuzzy matches in one call."""
    engine = DiscoveryEngine()

    shopify_pages = [
        {"path": "/", "name": "Home"},
        {"path": "/pages/about", "name": "About"},
    ]
    source_pages = [
        {"path": "/", "name": "Home"},
        {"path": "/about-us", "name": "About Us"},
    ]

    mapping = engine.auto_map(shopify_pages, source_pages)

    assert mapping["/"] == "/"
    assert mapping["/pages/about"] == "/about-us"
