from __future__ import annotations

from app.utils.source_detect import detect_source_type, extract_figma_file_key
from app.models.project import SourceType


# ---------------------------------------------------------------------------
# detect_source_type
# ---------------------------------------------------------------------------


def test_detect_none_when_url_is_none():
    assert detect_source_type(None) == SourceType.none


def test_detect_none_when_url_is_empty():
    assert detect_source_type("") == SourceType.none


def test_detect_none_when_url_is_whitespace():
    assert detect_source_type("   ") == SourceType.none


def test_detect_figma_design_url():
    url = "https://www.figma.com/design/ABC123xyz/MyDesign"
    assert detect_source_type(url) == SourceType.figma


def test_detect_figma_file_url():
    url = "https://figma.com/file/ABC123xyz/MyDesign"
    assert detect_source_type(url) == SourceType.figma


def test_detect_website_for_vercel():
    url = "https://my-project.vercel.app"
    assert detect_source_type(url) == SourceType.website


def test_detect_website_for_framer():
    url = "https://mysite.framer.app"
    assert detect_source_type(url) == SourceType.website


def test_detect_website_for_netlify():
    url = "https://mysite.netlify.app"
    assert detect_source_type(url) == SourceType.website


def test_detect_website_for_plain_html():
    url = "https://example.com/mockup.html"
    assert detect_source_type(url) == SourceType.website


def test_detect_website_for_webflow():
    url = "https://mysite.webflow.io"
    assert detect_source_type(url) == SourceType.website


# ---------------------------------------------------------------------------
# extract_figma_file_key
# ---------------------------------------------------------------------------


def test_extract_figma_file_key_design_url():
    url = "https://www.figma.com/design/ABC123xyz/MyDesign?node-id=0-1"
    assert extract_figma_file_key(url) == "ABC123xyz"


def test_extract_figma_file_key_file_url():
    url = "https://figma.com/file/XYZ789abc/Another"
    assert extract_figma_file_key(url) == "XYZ789abc"


def test_extract_figma_file_key_returns_none_for_non_figma():
    url = "https://example.com/design/ABC123"
    assert extract_figma_file_key(url) is None


def test_extract_figma_file_key_returns_none_for_empty():
    assert extract_figma_file_key("") is None


def test_extract_figma_file_key_board_url():
    url = "https://figma.com/board/DEF456ghi/MyBoard"
    assert extract_figma_file_key(url) is None
