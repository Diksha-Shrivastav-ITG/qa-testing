from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.flow_runner import FlowRunner, FlowResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_page() -> AsyncMock:
    """Return a mock Playwright page with common async methods."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.select_option = AsyncMock()
    page.hover = AsyncMock()
    page.evaluate = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.screenshot = AsyncMock()

    # locator chain: page.locator(sel) -> locator object
    mock_locator = AsyncMock()
    mock_locator.is_visible = AsyncMock(return_value=True)
    mock_locator.text_content = AsyncMock(return_value="some text")
    mock_locator.count = AsyncMock(return_value=1)
    page.locator = MagicMock(return_value=mock_locator)

    return page


# ---------------------------------------------------------------------------
# Individual action tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_navigate_action():
    """execute_step with navigate should call page.goto with base_url + value."""
    runner = FlowRunner(base_url="https://example.myshopify.com")
    page = _make_mock_page()

    step = {"action": "navigate", "value": "/collections/all"}
    await runner.execute_step(page, step)

    page.goto.assert_awaited_once_with("https://example.myshopify.com/collections/all")


@pytest.mark.asyncio
async def test_run_click_action():
    """execute_step with click should call page.click with the selector."""
    runner = FlowRunner(base_url="https://example.myshopify.com")
    page = _make_mock_page()

    step = {"action": "click", "selector": ".add-to-cart"}
    await runner.execute_step(page, step)

    page.click.assert_awaited_once_with(".add-to-cart")


@pytest.mark.asyncio
async def test_run_type_action():
    """execute_step with type should call page.fill with selector and value."""
    runner = FlowRunner(base_url="https://example.myshopify.com")
    page = _make_mock_page()

    step = {"action": "type", "selector": "input[name='q']", "value": "shirt"}
    await runner.execute_step(page, step)

    page.fill.assert_awaited_once_with("input[name='q']", "shirt")


@pytest.mark.asyncio
async def test_run_assert_visible():
    """execute_step with assert_visible should pass when locator.is_visible() returns True."""
    runner = FlowRunner(base_url="https://example.myshopify.com")
    page = _make_mock_page()
    page.locator.return_value.is_visible = AsyncMock(return_value=True)

    step = {"action": "assert_visible", "selector": ".cart-icon"}
    # Should not raise
    await runner.execute_step(page, step)

    page.locator.assert_called_with(".cart-icon")


@pytest.mark.asyncio
async def test_run_assert_visible_fails_when_hidden():
    """execute_step with assert_visible should raise AssertionError when element not visible."""
    runner = FlowRunner(base_url="https://example.myshopify.com")
    page = _make_mock_page()
    page.locator.return_value.is_visible = AsyncMock(return_value=False)

    step = {"action": "assert_visible", "selector": ".missing-element"}

    with pytest.raises(AssertionError):
        await runner.execute_step(page, step)


# ---------------------------------------------------------------------------
# Full flow test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_full_flow():
    """run_flow with a 3-step flow should succeed and return status='pass'."""
    runner = FlowRunner(base_url="https://example.myshopify.com")
    page = _make_mock_page()
    page.locator.return_value.is_visible = AsyncMock(return_value=True)

    flow = {
        "name": "test_flow",
        "steps": [
            {"action": "navigate", "value": "/"},
            {"action": "click", "selector": ".add-to-cart"},
            {"action": "assert_visible", "selector": ".cart-count"},
        ],
    }

    result = await runner.run_flow(page, flow, output_dir="/tmp/test_output")

    assert isinstance(result, FlowResult)
    assert result.status == "pass"
    assert result.name == "test_flow"
    assert result.step_failed is None
    assert result.error_message is None


@pytest.mark.asyncio
async def test_run_full_flow_fails_on_step_error():
    """run_flow should return status='fail' with step_failed set when a step raises."""
    runner = FlowRunner(base_url="https://example.myshopify.com")
    page = _make_mock_page()
    page.click = AsyncMock(side_effect=Exception("Element not found"))
    page.screenshot = AsyncMock()

    flow = {
        "name": "failing_flow",
        "steps": [
            {"action": "navigate", "value": "/"},
            {"action": "click", "selector": ".nonexistent"},
        ],
    }

    result = await runner.run_flow(page, flow, output_dir="/tmp/test_output")

    assert result.status == "fail"
    assert result.name == "failing_flow"
    assert result.step_failed is not None
    assert result.error_message is not None
