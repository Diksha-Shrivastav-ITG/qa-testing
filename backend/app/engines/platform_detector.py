"""Auto-detect the design platform from a URL.

Supports: Figma, Framer, Webflow, Vercel/Next.js, Shopify preview, generic web URLs.
"""
from __future__ import annotations

import re

# ── Detection rules ───────────────────────────────────────────────────────────
# Order matters — more specific patterns first.
_RULES: list[tuple[str, list[str]]] = [
    ("figma",           [r"figma\.com/(file|proto|design|board)"]),
    ("framer",          [r"framer\.com", r"\.framer\.app", r"\.framer\.website"]),
    ("webflow",         [r"webflow\.io", r"\.webflow\.com"]),
    ("vercel",          [r"\.vercel\.app", r"vercel\.app"]),
    ("shopify_preview", [r"myshopify\.com", r"shopify\.com/.*preview"]),
]

# Human-readable labels shown in the UI
PLATFORM_LABELS: dict[str, str] = {
    "figma":           "Figma",
    "framer":          "Framer",
    "webflow":         "Webflow",
    "vercel":          "Vercel / Next.js",
    "shopify_preview": "Shopify Preview",
    "url":             "Web URL",
    "none":            "None",
}

# Badge colours (Tailwind CSS classes) for the UI platform badge
PLATFORM_BADGE_CLASSES: dict[str, str] = {
    "figma":           "bg-purple-100 text-purple-700 border-purple-200",
    "framer":          "bg-blue-100 text-blue-700 border-blue-200",
    "webflow":         "bg-cyan-100 text-cyan-700 border-cyan-200",
    "vercel":          "bg-gray-100 text-gray-700 border-gray-200",
    "shopify_preview": "bg-green-100 text-green-700 border-green-200",
    "url":             "bg-slate-100 text-slate-600 border-slate-200",
    "none":            "bg-gray-50 text-gray-400 border-gray-100",
}


def detect_platform(url: str) -> str:
    """Return the platform identifier for *url*.

    Returns one of: 'figma', 'framer', 'webflow', 'vercel',
    'shopify_preview', 'url', or 'none' (empty URL).
    """
    if not url or not url.strip():
        return "none"
    for platform, patterns in _RULES:
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return platform
    return "url"


def platform_label(platform: str) -> str:
    """Return the human-readable label for a platform identifier."""
    return PLATFORM_LABELS.get(platform, "Web URL")
