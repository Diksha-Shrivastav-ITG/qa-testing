from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class FigmaCaptureResult:
    page: str
    image_path: str
    frame_id: str
    width: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class FigmaCapture:
    BASE_URL = "https://api.figma.com/v1"

    def __init__(self, token: str, storage_path: str) -> None:
        self.token = token
        self.storage_path = storage_path
        self.headers = {"X-Figma-Token": token}

    async def list_frames(self, file_key: str) -> list[dict]:
        """Return a list of {id, name, width} dicts for all FRAME nodes in the file.

        Traverses document.children for CANVAS nodes and collects their direct
        FRAME children.
        """
        url = f"{self.BASE_URL}/files/{file_key}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()

        frames: list[dict] = []
        canvases = data.get("document", {}).get("children", [])
        for canvas in canvases:
            if canvas.get("type") != "CANVAS":
                continue
            for node in canvas.get("children", []):
                if node.get("type") != "FRAME":
                    continue
                bounding_box = node.get("absoluteBoundingBox") or {}
                width = int(bounding_box.get("width", 0))
                frames.append(
                    {
                        "id": node["id"],
                        "name": node["name"],
                        "width": width,
                    }
                )
        return frames

    async def capture_frames(
        self,
        file_key: str,
        frame_mapping: dict[str, str],
        run_dir: str,
        scale: int = 2,
    ) -> list[FigmaCaptureResult]:
        """Download rendered images for the given frame IDs and save them to disk.

        Args:
            file_key: Figma file key.
            frame_mapping: Mapping of {frame_id: page_name}.
            run_dir: Sub-directory inside storage_path for this run.
            scale: Image export scale factor (default 2 for @2x).

        Returns:
            A list of FigmaCaptureResult, one per frame.
        """
        node_ids = ",".join(frame_mapping.keys())
        images_url = f"{self.BASE_URL}/images/{file_key}"
        params = {"ids": node_ids, "scale": scale, "format": "png"}

        async with httpx.AsyncClient() as client:
            # Fetch image URLs from Figma
            images_response = await client.get(
                images_url, headers=self.headers, params=params
            )
            images_response.raise_for_status()
            images_data = images_response.json()
            image_urls: dict[str, str] = images_data.get("images", {})

            results: list[FigmaCaptureResult] = []

            for frame_id, page_name in frame_mapping.items():
                img_url = image_urls.get(frame_id, "")
                if not img_url:
                    results.append(
                        FigmaCaptureResult(
                            page=page_name,
                            image_path="",
                            frame_id=frame_id,
                        )
                    )
                    continue

                # Download image bytes
                img_response = await client.get(img_url)
                img_response.raise_for_status()
                image_bytes = img_response.content

                # Save to {storage_path}/{run_dir}/source/{page_name}/figma.png
                output_dir = os.path.join(
                    self.storage_path, run_dir, "source", page_name
                )
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, "figma.png")

                with open(output_path, "wb") as f:
                    f.write(image_bytes)

                results.append(
                    FigmaCaptureResult(
                        page=page_name,
                        image_path=output_path,
                        frame_id=frame_id,
                    )
                )

        return results
