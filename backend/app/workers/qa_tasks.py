from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

from app.workers.celery_app import celery_app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BREAKPOINTS = [375, 768, 1440]  # Mobile, Tablet, Desktop — fast and covers all


def _clean_page_name(raw_path: str) -> str:
    """Convert a raw Shopify path (may include query params) to a clean page slug.

    Examples:
        "/"                                      → "home"
        "/collections/summer"                    → "collections/summer"
        "?_ab=0&preview_theme_id=148090650806"   → "home"
        "/?_ab=0&preview_theme_id=148090650806"  → "home"
    """
    from urllib.parse import urlparse as _up
    try:
        parsed = _up(raw_path if raw_path.startswith("http") else f"http://x{raw_path}")
        clean = parsed.path.strip("/")
    except Exception:
        clean = raw_path.strip("/").split("?")[0]
    return clean or "home"


def _build_page_url(base_url: str, path: str) -> str:
    """Build a full URL from a base URL and a path, preserving query params like preview_theme_id."""
    from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

    parsed = urlparse(base_url)
    # Combine the base path with the new path
    new_path = path if path.startswith("/") else f"/{path}"
    # Rebuild URL with the new path but keep all query params
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        new_path,
        parsed.params,
        parsed.query,  # preserves preview_theme_id etc.
        parsed.fragment,
    ))

# Phase weights for overall progress calculation (must sum to 1.0)
PHASE_WEIGHTS = {
    "discovery": 0.05,
    "capture": 0.30,
    "compare": 0.25,
    "functional": 0.10,
    "accessibility": 0.10,
    "link_audit": 0.10,
    "matching": 0.03,
    "scoring": 0.07,
}


def _should_run(phase: str, test_types: "Optional[list[str]]") -> bool:
    """Return True if this phase should run. None means run everything."""
    if test_types is None:
        return True
    return phase in test_types


def _overall_progress(completed_phases: list[str], current_phase: str, phase_progress: float) -> float:
    """Calculate overall progress (0-100) across all phases."""
    total = 0.0
    for phase, weight in PHASE_WEIGHTS.items():
        if phase in completed_phases:
            total += weight * 100
        elif phase == current_phase:
            total += weight * phase_progress * 100
    return min(100.0, round(total, 1))


# ---------------------------------------------------------------------------
# Redis progress publisher
# ---------------------------------------------------------------------------


async def _capture_element_screenshot(
    page_url: str,
    selector: str | None,
    output_path: str,
    password: str | None = None,
) -> str | None:
    """Navigate to a page and screenshot a specific element by CSS selector.

    Falls back to a viewport-sized screenshot if the selector isn't found.
    """
    if not selector or not selector.strip():
        return None
    try:
        from playwright.async_api import async_playwright

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            )
            await ctx.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await ctx.new_page()
            await page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)

            # Try each selector (comma-separated)
            for sel in selector.split(","):
                sel = sel.strip()
                if not sel:
                    continue
                try:
                    elem = page.locator(sel).first
                    if await elem.is_visible(timeout=3000):
                        await elem.screenshot(path=output_path)
                        await browser.close()
                        return output_path
                except Exception:
                    continue

            # Fallback: viewport screenshot
            await page.screenshot(path=output_path, clip={"x": 0, "y": 0, "width": 1440, "height": 600})
            await browser.close()
            return output_path
    except Exception:
        return None


def publish_progress(
    run_id: int,
    step: str,
    page: str = "",
    breakpoint_val: int = 0,
    progress: float = 0.0,
    message: str = "",
) -> None:
    """Publish progress JSON to Redis channel ``qa_run:{run_id}``.

    Also stores the latest state in a Redis key so new subscribers can get
    the current progress immediately without waiting for the next event.
    """
    try:
        import redis as redis_lib

        from app.config import settings

        r = redis_lib.Redis.from_url(settings.redis_url)
        payload = json.dumps(
            {
                "run_id": run_id,
                "step": step,
                "page": page,
                "breakpoint": breakpoint_val,
                "progress": progress,
                "message": message,
            }
        )
        # Publish to channel for active listeners
        r.publish(f"qa_run:{run_id}", payload)
        # Store latest state so new subscribers get it immediately (TTL 1 hour)
        r.set(f"qa_run:{run_id}:latest", payload, ex=3600)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Async orchestrator
# ---------------------------------------------------------------------------


async def _run_qa_job_async(
    run_id: int,
    partial_pages: Optional[list[str]] = None,
    test_mode: str = "design",
    test_types: Optional[list[str]] = None,
    reference_urls_override: Optional[list[str]] = None,
    *,
    _publish_fn=publish_progress,
) -> None:
    """Execute the full QA pipeline.

    Phases:
      1. Discovery       – auto-discover pages if project has no mappings
      2. Capture         – screenshot Shopify (+ design if test_mode=design)
      3. Compare         – SSIM + AI analysis (or AI-only if test_mode=ai)
      4. Functional      – surface tests + Shopify flows
      5. Accessibility   – ADA/WCAG compliance checks
      6. Link Audit      – audit all links and buttons
      7. Issue Matching  – compare with previous run
      8. Score           – calculate overall score, mark run completed
    """
    from app.config import settings
    from app.database import get_session_factory
    from app.engines.accessibility_engine import AccessibilityEngine
    from app.engines.capture_engine import CaptureEngine
    from app.engines.comparison_engine import ComparisonEngine
    from app.engines.discovery_engine import DiscoveryEngine
    from app.engines.functional_engine import FunctionalEngine
    from app.engines.link_audit_engine import LinkAuditEngine
    from app.models.accessibility_result import AccessibilityResult
    from app.models.capture import Capture, CaptureSource
    from app.models.comparison import AiAnalysisStatus, Comparison
    from app.models.functional_test import FunctionalTest, FunctionalTestStatus
    from app.models.issue import Issue, IssueSeverity, IssueStatus, IssueType
    from app.models.link_audit import LinkAudit
    from app.models.project import Project, SourceType
    from app.models.qa_run import QaRun, RunStatus
    from app.services.issue_matcher import match_issues
    from app.services.run_service import calculate_score

    db = get_session_factory()()

    try:
        # ---- Load run & project ----
        run = db.query(QaRun).filter(QaRun.id == run_id).first()
        if run is None:
            return
        project = db.query(Project).filter(Project.id == run.project_id).first()
        if project is None:
            run.status = RunStatus.failed
            run.completed_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            return

        # test_mode and test_types are already stored at run creation time in runs.py

        run_dir = f"run_{run_id}"
        done_phases: list[str] = []

        # ---- Phase 1: Discovery ----
        _publish_fn(run_id, "discovery", progress=_overall_progress(done_phases, "discovery", 0), message="Starting discovery")

        # ── Resolve page mappings ────────────────────────────────────────────
        # Priority:
        #   1. Explicit page_pairs stored in project.config (set at project creation)
        #   2. Cached mappings from a previous discovery run
        #   3. Auto-discovery (fallback)

        page_mappings: dict[str, str] = {}

        # 1. Explicit page_pairs (platform-independent multi-page support)
        raw_pairs: list[dict] = project.config.get("page_pairs", [])
        if raw_pairs:
            for pair in raw_pairs:
                sp = pair.get("shopify_path", "/")
                srcp = pair.get("source_path", "/")
                page_mappings[sp] = srcp

        # 2. Cached discovery mappings (keyed as "mappings" in config)
        if not page_mappings:
            page_mappings = project.config.get("mappings", {})

        has_design_source = (
            project.source_url
            and project.source_url.strip()
            and project.source_type != SourceType.none
        )

        if not page_mappings:
            discovery = DiscoveryEngine()
            shopify_pages = await discovery.discover_pages(
                project.shopify_url, password=project.shopify_password
            )

            if test_mode == "ai" or not has_design_source:
                # AI-only mode or no design source — map Shopify pages to themselves
                source_pages = shopify_pages
            elif project.source_type == SourceType.framer:
                source_pages = await discovery.discover_framer_pages(project.source_url)
            elif project.source_type == SourceType.figma:
                # Figma frames are captured via API; map Shopify paths to themselves
                source_pages = shopify_pages
            else:
                # Generic web URL (Vercel, Webflow, static site, etc.)
                # Attempt to crawl the source URL; fall back to Shopify paths
                try:
                    source_pages = await discovery.discover_pages(project.source_url)
                except Exception:
                    source_pages = shopify_pages

            page_mappings = discovery.auto_map(shopify_pages, source_pages)

        # Override page mappings with per-page reference URLs provided at run time
        # (set when user specifies a Reference URL per page in the Start QA modal)
        if partial_pages and reference_urls_override and len(reference_urls_override) == len(partial_pages):
            page_mappings = {
                path: ref_url
                for path, ref_url in zip(partial_pages, reference_urls_override)
                if path.strip()
            }

        # Filter to partial pages if specified
        if partial_pages and not reference_urls_override:
            # Known top-level prefixes for "other" filter
            _KNOWN_PREFIXES = ("/collections", "/products")

            def _page_matches(path: str, filters: list[str]) -> bool:
                for f in filters:
                    if f in ("/", ""):
                        # Homepage only
                        if path == "/" or path == "":
                            return True
                        continue
                    if f == "__other__":
                        # Pages that are NOT home, collections, or products
                        if path in ("/", ""):
                            continue
                        if any(path == pfx or path.startswith(pfx + "/") for pfx in _KNOWN_PREFIXES):
                            continue
                        return True
                    if f == "/collections":
                        # Match collection pages: /collections, /collections/all, /collections/summer etc.
                        if path == "/collections" or path.startswith("/collections/") or path == "/collections":
                            return True
                        continue
                    if f == "/products":
                        # Product pages — /products or any /products/...
                        if path == f or path.startswith(f + "/") or path == f.rstrip("/"):
                            return True
                        continue
                    # Generic exact or prefix match
                    if path == f:
                        return True
                    prefix = f.rstrip("/")
                    if path.startswith(prefix + "/") or path == prefix:
                        return True
                return False
            page_mappings = {k: v for k, v in page_mappings.items() if _page_matches(k, partial_pages)}

        if not page_mappings:
            run.overall_score = 0.0
            run.status = RunStatus.completed
            run.completed_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            _publish_fn(run_id, "completed", progress=1.0, message="No pages to test")
            return

        done_phases.append("discovery")
        _publish_fn(run_id, "discovery", progress=_overall_progress(done_phases, "", 0), message=f"Discovered {len(page_mappings)} pages")

        # ---- Phase 2: Capture ----
        capture_engine = CaptureEngine(storage_path=settings.storage_path)

        # In AI mode or no design source — only capture Shopify
        skip_design = test_mode == "ai" or not has_design_source
        sources_per_page = 1 if skip_design else 2
        total_captures = len(page_mappings) * len(BREAKPOINTS) * sources_per_page
        captured_count = 0
        capture_pairs: list[dict] = []

        for shopify_path, source_path in page_mappings.items():
            db.refresh(run)
            if run.status == RunStatus.cancelled:
                _publish_fn(run_id, "cancelled", progress=0.0, message="Run cancelled")
                return

            page_name = _clean_page_name(shopify_path)
            shopify_url = _build_page_url(project.shopify_url, shopify_path)

            if skip_design:
                shopify_results = await capture_engine.capture_page(
                    url=shopify_url,
                    page_name=page_name,
                    run_dir=run_dir,
                    source="shopify",
                    breakpoints=BREAKPOINTS,
                    password=project.shopify_password,
                )
                design_results = []
            else:
                # Capture Shopify + Design simultaneously
                # source_path may be a full URL (per-page reference URL override) or a path
                if source_path.startswith("http://") or source_path.startswith("https://"):
                    source_url = source_path
                else:
                    source_url = (project.source_url or "").rstrip("/") + source_path
                shopify_results, design_results = await asyncio.gather(
                    capture_engine.capture_page(
                        url=shopify_url,
                        page_name=page_name,
                        run_dir=run_dir,
                        source="shopify",
                        breakpoints=BREAKPOINTS,
                        password=project.shopify_password,
                    ),
                    capture_engine.capture_page(
                        url=source_url,
                        page_name=page_name,
                        run_dir=run_dir,
                        source="design",
                        breakpoints=BREAKPOINTS,
                        password=project.framer_password,
                    ),
                )

            for cr in shopify_results:
                captured_count += 1
                _publish_fn(
                    run_id, "capture", page=page_name,
                    breakpoint_val=cr.breakpoint,
                    progress=_overall_progress(done_phases, "capture", captured_count / total_captures),
                    message=f"Captured shopify {page_name} @{cr.breakpoint}px",
                )
                if cr.status == "success":
                    db.add(Capture(
                        qa_run_id=run_id,
                        source=CaptureSource.shopify,
                        page=page_name,
                        breakpoint=cr.breakpoint,
                        image_path=cr.image_path,
                    ))

            shopify_by_bp = {r.breakpoint: r for r in shopify_results if r.status == "success"}

            if skip_design:
                for bp, sr in shopify_by_bp.items():
                    capture_pairs.append({
                        "page": page_name,
                        "breakpoint": bp,
                        "shopify_path": sr.image_path,
                        "shopify_page_url": shopify_url,
                        "design_path": None,
                        "mode": "ai",
                    })
            else:
                for dr in design_results:
                    captured_count += 1
                    _publish_fn(
                        run_id, "capture", page=page_name,
                        breakpoint_val=dr.breakpoint,
                        progress=_overall_progress(done_phases, "capture", captured_count / total_captures),
                        message=f"Captured design {page_name} @{dr.breakpoint}px",
                    )
                    if dr.status == "success":
                        db.add(Capture(
                            qa_run_id=run_id,
                            source=CaptureSource.design,
                            page=page_name,
                            breakpoint=dr.breakpoint,
                            image_path=dr.image_path,
                        ))

                design_by_bp = {r.breakpoint: r for r in design_results if r.status == "success"}
                for bp in BREAKPOINTS:
                    if bp in shopify_by_bp and bp in design_by_bp:
                        # Both captures succeeded — run full design comparison
                        capture_pairs.append({
                            "page": page_name,
                            "breakpoint": bp,
                            "shopify_path": shopify_by_bp[bp].image_path,
                            "shopify_page_url": shopify_url,
                            "design_path": design_by_bp[bp].image_path,
                            "mode": "design",
                        })
                    elif bp in shopify_by_bp:
                        # Design capture failed — fall back to AI-only for this breakpoint
                        capture_pairs.append({
                            "page": page_name,
                            "breakpoint": bp,
                            "shopify_path": shopify_by_bp[bp].image_path,
                            "shopify_page_url": shopify_url,
                            "design_path": None,
                            "mode": "ai",
                        })

            db.commit()

        # ---- Phase 3: Compare ----
        done_phases.append("capture")
        if _should_run("qa", test_types):
            from app.engines.dom_comparison_engine import DomComparisonEngine
            from app.engines.dom_extraction_engine import DomExtractionEngine

            comparison_engine = ComparisonEngine(
                openai_api_key=settings.openai_api_key,
                aws_access_key=settings.aws_access_key,
                aws_bedrock_secret_key=settings.aws_bedrock_secret_key,
                aws_region=settings.aws_region,
                bedrock_model_id=settings.bedrock_model_id,
                storage_path=settings.storage_path,
            )
            dom_extractor = DomExtractionEngine()
            dom_comparator = DomComparisonEngine()
            total_comparisons = len(capture_pairs)

            _severity_map = {
                "critical": IssueSeverity.critical,
                "high": IssueSeverity.major,
                "medium": IssueSeverity.minor,
                "low": IssueSeverity.minor,
                "major": IssueSeverity.major,
                "minor": IssueSeverity.minor,
            }

            # ── Pre-extract DOM profiles once per unique page (not per breakpoint) ──
            # Only run DOM extraction in design mode (not AI-only)
            # dom_profiles keyed by (page_name, viewport_width) — one entry per breakpoint
            # so mobile comparisons use mobile DOM measurements.
            dom_profiles: dict[tuple, tuple] = {}  # (page, bp) → (dom_result, ref_prof, shop_prof)
            if not skip_design and has_design_source:
                _publish_fn(run_id, "compare",
                            progress=_overall_progress(done_phases, "compare", 0),
                            message="Extracting DOM style profiles")
                _dom_sem = asyncio.Semaphore(3)

                async def _extract_dom_pair(shopify_path: str, source_path: str, vp: int) -> tuple:
                    async with _dom_sem:
                        pname = shopify_path.strip("/") or "home"
                        shop_url = _build_page_url(project.shopify_url, shopify_path)
                        src_url = (project.source_url or "").rstrip("/") + source_path
                        ref_prof, shop_prof = await asyncio.gather(
                            dom_extractor.extract(src_url, password=project.framer_password, viewport_width=vp),
                            dom_extractor.extract(shop_url, password=project.shopify_password, viewport_width=vp),
                            return_exceptions=True,
                        )
                        return pname, vp, ref_prof, shop_prof

                # Extract at each unique breakpoint so responsive layout is measured correctly
                dom_tasks = [
                    _extract_dom_pair(sp, srcp, bp)
                    for sp, srcp in page_mappings.items()
                    for bp in BREAKPOINTS
                ]
                _dom_gather = await asyncio.gather(*dom_tasks, return_exceptions=True)
                for _dom_result in _dom_gather:
                    if isinstance(_dom_result, Exception):
                        continue
                    try:
                        pname, vp, ref_prof, shop_prof = _dom_result
                    except (TypeError, ValueError):
                        continue
                    if isinstance(ref_prof, Exception) or isinstance(shop_prof, Exception):
                        continue
                    try:
                        dom_result = dom_comparator.compare(ref_prof, shop_prof)
                        dom_profiles[(pname, vp)] = (dom_result, ref_prof, shop_prof)
                    except Exception:
                        pass

            # Run all breakpoint comparisons concurrently — semaphore caps parallel AI calls
            _compare_sem = asyncio.Semaphore(6)

            async def _run_single_comparison(pair: dict):
                async with _compare_sem:
                    _out = os.path.join(
                        settings.storage_path, run_dir, "comparisons",
                        pair["page"], str(pair["breakpoint"])
                    )
                    try:
                        if pair["mode"] == "ai":
                            result = await comparison_engine.compare_ai_only(
                                shopify_path=pair["shopify_path"],
                                output_dir=_out,
                                page=pair["page"],
                                breakpoint=pair["breakpoint"],
                            )
                        else:
                            result = await comparison_engine.compare(
                                design_path=pair["design_path"],
                                shopify_path=pair["shopify_path"],
                                output_dir=_out,
                                page=pair["page"],
                                breakpoint=pair["breakpoint"],
                            )
                        return pair, result
                    except Exception:
                        return pair, None

            _publish_fn(run_id, "compare", progress=_overall_progress(done_phases, "compare", 0), message="Running AI comparisons in parallel")
            raw_compare_results = await asyncio.gather(*[_run_single_comparison(p) for p in capture_pairs])

            for idx, (pair, comp_result) in enumerate(raw_compare_results):
                if comp_result is None:
                    continue

                # ── Attach DOM score + compute hybrid score ────────────────
                dom_score_val: float | None = None
                dom_issues: list = []
                _dom_key = (pair["page"], pair["breakpoint"])
                if _dom_key in dom_profiles:
                    dom_comp_result, _, _ = dom_profiles[_dom_key]
                    dom_score_val = dom_comp_result.dom_score
                    dom_issues = dom_comp_result.issues
                    comp_result.dom_score = dom_score_val
                    comp_result.hybrid_score = comparison_engine.compute_hybrid_score(
                        comp_result.ssim_score, dom_score_val
                    )

                if pair["mode"] == "ai":
                    msg = f"AI analysis of {pair['page']} @{pair['breakpoint']}px"
                else:
                    dom_info = f" DOM={dom_score_val:.1f}" if dom_score_val is not None else ""
                    visual_pct = comp_result.ssim_score * 100
                    msg = f"Compared {pair['page']} @{pair['breakpoint']}px Visual={visual_pct:.1f}% Mismatch={comp_result.mismatch_pct:.1f}%{dom_info}"

                ai_status = AiAnalysisStatus.failed if comp_result.ai_status == "failed" else AiAnalysisStatus.completed
                db.add(Comparison(
                    qa_run_id=run_id,
                    page=pair["page"],
                    breakpoint=pair["breakpoint"],
                    ssim_score=comp_result.ssim_score,
                    dom_score=dom_score_val,
                    diff_image_path=comp_result.diff_image_path,
                    heatmap_path=comp_result.heatmap_path,
                    ai_analysis_status=ai_status,
                ))

                # ── Annotate issues: crop + red-border screenshot per issue ────
                all_issues_for_pair = list(comp_result.ai_issues) + list(dom_issues)
                annotated_rel_paths: list[str | None] = [None] * len(all_issues_for_pair)
                if all_issues_for_pair and pair.get("shopify_page_url"):
                    try:
                        from app.engines.issue_annotator import annotate_issues as _annotate
                        _ann_subdir = os.path.join(
                            run_dir, "issues", pair["page"], str(pair["breakpoint"])
                        )
                        _ann_abs_dir = os.path.join(settings.storage_path, _ann_subdir)
                        _ann_abs_paths = await _annotate(
                            shopify_url=pair["shopify_page_url"],
                            breakpoint=pair["breakpoint"],
                            issues=all_issues_for_pair,
                            full_page_path=pair["shopify_path"],
                            output_dir=_ann_abs_dir,
                            password=project.shopify_password,
                        )
                        # Convert absolute paths → relative paths from storage_path
                        _storage_base = settings.storage_path.rstrip("/")
                        for _pi, _ap in enumerate(_ann_abs_paths):
                            if _ap:
                                _rel = _ap.replace(_storage_base, "").lstrip("/\\")
                                annotated_rel_paths[_pi] = _rel
                    except Exception as _ann_err:
                        logger.warning("issue_annotator failed: %s", _ann_err)

                # Save AI visual issues (from screenshot comparison)
                for _ai_idx, ai_issue in enumerate(comp_result.ai_issues):
                    severity_str = ai_issue.get("severity", "minor").lower()
                    severity = _severity_map.get(severity_str, IssueSeverity.minor)
                    element_desc = ai_issue.get("element", "")
                    db.add(Issue(
                        qa_run_id=run_id,
                        page=pair["page"],
                        breakpoint=pair["breakpoint"],
                        type=IssueType.visual,
                        severity=severity,
                        description=ai_issue.get("description", "Visual issue detected"),
                        ai_suggestion=ai_issue.get("suggestion"),
                        element_selector=element_desc,
                        location_x=None,
                        location_y=None,
                        screenshot_path=annotated_rel_paths[_ai_idx],
                        status=IssueStatus.open,
                    ))

                # Save DOM style issues (from CSS property comparison) — stored separately
                _dom_offset = len(comp_result.ai_issues)
                for _dom_idx, dom_issue in enumerate(dom_issues):
                    severity_str = dom_issue.get("severity", "minor").lower()
                    severity = _severity_map.get(severity_str, IssueSeverity.minor)
                    element_desc = dom_issue.get("element", "")
                    db.add(Issue(
                        qa_run_id=run_id,
                        page=pair["page"],
                        breakpoint=pair["breakpoint"],
                        type=IssueType.visual,
                        severity=severity,
                        description=dom_issue.get("description", "Style mismatch detected"),
                        ai_suggestion=dom_issue.get("suggestion"),
                        element_selector=element_desc,
                        location_x=None,
                        location_y=None,
                        screenshot_path=annotated_rel_paths[_dom_offset + _dom_idx],
                        status=IssueStatus.open,
                    ))


                db.commit()
                _publish_fn(run_id, "compare", page=pair["page"],
                            breakpoint_val=pair["breakpoint"],
                            progress=_overall_progress(done_phases, "compare", (idx + 1) / max(total_comparisons, 1)),
                            message=msg)
            done_phases.append("compare")
            _publish_fn(run_id, "compare", progress=_overall_progress(done_phases, "", 0), message="Comparison complete")
        else:
            done_phases.append("compare")
            _publish_fn(run_id, "compare", progress=_overall_progress(done_phases, "", 0), message="QA test skipped")

        # ---- Phase 3b: Chromatic visual regression ──────────────────────────
        # Runs in design mode only when a Chromatic project token is configured.
        if (
            _should_run("qa", test_types)
            and has_design_source
            and test_mode != "ai"
            and settings.chromatic_project_token
        ):
            _publish_fn(run_id, "compare",
                        progress=_overall_progress(done_phases, "compare", 0),
                        message="Running Chromatic visual snapshot comparison")
            try:
                from app.engines.chromatic_engine import ChromaticEngine

                chromatic = ChromaticEngine(project_token=settings.chromatic_project_token)

                c_paths = list(dict.fromkeys(
                    (k if k.startswith("/") else f"/{k}") or "/"
                    for k in page_mappings
                ))

                c_result = await chromatic.compare(
                    shopify_url=project.shopify_url,
                    page_paths=c_paths,
                    project_name=project.name,
                )

                if c_result.status in ("passed", "failed"):
                    _publish_fn(
                        run_id, "compare",
                        progress=_overall_progress(done_phases, "compare", 0),
                        message=(
                            f"Chromatic: {c_result.snapshot_count} snapshots, "
                            f"{c_result.change_count} visual change"
                            f"{'s' if c_result.change_count != 1 else ''}"
                        ),
                    )

                    if c_result.change_count > 0:
                        suggestion = (
                            f"Review all visual changes in the Chromatic build: {c_result.build_url}"
                            if c_result.build_url
                            else "Open your Chromatic dashboard to review visual changes."
                        )
                        # One issue per named snapshot with changes
                        if c_result.snapshots:
                            for snap in c_result.snapshots:
                                if snap.status not in ("changed", "error"):
                                    continue
                                snap_page = (snap.name.replace(" > ", "/") or "home")[:500]
                                try:
                                    db.add(Issue(
                                        qa_run_id=run_id,
                                        page=snap_page,
                                        breakpoint=1440,
                                        type=IssueType.visual,
                                        severity=IssueSeverity.major,
                                        description=(
                                            f"Chromatic detected visual changes on "
                                            f"'{snap.name}' snapshot."
                                        ),
                                        ai_suggestion=suggestion,
                                        element_selector=None,
                                        location_x=None,
                                        location_y=None,
                                        screenshot_path=snap.url or None,
                                        status=IssueStatus.open,
                                    ))
                                    db.flush()
                                except Exception as _snap_exc:
                                    db.rollback()
                                    logger.warning(
                                        "Chromatic: failed to save snapshot issue: %s", _snap_exc
                                    )
                        else:
                            # No per-snapshot data — save a single summary issue
                            try:
                                db.add(Issue(
                                    qa_run_id=run_id,
                                    page="home",
                                    breakpoint=1440,
                                    type=IssueType.visual,
                                    severity=IssueSeverity.major,
                                    description=(
                                        f"Chromatic detected {c_result.change_count} visual "
                                        f"change{'s' if c_result.change_count != 1 else ''} "
                                        f"across {c_result.snapshot_count} "
                                        f"snapshot{'s' if c_result.snapshot_count != 1 else ''}."
                                    ),
                                    ai_suggestion=suggestion,
                                    element_selector=None,
                                    location_x=None,
                                    location_y=None,
                                    screenshot_path=None,
                                    status=IssueStatus.open,
                                ))
                                db.flush()
                            except Exception as _sum_exc:
                                db.rollback()
                                logger.warning(
                                    "Chromatic: failed to save summary issue: %s", _sum_exc
                                )

                    db.commit()
                else:
                    logger.warning(
                        "Chromatic build ended with status '%s': %s",
                        c_result.status, c_result.error,
                    )

            except Exception as _chromatic_exc:
                # Chromatic failure must never block the rest of the pipeline
                logger.warning("Chromatic integration error: %s", _chromatic_exc)

        # ---- Phase 4: Functional Tests ----
        if _should_run("functional", test_types):
            _publish_fn(run_id, "functional", progress=_overall_progress(done_phases, "functional", 0), message="Running functional tests")

            functional_engine = FunctionalEngine(storage_path=settings.storage_path)
            func_output_dir = os.path.join(settings.storage_path, run_dir, "functional")
            os.makedirs(func_output_dir, exist_ok=True)

            first_shopify_path = list(page_mappings.keys())[0]
            func_url = _build_page_url(project.shopify_url, first_shopify_path)
            first_page_name = first_shopify_path.strip("/") or "home"

            try:
                pw_page = await functional_engine._create_page(func_url)
                surface_results = await functional_engine.run_surface_tests(pw_page, func_output_dir)
                flow_results = await functional_engine.run_shopify_flows(pw_page, func_output_dir)

                for fr in surface_results + flow_results:
                    status = FunctionalTestStatus.pass_ if fr.status == "pass" else FunctionalTestStatus.fail
                    db.add(FunctionalTest(
                        qa_run_id=run_id,
                        test_name=fr.test_name,
                        status=status,
                        severity=fr.severity,
                        step_failed=str(fr.step_failed) if fr.step_failed is not None else None,
                        error_message=fr.error_message,
                        screenshot_path=fr.screenshot_path,
                    ))
                    if fr.status == "fail":
                        db.add(Issue(
                            qa_run_id=run_id,
                            page=first_page_name,
                            breakpoint=None,
                            type=IssueType.functional,
                            severity=IssueSeverity.major if fr.severity == "major" else IssueSeverity.minor,
                            description=fr.error_message or f"Functional test '{fr.test_name}' failed",
                            status=IssueStatus.open,
                        ))

                db.commit()
            except Exception:
                pass

            done_phases.append("functional")
            _publish_fn(run_id, "functional", progress=_overall_progress(done_phases, "", 0), message="Functional tests complete")
        else:
            done_phases.append("functional")
            _publish_fn(run_id, "functional", progress=_overall_progress(done_phases, "", 0), message="Functional test skipped")

        # ---- Phases 5+6+6b: Accessibility, Link Audit, SEO — all run concurrently per page ----
        from app.engines.seo_engine import SeoPerformanceEngine
        from app.models.seo_result import SeoResult as SeoResultModel, PerformanceResult

        accessibility_engine = AccessibilityEngine()
        link_engine = LinkAuditEngine()
        seo_engine = SeoPerformanceEngine()

        _publish_fn(run_id, "accessibility", progress=_overall_progress(done_phases, "accessibility", 0), message="Running ADA, link audit & SEO in parallel")

        async def _empty_list():
            return []

        async def _empty_none():
            return None

        combined_pages_tested: set[str] = set()
        for shopify_path in list(page_mappings.keys())[:3]:
            db.refresh(run)
            if run.status == RunStatus.cancelled:
                return

            page_name = _clean_page_name(shopify_path)
            if page_name in combined_pages_tested:
                continue
            combined_pages_tested.add(page_name)
            page_url = _build_page_url(project.shopify_url, shopify_path)

            _publish_fn(run_id, "accessibility",
                        progress=_overall_progress(done_phases, "accessibility", 0.3),
                        message=f"Checking {page_name}: ADA + links + SEO simultaneously")

            run_ada = _should_run("ada", test_types)
            run_link_audit = _should_run("link_audit", test_types)
            run_seo_or_perf = _should_run("seo", test_types) or _should_run("performance", test_types)

            acc_results, link_items, seo_result = await asyncio.gather(
                accessibility_engine.run_checks(page_url=page_url, password=project.shopify_password)
                if run_ada else _empty_list(),
                link_engine.audit_page(page_url=page_url, password=project.shopify_password)
                if run_link_audit else _empty_list(),
                seo_engine.analyze_page(page_url=page_url, password=project.shopify_password)
                if run_seo_or_perf else _empty_none(),
                return_exceptions=True,
            )

            if run_ada and not isinstance(acc_results, Exception):
                try:
                    for ar in acc_results:
                        db.add(AccessibilityResult(
                            qa_run_id=run_id, page=page_name,
                            test_name=ar.test_name, severity=ar.severity,
                            description=ar.description, wcag=ar.wcag,
                            element=ar.element, help_text=ar.help_text,
                        ))
                    db.commit()
                except Exception:
                    pass

            if run_link_audit and not isinstance(link_items, Exception):
                try:
                    for item in link_items:
                        db.add(LinkAudit(
                            qa_run_id=run_id, page=page_name,
                            element_type=item.element_type, text=item.text,
                            href=item.href, destination=item.destination,
                            is_external=item.is_external, is_mail_or_tel=item.is_mail_or_tel,
                            has_href=item.has_href, issue=item.issue, aria_label=item.aria_label,
                        ))
                    db.commit()
                except Exception:
                    pass

            if run_seo_or_perf:
                if isinstance(seo_result, Exception):
                    logger.warning("SEO engine failed for %s: %s", page_name, seo_result)
                else:
                    try:
                        if _should_run("seo", test_types):
                            for check in seo_result.seo_checks:
                                db.add(SeoResultModel(
                                    qa_run_id=run_id, page=page_name,
                                    test=check.test, label=check.label,
                                    passed=check.passed, value=check.value,
                                    recommendation=check.recommendation, severity=check.severity,
                                ))
                        if _should_run("performance", test_types):
                            perf = seo_result.performance
                            db.add(PerformanceResult(
                                qa_run_id=run_id, page=page_name,
                                load_time_ms=perf.load_time_ms, dom_ready_ms=perf.dom_ready_ms,
                                ttfb_ms=perf.ttfb_ms, total_resources=perf.total_resources,
                                total_size_bytes=perf.total_size_bytes,
                                js_count=perf.js_count, js_size_bytes=perf.js_size_bytes,
                                css_count=perf.css_count, css_size_bytes=perf.css_size_bytes,
                                img_count=perf.img_count, img_size_bytes=perf.img_size_bytes,
                                dom_nodes=perf.dom_nodes,
                                issues_json=json.dumps(perf.issues) if perf.issues else None,
                            ))
                        db.commit()
                    except Exception as e:
                        logger.error("Failed to save SEO/performance results for %s: %s", page_name, e)

        done_phases.append("accessibility")
        done_phases.append("link_audit")
        _publish_fn(run_id, "link_audit", progress=_overall_progress(done_phases, "", 0), message="ADA, link audit & SEO complete")

        # ---- Phase 7: Issue Matching ----
        if run.run_number > 1:
            _publish_fn(run_id, "matching", progress=_overall_progress(done_phases, "matching", 0), message="Matching issues with previous run")
            prev_run = (
                db.query(QaRun)
                .filter(QaRun.project_id == project.id, QaRun.run_number == run.run_number - 1)
                .first()
            )
            if prev_run:
                prev_issues = db.query(Issue).filter(Issue.qa_run_id == prev_run.id).all()
                curr_issues = db.query(Issue).filter(Issue.qa_run_id == run_id).all()

                def _to_dict(i):
                    return {
                        "id": i.id, "page": i.page, "breakpoint": i.breakpoint,
                        "type": i.type.value if i.type else None,
                        "element_selector": i.element_selector,
                        "location_x": i.location_x or 0, "location_y": i.location_y or 0,
                    }

                match_result = match_issues([_to_dict(i) for i in prev_issues], [_to_dict(i) for i in curr_issues])

                for so in match_result["still_open"]:
                    issue = db.query(Issue).filter(Issue.id == so["id"]).first()
                    if issue:
                        issue.status = IssueStatus.open
                        prev_info = so.get("_matched_prev", {})
                        if prev_info and prev_info.get("id"):
                            issue.original_issue_id = prev_info["id"]

                for new_issue in match_result["new"]:
                    issue = db.query(Issue).filter(Issue.id == new_issue["id"]).first()
                    if issue:
                        issue.status = IssueStatus.new

                db.commit()
            done_phases.append("matching")
            _publish_fn(run_id, "matching", progress=_overall_progress(done_phases, "", 0), message="Issue matching complete")
        else:
            done_phases.append("matching")

        # ---- Phase 8: Score ----
        _publish_fn(run_id, "scoring", progress=_overall_progress(done_phases, "scoring", 0), message="Calculating score")
        score = calculate_score(db, run_id)
        run.overall_score = score
        run.status = RunStatus.completed
        run.completed_at = datetime.now(timezone.utc).isoformat()
        db.commit()
        _publish_fn(run_id, "completed", progress=100.0, message=f"Run completed — Score: {score:.1f}/100")

    except Exception as exc:
        try:
            db.refresh(run)
            run.status = RunStatus.failed
            run.completed_at = datetime.now(timezone.utc).isoformat()
            db.commit()
        except Exception:
            pass
        _publish_fn(run_id, "failed", progress=0.0, message=str(exc))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------


@celery_app.task(name="run_qa_job")
def run_qa_job(
    run_id: int,
    partial_pages: Optional[list[str]] = None,
    test_mode: str = "design",
    test_types: Optional[list[str]] = None,
    reference_urls_override: Optional[list[str]] = None,
) -> dict:
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            _run_qa_job_async(
                run_id, partial_pages, test_mode,
                test_types=test_types,
                reference_urls_override=reference_urls_override,
            )
        )
    finally:
        loop.close()
    return {"run_id": run_id, "status": "dispatched"}


@celery_app.task(name="cleanup_old_runs")
def cleanup_old_runs() -> dict:
    import shutil
    from datetime import timedelta

    from app.config import settings
    from app.database import get_session_factory
    from app.models.qa_run import QaRun, RunStatus

    db = get_session_factory()()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    deleted = 0
    try:
        old_runs = (
            db.query(QaRun)
            .filter(QaRun.completed_at < cutoff, QaRun.status != RunStatus.running)
            .all()
        )
        for run in old_runs:
            run_dir = os.path.join(settings.storage_path, f"run_{run.id}")
            if os.path.isdir(run_dir):
                shutil.rmtree(run_dir, ignore_errors=True)
                deleted += 1
    finally:
        db.close()
    return {"deleted": deleted}
