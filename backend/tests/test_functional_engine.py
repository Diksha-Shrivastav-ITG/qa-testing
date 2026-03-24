from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.functional_engine import FunctionalEngine, FunctionalResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_page(evaluate_side_effect=None, evaluate_return_value=None) -> AsyncMock:
    """Return a mock Playwright page."""
    page = AsyncMock()
    if evaluate_side_effect is not None:
        page.evaluate = AsyncMock(side_effect=evaluate_side_effect)
    elif evaluate_return_value is not None:
        page.evaluate = AsyncMock(return_value=evaluate_return_value)
    else:
        page.evaluate = AsyncMock(return_value=[])
    page.url = "https://example.myshopify.com/"
    return page


# ---------------------------------------------------------------------------
# test_check_links
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_links():
    """check_links should return 1 failure when one link returns 404."""
    engine = FunctionalEngine(storage_path="/tmp/test_storage")

    links = [
        "https://example.myshopify.com/good-page",
        "https://example.myshopify.com/missing-page",
    ]
    page = _make_mock_page(evaluate_return_value=links)

    # Mock httpx responses: first 200, second 404
    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200

    mock_response_404 = MagicMock()
    mock_response_404.status_code = 404

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(side_effect=[mock_response_200, mock_response_404])

    with patch("httpx.AsyncClient", return_value=mock_client):
        failures = await engine.check_links(page)

    assert len(failures) == 1
    assert isinstance(failures[0], FunctionalResult)
    assert failures[0].status == "fail"
    assert "404" in (failures[0].error_message or "") or "missing-page" in (failures[0].error_message or "")


@pytest.mark.asyncio
async def test_check_links_all_pass():
    """check_links should return empty list when all links return 200."""
    engine = FunctionalEngine(storage_path="/tmp/test_storage")

    links = ["https://example.myshopify.com/page1", "https://example.myshopify.com/page2"]
    page = _make_mock_page(evaluate_return_value=links)

    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(return_value=mock_response_200)

    with patch("httpx.AsyncClient", return_value=mock_client):
        failures = await engine.check_links(page)

    assert failures == []


# ---------------------------------------------------------------------------
# test_check_images
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_images():
    """check_images should return at least 1 failure for broken src or missing alt."""
    engine = FunctionalEngine(storage_path="/tmp/test_storage")

    images = [
        {"src": "", "alt": "Good image", "natural_width": 0},   # broken src (empty)
        {"src": "https://example.com/good.jpg", "alt": "", "natural_width": 100},  # missing alt
    ]
    page = _make_mock_page(evaluate_return_value=images)

    failures = await engine.check_images(page)

    assert len(failures) >= 1
    for f in failures:
        assert isinstance(f, FunctionalResult)
        assert f.status == "fail"


@pytest.mark.asyncio
async def test_check_images_all_pass():
    """check_images should return empty list when all images have src and alt."""
    engine = FunctionalEngine(storage_path="/tmp/test_storage")

    images = [
        {"src": "https://example.com/img1.jpg", "alt": "Image 1", "natural_width": 100},
        {"src": "https://example.com/img2.jpg", "alt": "Image 2", "natural_width": 200},
    ]
    page = _make_mock_page(evaluate_return_value=images)

    failures = await engine.check_images(page)

    assert failures == []


# ---------------------------------------------------------------------------
# test_run_shopify_flows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_shopify_flows_returns_functional_results():
    """run_shopify_flows should wrap FlowResult objects as FunctionalResult."""
    engine = FunctionalEngine(storage_path="/tmp/test_storage")

    page = _make_mock_page()

    from app.engines.flow_runner import FlowResult

    mock_pass_result = FlowResult(name="add_to_cart", status="pass")
    mock_fail_result = FlowResult(
        name="mobile_menu",
        status="fail",
        step_failed=1,
        error_message="Element not found",
    )

    with patch.object(engine.flow_runner, "run_flow", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = [mock_pass_result, mock_fail_result]

        results = await engine.run_shopify_flows(
            page,
            output_dir="/tmp/output",
            enabled_flows=["add_to_cart", "mobile_menu"],
        )

    assert len(results) == 2
    assert all(isinstance(r, FunctionalResult) for r in results)

    pass_result = next(r for r in results if r.test_name == "add_to_cart")
    fail_result = next(r for r in results if r.test_name == "mobile_menu")

    assert pass_result.status == "pass"
    assert fail_result.status == "fail"
    assert fail_result.error_message == "Element not found"
