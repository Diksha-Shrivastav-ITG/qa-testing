from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Optional

from app.workers.celery_app import celery_app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BREAKPOINTS = [375, 425, 768, 1024, 1280, 1440, 1920]


# ---------------------------------------------------------------------------
# Redis progress publisher
# ---------------------------------------------------------------------------


def publish_progress(
    run_id: int,
    step: str,
    page: str = "",
    breakpoint_val: int = 0,
    progress: float = 0.0,
    message: str = "",
) -> None:
    """Publish progress JSON to Redis channel ``qa_run:{run_id}``."""
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
        r.publish(f"qa_run:{run_id}", payload)
    except Exception:
        pass  # Non-critical; swallow errors so the pipeline keeps running


# ---------------------------------------------------------------------------
# Async orchestrator
# ---------------------------------------------------------------------------


async def _run_qa_job_async(
    run_id: int,
    partial_pages: Optional[list[str]] = None,
    *,
    _publish_fn=publish_progress,
) -> None:
    """Execute the full QA pipeline for a given run.

    Phases:
      1. Discovery  - auto-discover pages if project has no mappings
      2. Capture    - screenshot Shopify + source at all breakpoints
      3. Compare    - SSIM + AI analysis for each pair
      4. Functional - surface tests + Shopify flows
      5. Issue Matching - compare with previous run's issues
      6. Score      - calculate overall score, mark run completed
    """
    from app.config import settings
    from app.database import get_session_factory
    from app.engines.capture_engine import CaptureEngine
    from app.engines.comparison_engine import ComparisonEngine
    from app.engines.discovery_engine import DiscoveryEngine
    from app.engines.functional_engine import FunctionalEngine
    from app.models.capture import Capture, CaptureSource
    from app.models.comparison import AiAnalysisStatus, Comparison
    from app.models.functional_test import FunctionalTest, FunctionalTestStatus
    from app.models.issue import Issue, IssueSeverity, IssueStatus, IssueType
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

        run_dir = f"run_{run_id}"

        # ---- Phase 1: Discovery ----
        _publish_fn(run_id, "discovery", progress=0.0, message="Starting discovery")

        page_mappings: dict[str, str] = project.config.get("page_mappings", {})

        if not page_mappings:
            discovery = DiscoveryEngine()
            shopify_pages = await discovery.discover_pages(
                project.shopify_url, password=project.shopify_password
            )
            if project.source_type == SourceType.framer:
                source_pages = await discovery.discover_framer_pages(project.source_url)
            else:
                source_pages = shopify_pages  # Figma mapping handled differently
            page_mappings = discovery.auto_map(shopify_pages, source_pages)

        # Filter to partial pages if specified
        if partial_pages:
            page_mappings = {
                k: v for k, v in page_mappings.items() if k in partial_pages
            }

        if not page_mappings:
            # Nothing to test - still mark completed with score 0
            run.overall_score = 0.0
            run.status = RunStatus.completed
            run.completed_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            _publish_fn(run_id, "completed", progress=1.0, message="No pages to test")
            return

        _publish_fn(run_id, "discovery", progress=1.0, message=f"Discovered {len(page_mappings)} pages")

        # ---- Phase 2: Capture ----
        capture_engine = CaptureEngine(storage_path=settings.storage_path)
        total_captures = len(page_mappings) * len(BREAKPOINTS) * 2
        captured_count = 0
        capture_pairs: list[dict] = []  # {page, breakpoint, shopify_path, design_path}

        for shopify_path, source_path in page_mappings.items():
            # Check cancellation
            db.refresh(run)
            if run.status == RunStatus.cancelled:
                _publish_fn(run_id, "cancelled", progress=0.0, message="Run cancelled")
                return

            page_name = shopify_path.strip("/") or "home"

            # Capture Shopify
            shopify_url = project.shopify_url.rstrip("/") + shopify_path
            shopify_results = await capture_engine.capture_page(
                url=shopify_url,
                page_name=page_name,
                run_dir=run_dir,
                source="shopify",
                breakpoints=BREAKPOINTS,
                password=project.shopify_password,
            )

            for cr in shopify_results:
                captured_count += 1
                _publish_fn(
                    run_id, "capture", page=page_name,
                    breakpoint_val=cr.breakpoint,
                    progress=captured_count / total_captures,
                    message=f"Captured shopify {page_name} @{cr.breakpoint}",
                )
                if cr.status == "success":
                    capture = Capture(
                        qa_run_id=run_id,
                        source=CaptureSource.shopify,
                        page=page_name,
                        breakpoint=cr.breakpoint,
                        image_path=cr.image_path,
                    )
                    db.add(capture)

            # Capture design source
            source_url = project.source_url.rstrip("/") + source_path
            design_results = await capture_engine.capture_page(
                url=source_url,
                page_name=page_name,
                run_dir=run_dir,
                source="design",
                breakpoints=BREAKPOINTS,
                password=project.framer_password,
            )

            for dr in design_results:
                captured_count += 1
                _publish_fn(
                    run_id, "capture", page=page_name,
                    breakpoint_val=dr.breakpoint,
                    progress=captured_count / total_captures,
                    message=f"Captured design {page_name} @{dr.breakpoint}",
                )
                if dr.status == "success":
                    capture = Capture(
                        qa_run_id=run_id,
                        source=CaptureSource.design,
                        page=page_name,
                        breakpoint=dr.breakpoint,
                        image_path=dr.image_path,
                    )
                    db.add(capture)

            db.commit()

            # Build capture pairs for comparison
            shopify_by_bp = {r.breakpoint: r for r in shopify_results if r.status == "success"}
            design_by_bp = {r.breakpoint: r for r in design_results if r.status == "success"}

            for bp in BREAKPOINTS:
                if bp in shopify_by_bp and bp in design_by_bp:
                    capture_pairs.append(
                        {
                            "page": page_name,
                            "breakpoint": bp,
                            "shopify_path": shopify_by_bp[bp].image_path,
                            "design_path": design_by_bp[bp].image_path,
                        }
                    )

        # ---- Phase 3: Compare ----
        comparison_engine = ComparisonEngine(
            groq_api_key=settings.groq_api_key,
            storage_path=settings.storage_path,
        )
        total_comparisons = len(capture_pairs)

        for idx, pair in enumerate(capture_pairs):
            db.refresh(run)
            if run.status == RunStatus.cancelled:
                _publish_fn(run_id, "cancelled", progress=0.0, message="Run cancelled")
                return

            output_dir = os.path.join(
                settings.storage_path, run_dir, "comparisons", pair["page"], str(pair["breakpoint"])
            )

            try:
                comp_result = await comparison_engine.compare(
                    design_path=pair["design_path"],
                    shopify_path=pair["shopify_path"],
                    output_dir=output_dir,
                    page=pair["page"],
                    breakpoint=pair["breakpoint"],
                )
            except Exception:
                # On complete comparison failure, skip this pair
                continue

            ai_status = AiAnalysisStatus.completed
            if comp_result.ai_status == "failed":
                ai_status = AiAnalysisStatus.failed

            comparison = Comparison(
                qa_run_id=run_id,
                page=pair["page"],
                breakpoint=pair["breakpoint"],
                ssim_score=comp_result.ssim_score,
                diff_image_path=comp_result.diff_image_path,
                heatmap_path=comp_result.heatmap_path,
                ai_analysis_status=ai_status,
            )
            db.add(comparison)

            # Create issues from AI analysis
            _severity_map = {
                "critical": IssueSeverity.critical,
                "high": IssueSeverity.major,
                "medium": IssueSeverity.minor,
                "low": IssueSeverity.minor,
                "major": IssueSeverity.major,
                "minor": IssueSeverity.minor,
            }

            for ai_issue in comp_result.ai_issues:
                severity_str = ai_issue.get("severity", "minor").lower()
                severity = _severity_map.get(severity_str, IssueSeverity.minor)
                location = ai_issue.get("location", {})

                issue = Issue(
                    qa_run_id=run_id,
                    page=pair["page"],
                    breakpoint=pair["breakpoint"],
                    type=IssueType.visual,
                    severity=severity,
                    description=ai_issue.get("description", "Visual discrepancy detected"),
                    ai_suggestion=ai_issue.get("suggestion"),
                    element_selector=ai_issue.get("selector"),
                    location_x=location.get("x"),
                    location_y=location.get("y"),
                    status=IssueStatus.open,
                )
                db.add(issue)

            db.commit()

            _publish_fn(
                run_id, "compare", page=pair["page"],
                breakpoint_val=pair["breakpoint"],
                progress=(idx + 1) / total_comparisons,
                message=f"Compared {pair['page']} @{pair['breakpoint']} SSIM={comp_result.ssim_score:.3f}",
            )

        # ---- Phase 4: Functional Tests ----
        _publish_fn(run_id, "functional", progress=0.0, message="Starting functional tests")

        functional_engine = FunctionalEngine(storage_path=settings.storage_path)
        func_output_dir = os.path.join(settings.storage_path, run_dir, "functional")
        os.makedirs(func_output_dir, exist_ok=True)

        try:
            # Use the first Shopify page for functional tests
            first_shopify_path = list(page_mappings.keys())[0]
            func_url = project.shopify_url.rstrip("/") + first_shopify_path
            pw_page = await functional_engine._create_page(func_url)

            surface_results = await functional_engine.run_surface_tests(pw_page, func_output_dir)
            flow_results = await functional_engine.run_shopify_flows(pw_page, func_output_dir)

            all_func_results = surface_results + flow_results

            for fr in all_func_results:
                status = FunctionalTestStatus.pass_ if fr.status == "pass" else FunctionalTestStatus.fail
                ft = FunctionalTest(
                    qa_run_id=run_id,
                    test_name=fr.test_name,
                    status=status,
                    severity=fr.severity,
                    step_failed=str(fr.step_failed) if fr.step_failed is not None else None,
                    error_message=fr.error_message,
                    screenshot_path=fr.screenshot_path,
                )
                db.add(ft)

                # Create functional issues for failures
                if fr.status == "fail":
                    issue = Issue(
                        qa_run_id=run_id,
                        page=first_shopify_path.strip("/") or "home",
                        breakpoint=None,
                        type=IssueType.functional,
                        severity=IssueSeverity.major if fr.severity == "major" else IssueSeverity.minor,
                        description=fr.error_message or f"Functional test '{fr.test_name}' failed",
                        status=IssueStatus.open,
                    )
                    db.add(issue)

            db.commit()
        except Exception:
            pass  # Functional tests are non-blocking

        _publish_fn(run_id, "functional", progress=1.0, message="Functional tests complete")

        # ---- Phase 5: Issue Matching ----
        if run.run_number > 1:
            _publish_fn(run_id, "matching", progress=0.0, message="Matching issues with previous run")

            prev_run = (
                db.query(QaRun)
                .filter(
                    QaRun.project_id == project.id,
                    QaRun.run_number == run.run_number - 1,
                )
                .first()
            )

            if prev_run:
                prev_issues = db.query(Issue).filter(Issue.qa_run_id == prev_run.id).all()
                curr_issues = db.query(Issue).filter(Issue.qa_run_id == run_id).all()

                prev_dicts = [
                    {
                        "id": i.id,
                        "page": i.page,
                        "breakpoint": i.breakpoint,
                        "type": i.type.value if i.type else None,
                        "element_selector": i.element_selector,
                        "location_x": i.location_x or 0,
                        "location_y": i.location_y or 0,
                    }
                    for i in prev_issues
                ]
                curr_dicts = [
                    {
                        "id": i.id,
                        "page": i.page,
                        "breakpoint": i.breakpoint,
                        "type": i.type.value if i.type else None,
                        "element_selector": i.element_selector,
                        "location_x": i.location_x or 0,
                        "location_y": i.location_y or 0,
                    }
                    for i in curr_issues
                ]

                match_result = match_issues(prev_dicts, curr_dicts)

                # Update statuses based on matching
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

            _publish_fn(run_id, "matching", progress=1.0, message="Issue matching complete")

        # ---- Phase 6: Score ----
        _publish_fn(run_id, "scoring", progress=0.0, message="Calculating score")

        score = calculate_score(db, run_id)
        run.overall_score = score
        run.status = RunStatus.completed
        run.completed_at = datetime.now(timezone.utc).isoformat()
        db.commit()

        _publish_fn(run_id, "completed", progress=1.0, message=f"Run completed with score {score:.1f}")

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
def run_qa_job(run_id: int, partial_pages: Optional[list[str]] = None) -> dict:
    """Celery task entry point. Runs the async QA pipeline in an event loop."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run_qa_job_async(run_id, partial_pages))
    finally:
        loop.close()
    return {"run_id": run_id, "status": "dispatched"}


@celery_app.task(name="cleanup_old_runs")
def cleanup_old_runs() -> dict:
    """Delete screenshots for runs older than 90 days, keep DB metadata."""
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
