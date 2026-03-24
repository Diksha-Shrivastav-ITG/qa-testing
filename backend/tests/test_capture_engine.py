from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.engines.capture_engine import CaptureEngine, CaptureResult

ALL_BREAKPOINTS = [320, 375, 414, 768, 1024, 1280, 1440]


@pytest.mark.asyncio
async def test_capture_returns_results_for_all_breakpoints():
    """Capture should return one CaptureResult per breakpoint."""
    engine = CaptureEngine(storage_path="/tmp/screenshots")

    with patch.object(engine, "_take_screenshot", new_callable=AsyncMock) as mock_shot:
        mock_shot.return_value = "/fake/path.png"

        results = await engine.capture_page(
            url="https://example.myshopify.com",
            page_name="home",
            run_dir="run_001",
            source="live",
            breakpoints=ALL_BREAKPOINTS,
        )

    assert len(results) == 7
    result_breakpoints = [r.breakpoint for r in results]
    assert result_breakpoints == ALL_BREAKPOINTS
    for r in results:
        assert r.status == "success"
        assert r.image_path == "/fake/path.png"


@pytest.mark.asyncio
async def test_capture_handles_password_protected_store():
    """Password should be forwarded to _take_screenshot."""
    engine = CaptureEngine(storage_path="/tmp/screenshots")

    with patch.object(engine, "_take_screenshot", new_callable=AsyncMock) as mock_shot:
        mock_shot.return_value = "/fake/path.png"

        await engine.capture_page(
            url="https://example.myshopify.com",
            page_name="home",
            run_dir="run_001",
            source="live",
            breakpoints=[375],
            password="dev123",
        )

    # Verify password was passed in the call args
    _args, kwargs = mock_shot.call_args
    assert kwargs.get("password") == "dev123"


@pytest.mark.asyncio
async def test_capture_retries_on_failure():
    """On first call failure, engine retries once and returns a success result."""
    engine = CaptureEngine(storage_path="/tmp/screenshots")

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("network error")
        return "/fake/retry.png"

    with patch.object(engine, "_take_screenshot", side_effect=side_effect):
        results = await engine.capture_page(
            url="https://example.myshopify.com",
            page_name="home",
            run_dir="run_001",
            source="live",
            breakpoints=[375],
        )

    assert len(results) == 1
    assert call_count == 2
    assert results[0].status == "success"
    assert results[0].image_path == "/fake/retry.png"
