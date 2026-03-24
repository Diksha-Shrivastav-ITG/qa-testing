from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from PIL import Image

from app.engines.comparison_engine import ComparisonEngine, ComparisonResult, SSIM_THRESHOLD


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine(tmp_path):
    """Return a ComparisonEngine instance with a dummy API key."""
    return ComparisonEngine(groq_api_key="test-key", storage_path=str(tmp_path))


def _make_solid_image(path: str, color: tuple[int, int, int], size: tuple[int, int] = (200, 200)) -> str:
    """Create a solid-color PNG image at the given path and return the path."""
    img = Image.fromarray(
        np.full((size[1], size[0], 3), color, dtype=np.uint8),
        mode="RGB",
    )
    img.save(path)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ssim_identical_images(engine, tmp_path):
    """Two identical red images should produce an SSIM score > 0.99."""
    img1 = _make_solid_image(str(tmp_path / "red1.png"), (255, 0, 0))
    img2 = _make_solid_image(str(tmp_path / "red2.png"), (255, 0, 0))

    score, diff_path, heatmap_path = engine.compute_ssim(img1, img2, str(tmp_path))

    assert score > 0.99, f"Expected SSIM > 0.99 for identical images, got {score}"
    assert os.path.exists(diff_path), "Diff image should be saved"
    assert os.path.exists(heatmap_path), "Heatmap image should be saved"


@pytest.mark.asyncio
async def test_ssim_different_images(engine, tmp_path):
    """A red image vs a blue image should produce an SSIM score < 0.5."""
    img1 = _make_solid_image(str(tmp_path / "red.png"), (255, 0, 0))
    img2 = _make_solid_image(str(tmp_path / "blue.png"), (0, 0, 255))

    score, diff_path, heatmap_path = engine.compute_ssim(img1, img2, str(tmp_path))

    assert score < 0.5, f"Expected SSIM < 0.5 for red vs blue images, got {score}"
    assert os.path.exists(diff_path), "Diff image should be saved"
    assert os.path.exists(heatmap_path), "Heatmap image should be saved"


@pytest.mark.asyncio
async def test_ai_analysis_called_when_ssim_low(engine, tmp_path):
    """When SSIM is below threshold, analyze_with_groq should be called and issues returned."""
    img1 = _make_solid_image(str(tmp_path / "red.png"), (255, 0, 0))
    img2 = _make_solid_image(str(tmp_path / "blue.png"), (0, 0, 255))

    mock_issues = [
        {
            "type": "color_mismatch",
            "severity": "high",
            "element": "background",
            "description": "Background color differs significantly",
            "location": {"x": 0, "y": 0},
            "selector": "body",
            "suggestion": "Update background to match design",
        }
    ]

    with patch.object(engine, "analyze_with_groq", new=AsyncMock(return_value={"issues": mock_issues})) as mock_ai:
        result = await engine.compare(
            design_path=img1,
            shopify_path=img2,
            output_dir=str(tmp_path),
            page="home",
            breakpoint=1440,
        )

    mock_ai.assert_called_once()
    assert result.ai_issues == mock_issues, "AI issues should be populated from Groq response"
    assert result.ssim_score < SSIM_THRESHOLD
    assert result.ai_status == "completed"
    assert result.page == "home"
    assert result.breakpoint == 1440


@pytest.mark.asyncio
async def test_ai_analysis_skipped_when_ssim_high(engine, tmp_path):
    """When SSIM is at or above threshold, analyze_with_groq should NOT be called."""
    img1 = _make_solid_image(str(tmp_path / "red1.png"), (255, 0, 0))
    img2 = _make_solid_image(str(tmp_path / "red2.png"), (255, 0, 0))

    with patch.object(engine, "analyze_with_groq", new=AsyncMock()) as mock_ai:
        result = await engine.compare(
            design_path=img1,
            shopify_path=img2,
            output_dir=str(tmp_path),
            page="product",
            breakpoint=768,
        )

    mock_ai.assert_not_called()
    assert result.ai_issues == [], "AI issues should be empty when SSIM is high"
    assert result.ssim_score >= SSIM_THRESHOLD
    assert result.page == "product"
    assert result.breakpoint == 768
