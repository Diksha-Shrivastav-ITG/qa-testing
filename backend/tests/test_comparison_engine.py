from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from app.engines.comparison_engine import (
    ComparisonEngine,
    ComparisonResult,
    PIXEL_THRESHOLD,
    VISUAL_WEIGHT,
    DOM_WEIGHT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine(tmp_path):
    """Return a ComparisonEngine instance with a dummy API key."""
    return ComparisonEngine(storage_path=str(tmp_path))


def _make_solid_image(path: str, color: tuple[int, int, int], size: tuple[int, int] = (200, 200)) -> str:
    """Create a solid-color PNG image at the given path and return the path."""
    img = Image.new("RGB", size, color)
    img.save(path)
    return path


# ---------------------------------------------------------------------------
# compute_visual_diff tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_visual_diff_identical_images(engine, tmp_path):
    """Two identical red images should produce a visual score close to 1.0 (0% mismatch)."""
    img1 = _make_solid_image(str(tmp_path / "red1.png"), (255, 0, 0))
    img2 = _make_solid_image(str(tmp_path / "red2.png"), (255, 0, 0))

    score_norm, mismatch_pct, diff_path, heatmap_path = engine.compute_visual_diff(
        img1, img2, str(tmp_path)
    )

    assert score_norm > 0.99, f"Expected visual score > 0.99 for identical images, got {score_norm}"
    assert mismatch_pct < 1.0, f"Expected mismatch < 1% for identical images, got {mismatch_pct}"
    assert os.path.exists(diff_path), "Diff image should be saved"
    assert os.path.exists(heatmap_path), "Heatmap image should be saved"


@pytest.mark.asyncio
async def test_visual_diff_different_images(engine, tmp_path):
    """A red image vs a blue image should produce high mismatch (low visual score)."""
    img1 = _make_solid_image(str(tmp_path / "red.png"), (255, 0, 0))
    img2 = _make_solid_image(str(tmp_path / "blue.png"), (0, 0, 255))

    score_norm, mismatch_pct, diff_path, heatmap_path = engine.compute_visual_diff(
        img1, img2, str(tmp_path)
    )

    assert score_norm < 0.5, f"Expected visual score < 0.5 for red vs blue, got {score_norm}"
    assert mismatch_pct > 50.0, f"Expected mismatch > 50% for red vs blue, got {mismatch_pct}"
    assert os.path.exists(diff_path), "Diff image should be saved"
    assert os.path.exists(heatmap_path), "Heatmap image should be saved"


# ---------------------------------------------------------------------------
# compare (reference mode) tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compare_returns_ai_issues(engine, tmp_path):
    """compare() should run pixelmatch diff and call analyze_with_groq for issues."""
    img1 = _make_solid_image(str(tmp_path / "design.png"), (255, 0, 0))
    img2 = _make_solid_image(str(tmp_path / "shopify.png"), (0, 0, 255))

    mock_issues = [
        {
            "type": "color",
            "severity": "high",
            "element": "background",
            "description": "Background color differs significantly",
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
    assert result.ai_status == "completed"
    assert result.page == "home"
    assert result.breakpoint == 1440
    assert result.ssim_score < 0.5  # red vs blue should be low
    assert result.mismatch_pct > 50.0


@pytest.mark.asyncio
async def test_compare_identical_images_no_issues(engine, tmp_path):
    """compare() on identical images should still call AI analysis and return a high visual score."""
    img1 = _make_solid_image(str(tmp_path / "design.png"), (255, 0, 0))
    img2 = _make_solid_image(str(tmp_path / "shopify.png"), (255, 0, 0))

    with patch.object(engine, "analyze_with_groq", new=AsyncMock(return_value={"issues": []})) as mock_ai:
        result = await engine.compare(
            design_path=img1,
            shopify_path=img2,
            output_dir=str(tmp_path),
            page="product",
            breakpoint=768,
        )

    mock_ai.assert_called_once()
    assert result.ai_issues == []
    assert result.ssim_score > 0.99
    assert result.mismatch_pct < 1.0


# ---------------------------------------------------------------------------
# Hybrid score tests
# ---------------------------------------------------------------------------


def test_hybrid_score_no_dom():
    """Without DOM score, hybrid = visual_pct."""
    score = ComparisonEngine.compute_hybrid_score(0.85, None)
    assert score == pytest.approx(85.0, abs=0.1)


def test_hybrid_score_with_dom():
    """With DOM score, hybrid uses 80/20 weighting."""
    score = ComparisonEngine.compute_hybrid_score(0.80, 60.0)
    expected = 80.0 * VISUAL_WEIGHT + 60.0 * DOM_WEIGHT
    assert score == pytest.approx(expected, abs=0.1)


def test_hybrid_score_weights_sum_to_one():
    assert VISUAL_WEIGHT + DOM_WEIGHT == pytest.approx(1.0, abs=1e-9)
