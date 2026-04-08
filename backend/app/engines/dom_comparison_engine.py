"""Property-by-property DOM comparison engine.

Compares two DomProfile objects element-by-element and reports every
CSS property that differs between the reference design and the Shopify
implementation, including properties present in reference but missing
in Shopify.

All issue descriptions are written as plain-English sentences so developers
and clients can understand them without reading raw CSS values.

Format: "[Element] is/has [Shopify value] in Shopify but should be [Reference value] (reference design)"
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class DomComparisonResult:
    dom_score: float          # 0–100 overall similarity
    typography_score: float   # 0–100
    color_score: float        # 0–100
    button_score: float       # 0–100
    layout_score: float       # 0–100
    issues: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _parse_rgb(color: str) -> tuple[int, int, int] | None:
    if not color:
        return None
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", color)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def _parse_px(value: str | None) -> float | None:
    if not value:
        return None
    m = re.match(r"([\d.]+)px", str(value).strip())
    return float(m.group(1)) if m else None


def _color_dist(c1: str, c2: str) -> float:
    """Return perceptual color distance [0, 1]. 0 = identical."""
    rgb1, rgb2 = _parse_rgb(c1), _parse_rgb(c2)
    if rgb1 is None or rgb2 is None:
        return 0.0  # unknown color → don't penalise
    dist = (
        (rgb1[0] - rgb2[0]) ** 2
        + (rgb1[1] - rgb2[1]) ** 2
        + (rgb1[2] - rgb2[2]) ** 2
    ) ** 0.5
    return min(dist / 441.67, 1.0)


def _px_differs(ref_str: str | None, shop_str: str | None,
                abs_tol: float = 4.0, pct_tol: float = 0.10) -> tuple[bool, float, float]:
    """Return (differs, ref_val, shop_val).
    differs=True when the absolute difference exceeds abs_tol AND
    the relative difference exceeds pct_tol.
    """
    r, s = _parse_px(ref_str), _parse_px(shop_str)
    if r is None or s is None:
        return False, 0.0, 0.0
    abs_diff = abs(r - s)
    pct_diff = abs_diff / max(r, s, 1.0)
    return (abs_diff > abs_tol and pct_diff > pct_tol), r, s


def _font_root(font: str) -> str:
    """Return the root name of a font-family string (first word, lower-cased)."""
    return font.strip().lower().split()[0].rstrip(",").strip("'\"") if font else ""


def _font_differs(ref_font: str | None, shop_font: str | None) -> bool:
    return _font_root(ref_font or "") != _font_root(shop_font or "") and bool(ref_font)


def _color_differs(c1: str | None, c2: str | None, tol: float = 0.12) -> bool:
    if not c1 or not c2:
        return False
    return _color_dist(c1, c2) > tol


# ---------------------------------------------------------------------------
# Issue factory helpers
# ---------------------------------------------------------------------------


def _issue(
    issue_type: str,
    severity: str,
    element: str,
    description: str,
    suggestion: str,
) -> dict:
    return {
        "type": issue_type,
        "severity": severity,
        "element": element,
        "description": description,
        "suggestion": suggestion,
    }


def _typo_issues(
    ref: dict | None,
    shop: dict | None,
    label: str,
    issues: list[dict],
) -> float:
    """Compare full typography of two elements. Append issues, return similarity 0-100."""
    if not ref or not shop:
        return 50.0

    scores: list[float] = []

    # Font family
    if _font_differs(ref.get("fontFamily"), shop.get("fontFamily")):
        issues.append(_issue(
            "font", "high", label,
            f"{label} font family is '{shop.get('fontFamily')}' in Shopify but should be '{ref.get('fontFamily')}' (reference design)",
            f"font-family: '{ref.get('fontFamily')}'",
        ))
        scores.append(0.0)
    else:
        scores.append(100.0)

    # Font size
    differs, rv, sv = _px_differs(ref.get("fontSize"), shop.get("fontSize"), abs_tol=2.0, pct_tol=0.08)
    if differs:
        issues.append(_issue(
            "font", "high", label,
            f"{label} font size is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
            f"font-size: {rv:.0f}px",
        ))
        scores.append(min(rv, sv) / max(rv, sv) * 100)
    else:
        scores.append(100.0)

    # Font weight
    rw, sw = str(ref.get("fontWeight", "") or ""), str(shop.get("fontWeight", "") or "")
    if rw and sw and rw != sw:
        issues.append(_issue(
            "font", "medium", label,
            f"{label} font weight is {sw} in Shopify but should be {rw} (reference design)",
            f"font-weight: {rw}",
        ))
        scores.append(50.0)
    else:
        scores.append(100.0)

    # Line height
    differs, rv, sv = _px_differs(ref.get("lineHeight"), shop.get("lineHeight"), abs_tol=2.0, pct_tol=0.08)
    if differs:
        issues.append(_issue(
            "spacing", "medium", label,
            f"{label} line height is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
            f"line-height: {rv:.0f}px",
        ))
        scores.append(min(rv, sv) / max(rv, sv) * 100)
    else:
        scores.append(100.0)

    # Letter spacing
    differs, rv, sv = _px_differs(ref.get("letterSpacing"), shop.get("letterSpacing"), abs_tol=0.5, pct_tol=0.10)
    if differs:
        issues.append(_issue(
            "font", "low", label,
            f"{label} letter spacing is {sv:.2f}px in Shopify but should be {rv:.2f}px (reference design)",
            f"letter-spacing: {rv:.2f}px",
        ))
        scores.append(min(rv, sv) / max(rv, sv) * 100 if max(rv, sv) > 0 else 100.0)
    else:
        scores.append(100.0)

    # Text color
    if _color_differs(ref.get("color"), shop.get("color"), tol=0.12):
        dist = _color_dist(ref["color"], shop["color"])
        issues.append(_issue(
            "color", "high" if dist > 0.3 else "medium", label,
            f"{label} text color is {shop.get('color')} in Shopify but should be {ref.get('color')} (reference design)",
            f"color: {ref.get('color')}",
        ))
        scores.append((1.0 - dist) * 100)
    else:
        scores.append(100.0)

    # Text transform
    rt, st = ref.get("textTransform", ""), shop.get("textTransform", "")
    if rt and st and rt != st and rt != "none":
        issues.append(_issue(
            "font", "low", label,
            f"{label} text transform is '{st}' in Shopify but should be '{rt}' (reference design)",
            f"text-transform: {rt}",
        ))
        scores.append(50.0)
    else:
        scores.append(100.0)

    return sum(scores) / len(scores) if scores else 50.0


def _spacing_issues(
    ref: dict | None,
    shop: dict | None,
    label: str,
    issues: list[dict],
    tol_abs: float = 4.0,
    tol_pct: float = 0.12,
) -> float:
    """Compare padding + margin on two elements. Return similarity 0-100."""
    if not ref or not shop:
        return 50.0

    props = [
        ("paddingTop",    "padding-top"),
        ("paddingRight",  "padding-right"),
        ("paddingBottom", "padding-bottom"),
        ("paddingLeft",   "padding-left"),
        ("marginTop",     "margin-top"),
        ("marginRight",   "margin-right"),
        ("marginBottom",  "margin-bottom"),
        ("marginLeft",    "margin-left"),
    ]
    scores: list[float] = []
    for key, css_name in props:
        differs, rv, sv = _px_differs(ref.get(key), shop.get(key), tol_abs, tol_pct)
        if differs:
            issues.append(_issue(
                "spacing", "medium", label,
                f"{label} {css_name} is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
                f"{css_name}: {rv:.0f}px",
            ))
            scores.append(min(rv, sv) / max(rv, sv) * 100 if max(rv, sv) > 0 else 100.0)
        else:
            scores.append(100.0)

    return sum(scores) / len(scores) if scores else 100.0


def _dimension_issues(
    ref: dict | None,
    shop: dict | None,
    label: str,
    issues: list[dict],
    kind: str = "layout",
    tol_abs: float = 10.0,
    tol_pct: float = 0.12,
) -> float:
    if not ref or not shop:
        return 50.0
    scores: list[float] = []
    for key, css_prop in (("width", "width"), ("height", "height")):
        rv_raw = ref.get(key)
        sv_raw = shop.get(key)
        if rv_raw is None or sv_raw is None:
            continue
        rv, sv = float(rv_raw), float(sv_raw)
        abs_diff = abs(rv - sv)
        pct_diff = abs_diff / max(rv, sv, 1.0)
        if abs_diff > tol_abs and pct_diff > tol_pct:
            issues.append(_issue(
                kind, "medium" if pct_diff < 0.25 else "high", label,
                f"{label} {css_prop} is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
                f"{css_prop}: {rv:.0f}px",
            ))
            scores.append(min(rv, sv) / max(rv, sv) * 100)
        else:
            scores.append(100.0)
    return sum(scores) / len(scores) if scores else 100.0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class DomComparisonEngine:
    """Full property-by-property comparison of two DomProfile instances."""

    def compare(
        self,
        ref: "DomProfile",  # type: ignore[name-defined]
        shopify: "DomProfile",  # type: ignore[name-defined]
    ) -> DomComparisonResult:
        issues: list[dict] = []
        typo_scores: list[float] = []
        color_scores: list[float] = []
        button_scores: list[float] = []
        layout_scores: list[float] = []

        # ── Global typography ─────────────────────────────────────────────────
        ref_g = ref.global_styles or {}
        shop_g = shopify.global_styles or {}

        for key, label in (("h1", "H1 heading"), ("h2", "H2 heading"), ("body", "Body text")):
            s = _typo_issues(ref_g.get(key) or {}, shop_g.get(key) or {}, label, issues)
            typo_scores.append(s)

        # Body background color
        ref_bg = (ref_g.get("body") or {}).get("backgroundColor")
        shop_bg = (shop_g.get("body") or {}).get("backgroundColor")
        if _color_differs(ref_bg, shop_bg):
            dist = _color_dist(ref_bg, shop_bg)
            issues.append(_issue(
                "color", "high" if dist > 0.3 else "medium", "Page background",
                f"Page background color is {shop_bg} in Shopify but should be {ref_bg} (reference design)",
                f"background-color: {ref_bg}",
            ))
            color_scores.append((1.0 - dist) * 100)
        else:
            color_scores.append(100.0)

        # Global container max-width
        r_mw = (ref_g.get("container") or {}).get("maxWidth")
        s_mw = (shop_g.get("container") or {}).get("maxWidth")
        differs, rv, sv = _px_differs(r_mw, s_mw, abs_tol=5.0, pct_tol=0.05)
        if differs:
            issues.append(_issue(
                "layout", "medium", "Page container",
                f"Page container max-width is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
                f"max-width: {rv:.0f}px",
            ))
            layout_scores.append(min(rv, sv) / max(rv, sv) * 100)
        else:
            layout_scores.append(100.0)

        # ── Primary button (global) ────────────────────────────────────────────
        ref_btn = ref_g.get("primaryButton")
        shop_btn = shop_g.get("primaryButton")
        if ref_btn and shop_btn:
            s = _typo_issues(ref_btn, shop_btn, "Primary button text", issues)
            button_scores.append(s)
            _spacing_issues(ref_btn, shop_btn, "Primary button", issues, tol_abs=3.0)
            _dimension_issues(ref_btn, shop_btn, "Primary button", issues, kind="button", tol_pct=0.15)

            # button-specific color/radius/border
            if _color_differs(ref_btn.get("backgroundColor"), shop_btn.get("backgroundColor")):
                dist = _color_dist(ref_btn["backgroundColor"], shop_btn["backgroundColor"])
                issues.append(_issue(
                    "button", "high", "Primary button",
                    f"Primary button background is {shop_btn['backgroundColor']} in Shopify but should be {ref_btn['backgroundColor']} (reference design)",
                    f"background-color: {ref_btn['backgroundColor']}",
                ))
                button_scores.append((1.0 - dist) * 100)
            else:
                button_scores.append(100.0)

            differs, rv, sv = _px_differs(ref_btn.get("borderRadius"), shop_btn.get("borderRadius"), 2.0, 0.1)
            if differs:
                issues.append(_issue(
                    "button", "low", "Primary button",
                    f"Primary button border radius is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
                    f"border-radius: {rv:.0f}px",
                ))
                button_scores.append(min(rv, sv) / max(rv, sv) * 100)

            r_border = ref_btn.get("border", "")
            s_border = shop_btn.get("border", "")
            if r_border and s_border and r_border != s_border and "none" not in r_border:
                issues.append(_issue(
                    "button", "low", "Primary button",
                    f"Primary button border is '{s_border}' in Shopify but should be '{r_border}' (reference design)",
                    f"border: {r_border}",
                ))
                button_scores.append(60.0)

        # ── Header ────────────────────────────────────────────────────────────
        ref_h = ref.header or {}
        shop_h = shopify.header or {}
        if ref_h and shop_h:
            # Header height
            differs, rv, sv = _px_differs(
                str(ref_h.get("height") or ""), str(shop_h.get("height") or ""),
                abs_tol=4.0, pct_tol=0.08,
            )
            if differs:
                issues.append(_issue(
                    "layout", "high", "Header",
                    f"Header height is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
                    f"height: {rv:.0f}px",
                ))
                layout_scores.append(min(rv, sv) / max(rv, sv) * 100)

            # Header background
            if _color_differs(ref_h.get("backgroundColor"), shop_h.get("backgroundColor")):
                dist = _color_dist(ref_h["backgroundColor"], shop_h["backgroundColor"])
                issues.append(_issue(
                    "color", "high", "Header background",
                    f"Header background is {shop_h['backgroundColor']} in Shopify but should be {ref_h['backgroundColor']} (reference design)",
                    f"background-color: {ref_h['backgroundColor']}",
                ))
                color_scores.append((1.0 - dist) * 100)

            # Navigation font + color
            ref_nav = ref_h.get("nav") or {}
            shop_nav = shop_h.get("nav") or {}
            if ref_nav and shop_nav:
                if _font_differs(ref_nav.get("fontFamily"), shop_nav.get("fontFamily")):
                    issues.append(_issue(
                        "font", "medium", "Navigation",
                        f"Navigation font family is '{shop_nav.get('fontFamily')}' in Shopify but should be '{ref_nav.get('fontFamily')}' (reference design)",
                        f"font-family: '{ref_nav.get('fontFamily')}'",
                    ))
                    typo_scores.append(0.0)

                differs, rv, sv = _px_differs(ref_nav.get("fontSize"), shop_nav.get("fontSize"), 1.0, 0.07)
                if differs:
                    issues.append(_issue(
                        "font", "medium", "Navigation",
                        f"Navigation font size is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
                        f"font-size: {rv:.0f}px",
                    ))

                if _color_differs(ref_nav.get("color"), shop_nav.get("color")):
                    dist = _color_dist(ref_nav["color"], shop_nav["color"])
                    issues.append(_issue(
                        "color", "medium", "Navigation links",
                        f"Navigation link color is {shop_nav['color']} in Shopify but should be {ref_nav['color']} (reference design)",
                        f"color: {ref_nav['color']}",
                    ))
                    color_scores.append((1.0 - dist) * 100)

                # Nav item count
                r_ic = ref_nav.get("itemCount", 0) or 0
                s_ic = shop_nav.get("itemCount", 0) or 0
                if r_ic > 0 and s_ic > 0 and abs(r_ic - s_ic) > 1:
                    issues.append(_issue(
                        "navigation", "high", "Navigation",
                        f"Navigation has {s_ic} link(s) in Shopify but the reference design shows {r_ic} link(s) — check if nav items are missing",
                        "Verify all navigation items from the reference design are present in Shopify",
                    ))
                    layout_scores.append(min(r_ic, s_ic) / max(r_ic, s_ic) * 100)

            # Logo dimensions
            ref_logo = ref_h.get("logo") or {}
            shop_logo = shop_h.get("logo") or {}
            if ref_logo and shop_logo:
                s = _dimension_issues(ref_logo, shop_logo, "Header logo", issues, kind="layout", tol_pct=0.15)
                layout_scores.append(s)

        # ── Footer ────────────────────────────────────────────────────────────
        ref_f = ref.footer or {}
        shop_f = shopify.footer or {}
        if ref_f and shop_f:
            if _color_differs(ref_f.get("backgroundColor"), shop_f.get("backgroundColor")):
                dist = _color_dist(ref_f["backgroundColor"], shop_f["backgroundColor"])
                issues.append(_issue(
                    "color", "medium", "Footer background",
                    f"Footer background is {shop_f['backgroundColor']} in Shopify but should be {ref_f['backgroundColor']} (reference design)",
                    f"background-color: {ref_f['backgroundColor']}",
                ))
                color_scores.append((1.0 - dist) * 100)

            if _color_differs(ref_f.get("color"), shop_f.get("color")):
                issues.append(_issue(
                    "color", "low", "Footer text",
                    f"Footer text color is {shop_f.get('color')} in Shopify but should be {ref_f.get('color')} (reference design)",
                    f"color: {ref_f.get('color')}",
                ))

            differs, rv, sv = _px_differs(ref_f.get("fontSize"), shop_f.get("fontSize"), 1.0, 0.08)
            if differs:
                issues.append(_issue(
                    "font", "low", "Footer",
                    f"Footer font size is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
                    f"font-size: {rv:.0f}px",
                ))

            _spacing_issues(ref_f, shop_f, "Footer", issues)

        # ── Sections ──────────────────────────────────────────────────────────
        ref_secs = ref.sections or []
        shop_secs = shopify.sections or []

        # Flag sections present in reference but missing in Shopify.
        # Guard: if Shopify returned 0 sections it means DOM extraction found no
        # matching elements (layout differs structurally) — not that all sections
        # are genuinely absent.  Only fire when Shopify has some sections but
        # meaningfully fewer than reference (gap > 2 avoids noise from minor
        # structural differences between platforms).
        if len(shop_secs) > 0 and len(ref_secs) > len(shop_secs) + 2:
            missing = len(ref_secs) - len(shop_secs)
            issues.append(_issue(
                "layout", "high", "Missing sections",
                f"{missing} section(s) may be missing — reference design has {len(ref_secs)} sections but Shopify shows only {len(shop_secs)}",
                "Check if all sections from the reference design are implemented in Shopify",
            ))
            layout_scores.append(len(shop_secs) / len(ref_secs) * 100)
        elif ref_secs and shop_secs:
            layout_scores.append(100.0)

        n_compare = min(len(ref_secs), len(shop_secs), 10)
        for i in range(n_compare):
            rs = ref_secs[i]
            ss = shop_secs[i]
            sec_label = f"Section {i + 1}"

            # Section background
            if _color_differs(rs.get("backgroundColor"), ss.get("backgroundColor")):
                dist = _color_dist(rs["backgroundColor"], ss["backgroundColor"])
                issues.append(_issue(
                    "color", "high" if dist > 0.3 else "medium", f"{sec_label} background",
                    f"{sec_label} background is {ss['backgroundColor']} in Shopify but should be {rs['backgroundColor']} (reference design)",
                    f"background-color: {rs['backgroundColor']}",
                ))
                color_scores.append((1.0 - dist) * 100)
            else:
                color_scores.append(100.0)

            # Section padding
            s_sp = _spacing_issues(rs, ss, sec_label, issues)
            layout_scores.append(s_sp)

            # Section dimensions (height / width) — generous tolerance
            s_dim = _dimension_issues(rs, ss, sec_label, issues, tol_abs=20.0, tol_pct=0.15)
            layout_scores.append(s_dim)

            # Inner container max-width
            r_inner = rs.get("container") or {}
            s_inner = ss.get("container") or {}
            if r_inner and s_inner:
                differs, rv, sv = _px_differs(r_inner.get("maxWidth"), s_inner.get("maxWidth"), 5.0, 0.05)
                if differs:
                    issues.append(_issue(
                        "layout", "medium", f"{sec_label} container",
                        f"{sec_label} inner container max-width is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
                        f"max-width: {rv:.0f}px",
                    ))
                    layout_scores.append(min(rv, sv) / max(rv, sv) * 100)

            # ── Headings within this section ──────────────────────────────────
            r_heads = rs.get("headings") or []
            s_heads = ss.get("headings") or []
            if len(r_heads) > len(s_heads) and r_heads:
                issues.append(_issue(
                    "layout", "high", f"{sec_label} headings",
                    f"{sec_label} is missing headings — reference design has {len(r_heads)} heading(s) but Shopify only shows {len(s_heads)}",
                    f"Add {len(r_heads) - len(s_heads)} missing heading(s) to {sec_label}",
                ))
            for j in range(min(len(r_heads), len(s_heads))):
                rh, sh = r_heads[j], s_heads[j]
                head_label = f"{sec_label} › {rh.get('tag', 'heading').upper()}"
                s_t = _typo_issues(rh, sh, head_label, issues)
                typo_scores.append(s_t)
                _dimension_issues(rh, sh, head_label, issues, kind="layout", tol_pct=0.20)

            # ── Body text within this section ─────────────────────────────────
            r_paras = rs.get("paragraphs") or []
            s_paras = ss.get("paragraphs") or []
            for j in range(min(len(r_paras), len(s_paras), 2)):
                rp, sp = r_paras[j], s_paras[j]
                para_label = f"{sec_label} › body text"
                s_t = _typo_issues(rp, sp, para_label, issues)
                typo_scores.append(s_t)

            # ── Images within this section ────────────────────────────────────
            r_imgs = rs.get("images") or []
            s_imgs = ss.get("images") or []
            if len(r_imgs) > len(s_imgs) and r_imgs:
                issues.append(_issue(
                    "layout", "high", f"{sec_label} images",
                    f"{sec_label} is missing images — reference design has {len(r_imgs)} image(s) but Shopify only shows {len(s_imgs)}",
                    f"Add {len(r_imgs) - len(s_imgs)} missing image(s) to {sec_label}",
                ))
            for j in range(min(len(r_imgs), len(s_imgs))):
                ri, si = r_imgs[j], s_imgs[j]
                img_label = f"{sec_label} › image {j + 1}"
                # Rendered dimensions
                for dim_key, css_prop in (("width", "width"), ("height", "height")):
                    rv_raw = ri.get(dim_key)
                    sv_raw = si.get(dim_key)
                    if rv_raw and sv_raw:
                        rv, sv = float(rv_raw), float(sv_raw)
                        abs_diff = abs(rv - sv)
                        pct_diff = abs_diff / max(rv, sv, 1.0)
                        if abs_diff > 15.0 and pct_diff > 0.15:
                            issues.append(_issue(
                                "layout", "medium", img_label,
                                f"{img_label} {css_prop} is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
                                f"{css_prop}: {rv:.0f}px",
                            ))
                            layout_scores.append(min(rv, sv) / max(rv, sv) * 100)
                # object-fit
                rof, sof = ri.get("objectFit", ""), si.get("objectFit", "")
                if rof and sof and rof != sof:
                    issues.append(_issue(
                        "layout", "low", img_label,
                        f"{img_label} object-fit is '{sof}' in Shopify but should be '{rof}' (reference design)",
                        f"object-fit: {rof}",
                    ))

            # ── Buttons within this section ───────────────────────────────────
            r_btns = rs.get("buttons") or []
            s_btns = ss.get("buttons") or []
            if len(r_btns) > len(s_btns) and r_btns:
                issues.append(_issue(
                    "button", "high", f"{sec_label} buttons",
                    f"{sec_label} is missing buttons — reference design has {len(r_btns)} button(s) but Shopify only shows {len(s_btns)}",
                    f"Add {len(r_btns) - len(s_btns)} missing button(s) to {sec_label}",
                ))
            for j in range(min(len(r_btns), len(s_btns))):
                rb, sb = r_btns[j], s_btns[j]
                btn_text = rb.get("text") or str(j + 1)
                btn_label = f"{sec_label} › '{btn_text}' button"

                _typo_issues(rb, sb, btn_label, issues)
                if _color_differs(rb.get("backgroundColor"), sb.get("backgroundColor")):
                    dist = _color_dist(rb["backgroundColor"], sb["backgroundColor"])
                    issues.append(_issue(
                        "button", "high", btn_label,
                        f"'{btn_text}' button background is {sb['backgroundColor']} in Shopify but should be {rb['backgroundColor']} (reference design)",
                        f"background-color: {rb['backgroundColor']}",
                    ))
                    button_scores.append((1.0 - dist) * 100)
                else:
                    button_scores.append(100.0)

                differs, rv, sv = _px_differs(rb.get("borderRadius"), sb.get("borderRadius"), 2.0, 0.1)
                if differs:
                    issues.append(_issue(
                        "button", "low", btn_label,
                        f"'{btn_text}' button border radius is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
                        f"border-radius: {rv:.0f}px",
                    ))

                _spacing_issues(rb, sb, btn_label, issues, tol_abs=2.0, tol_pct=0.10)
                _dimension_issues(rb, sb, btn_label, issues, kind="button", tol_abs=5.0, tol_pct=0.15)

            # ── Icons within this section ─────────────────────────────────────
            r_icons = rs.get("icons") or []
            s_icons = ss.get("icons") or []
            for j in range(min(len(r_icons), len(s_icons))):
                ri, si = r_icons[j], s_icons[j]
                icon_label = f"{sec_label} › icon {j + 1}"
                for dim_key in ("width", "height"):
                    rv_raw = ri.get(dim_key)
                    sv_raw = si.get(dim_key)
                    if rv_raw and sv_raw:
                        rv, sv = float(rv_raw), float(sv_raw)
                        if abs(rv - sv) > 4.0 and abs(rv - sv) / max(rv, sv, 1.0) > 0.15:
                            issues.append(_issue(
                                "layout", "low", icon_label,
                                f"{icon_label} {dim_key} is {sv:.0f}px in Shopify but should be {rv:.0f}px (reference design)",
                                f"{dim_key}: {rv:.0f}px",
                            ))
                            layout_scores.append(min(rv, sv) / max(rv, sv) * 100)

        # ── Weighted final score ──────────────────────────────────────────────
        def _avg(lst: list[float]) -> float:
            return round(sum(lst) / len(lst), 2) if lst else 50.0

        typography_score = _avg(typo_scores)
        color_score      = _avg(color_scores)
        button_score     = _avg(button_scores)
        layout_score     = _avg(layout_scores)

        dom_score = (
            typography_score * 0.35
            + color_score    * 0.25
            + button_score   * 0.15
            + layout_score   * 0.25
        )

        return DomComparisonResult(
            dom_score=round(dom_score, 2),
            typography_score=typography_score,
            color_score=color_score,
            button_score=button_score,
            layout_score=layout_score,
            issues=issues,
        )
