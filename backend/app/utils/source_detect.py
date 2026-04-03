from __future__ import annotations

import re

from app.models.project import SourceType

_FIGMA_URL_PATTERN = re.compile(r"https?://(?:www\.)?figma\.com/")


def detect_source_type(url: str | None) -> SourceType:
    """Auto-detect the source type from a URL.

    Returns SourceType.figma for Figma URLs, SourceType.website for any
    other valid URL, or SourceType.none if the URL is empty/missing.
    """
    if not url or not url.strip():
        return SourceType.none
    if _FIGMA_URL_PATTERN.match(url):
        return SourceType.figma
    return SourceType.website


def extract_figma_file_key(url: str | None) -> str | None:
    """Extract the Figma file key from a Figma URL.

    Supports:
      - https://figma.com/design/FILE_KEY/...
      - https://figma.com/file/FILE_KEY/...
      - https://www.figma.com/design/FILE_KEY/...

    Returns None if the URL doesn't match a known Figma pattern.
    """
    if not url:
        return None
    match = re.match(
        r"https?://(?:www\.)?figma\.com/(?:design|file)/([a-zA-Z0-9_-]+)",
        url,
    )
    return match.group(1) if match else None
