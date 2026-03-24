from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.figma_capture import FigmaCapture, FigmaCaptureResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_TOKEN = "figma-token-abc"
FAKE_FILE_KEY = "file123"
FAKE_RUN_DIR = "run_001"
STORAGE_PATH = "/tmp/figma_test"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_frame_images():
    """capture_frames should return one FigmaCaptureResult per frame mapping."""
    engine = FigmaCapture(token=FAKE_TOKEN, storage_path=STORAGE_PATH)

    frame_mapping = {
        "frame-id-1": "home",
        "frame-id-2": "product",
    }

    # Build the mock response for the /images endpoint
    images_response = MagicMock()
    images_response.raise_for_status = MagicMock()
    images_response.json.return_value = {
        "images": {
            "frame-id-1": "https://cdn.figma.com/img/frame1.png",
            "frame-id-2": "https://cdn.figma.com/img/frame2.png",
        }
    }

    # Build a mock response for downloading the image bytes
    image_bytes_response = MagicMock()
    image_bytes_response.raise_for_status = MagicMock()
    image_bytes_response.content = b"\x89PNG\r\n"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            images_response,          # first call: fetch image URLs
            image_bytes_response,     # second call: download frame 1
            image_bytes_response,     # third call: download frame 2
        ]
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.engines.figma_capture.httpx.AsyncClient", return_value=mock_client):
        with patch("builtins.open", MagicMock()):
            with patch("os.makedirs", MagicMock()):
                results = await engine.capture_frames(
                    file_key=FAKE_FILE_KEY,
                    frame_mapping=frame_mapping,
                    run_dir=FAKE_RUN_DIR,
                )

    assert len(results) == 2
    assert all(isinstance(r, FigmaCaptureResult) for r in results)
    pages = {r.page for r in results}
    assert pages == {"home", "product"}


@pytest.mark.asyncio
async def test_fetch_frame_list():
    """list_frames should return one dict per FRAME node inside CANVAS nodes."""
    engine = FigmaCapture(token=FAKE_TOKEN, storage_path=STORAGE_PATH)

    # Simulate GET /files/{file_key} response with 2 frames inside 1 canvas
    files_response = MagicMock()
    files_response.raise_for_status = MagicMock()
    files_response.json.return_value = {
        "document": {
            "children": [
                {
                    "type": "CANVAS",
                    "children": [
                        {"id": "frame-id-1", "name": "Home", "type": "FRAME",
                         "absoluteBoundingBox": {"width": 1440, "height": 900}},
                        {"id": "frame-id-2", "name": "Product", "type": "FRAME",
                         "absoluteBoundingBox": {"width": 1280, "height": 900}},
                    ],
                }
            ]
        }
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=files_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.engines.figma_capture.httpx.AsyncClient", return_value=mock_client):
        frames = await engine.list_frames(file_key=FAKE_FILE_KEY)

    assert len(frames) == 2

    names = {f["name"] for f in frames}
    assert names == {"Home", "Product"}

    widths = {f["name"]: f["width"] for f in frames}
    assert widths["Home"] == 1440
    assert widths["Product"] == 1280

    ids = {f["id"] for f in frames}
    assert ids == {"frame-id-1", "frame-id-2"}
