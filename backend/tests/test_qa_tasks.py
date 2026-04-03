"""Tests for the QA job orchestrator (qa_tasks._run_qa_job_async).

All external engines are mocked so we can test orchestration logic
without Playwright, Groq, or a real Redis instance.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import Base
from app.models.capture import Capture, CaptureSource
from app.models.comparison import AiAnalysisStatus, Comparison
from app.models.functional_test import FunctionalTest, FunctionalTestStatus
from app.models.issue import Issue, IssueSeverity, IssueStatus, IssueType
from app.models.project import Project, SourceType
from app.models.qa_run import QaRun, RunStatus
from app.models.user import User

# Re-use the test DB infrastructure from conftest
from tests.conftest import _TestSessionLocal, _test_engine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BREAKPOINTS = [375, 768, 1440]


def _make_capture_result(page, bp, source, status="success"):
    from app.engines.capture_engine import CaptureResult

    return CaptureResult(
        page=page,
        breakpoint=bp,
        source=source,
        image_path=f"/fake/{source}/{page}/{bp}.png" if status == "success" else "",
        status=status,
    )


def _make_comparison_result(page, bp, ssim=0.92, ai_status="completed", ai_issues=None):
    from app.engines.comparison_engine import ComparisonResult

    return ComparisonResult(
        page=page,
        breakpoint=bp,
        ssim_score=ssim,
        diff_image_path=f"/fake/diff/{page}/{bp}.png",
        heatmap_path=f"/fake/heatmap/{page}/{bp}.png",
        ai_issues=ai_issues or [],
        ai_status=ai_status,
    )


def _make_functional_result(name, status="pass"):
    from app.engines.functional_engine import FunctionalResult

    return FunctionalResult(
        test_name=name,
        status=status,
        severity="major",
        error_message=f"{name} failed" if status == "fail" else None,
    )


def _seed_project_and_run(db, run_number=1, config=None):
    """Insert a User, Project, and QaRun, returning (project, run)."""
    user = User(
        email="worker@test.com",
        name="Worker",
        password_hash="x",
        role="developer",
    )
    db.add(user)
    db.flush()

    project = Project(
        name="Test Shop",
        shopify_url="https://test.myshopify.com",
        source_type=SourceType.website,
        source_url="https://test.vercel.app",
        created_by=user.id,
        config=config or {"page_mappings": {"/": "/", "/about": "/about"}},
    )
    db.add(project)
    db.flush()

    run = QaRun(
        project_id=project.id,
        status=RunStatus.running,
        run_number=run_number,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    db.refresh(project)
    return project, run


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    session = _TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# Patches target the source modules since _run_qa_job_async uses local imports
_PATCHES = {
    "cap": "app.engines.capture_engine.CaptureEngine",
    "comp": "app.engines.comparison_engine.ComparisonEngine",
    "func": "app.engines.functional_engine.FunctionalEngine",
    "disc": "app.engines.discovery_engine.DiscoveryEngine",
    "sf": "app.database.get_session_factory",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch(_PATCHES["func"])
@patch(_PATCHES["comp"])
@patch(_PATCHES["cap"])
@patch(_PATCHES["sf"])
def test_qa_job_completes_successfully(mock_sf, mock_cap_cls, mock_comp_cls, mock_func_cls, db):
    """Full happy-path: capture, compare, functional tests all succeed."""
    project, run = _seed_project_and_run(db)

    mock_sf.return_value = lambda: _TestSessionLocal()

    # --- CaptureEngine mock ---
    mock_capture = MagicMock()

    async def _fake_capture(url, page_name, run_dir, source, breakpoints, password=None, **kw):
        return [_make_capture_result(page_name, bp, source) for bp in breakpoints]

    mock_capture.capture_page = AsyncMock(side_effect=_fake_capture)
    mock_cap_cls.return_value = mock_capture

    # --- ComparisonEngine mock ---
    mock_comparison = MagicMock()

    async def _fake_compare(design_path, shopify_path, output_dir, page, breakpoint):
        return _make_comparison_result(
            page, breakpoint, ssim=0.90,
            ai_issues=[
                {
                    "severity": "medium",
                    "description": "Font mismatch",
                    "selector": ".header",
                    "suggestion": "Use Inter font",
                    "location": {"x": 100, "y": 200},
                }
            ],
        )

    mock_comparison.compare = AsyncMock(side_effect=_fake_compare)
    mock_comp_cls.return_value = mock_comparison

    # --- FunctionalEngine mock ---
    mock_functional = MagicMock()
    mock_pw_page = AsyncMock()
    mock_functional._create_page = AsyncMock(return_value=mock_pw_page)
    mock_functional.run_surface_tests = AsyncMock(return_value=[])
    mock_functional.run_shopify_flows = AsyncMock(
        return_value=[_make_functional_result("add_to_cart", "pass")]
    )
    mock_func_cls.return_value = mock_functional

    noop_publish = MagicMock()

    from app.workers.qa_tasks import _run_qa_job_async

    _run_async(_run_qa_job_async(run.id, _publish_fn=noop_publish))

    # ---- Assertions ----
    verify_db = _TestSessionLocal()
    try:
        updated_run = verify_db.query(QaRun).filter(QaRun.id == run.id).first()
        assert updated_run is not None
        assert updated_run.status == RunStatus.completed
        assert updated_run.overall_score is not None
        assert updated_run.completed_at is not None

        # 2 pages * 3 breakpoints * 2 sources = 12
        captures = verify_db.query(Capture).filter(Capture.qa_run_id == run.id).all()
        assert len(captures) == 12

        # 2 pages * 3 breakpoints = 6
        comparisons = verify_db.query(Comparison).filter(Comparison.qa_run_id == run.id).all()
        assert len(comparisons) == 6

        # Each comparison has 1 AI issue -> 6 issues
        issues = verify_db.query(Issue).filter(Issue.qa_run_id == run.id).all()
        assert len(issues) == 6

        # 1 functional test
        func_tests = verify_db.query(FunctionalTest).filter(FunctionalTest.qa_run_id == run.id).all()
        assert len(func_tests) == 1

        assert noop_publish.call_count > 0
    finally:
        verify_db.close()


@patch(_PATCHES["func"])
@patch(_PATCHES["comp"])
@patch(_PATCHES["cap"])
@patch(_PATCHES["sf"])
def test_qa_job_handles_capture_failure(mock_sf, mock_cap_cls, mock_comp_cls, mock_func_cls, db):
    """When capture fails for one page, the other page is still processed."""
    project, run = _seed_project_and_run(
        db, config={"page_mappings": {"/": "/", "/broken": "/broken"}}
    )

    mock_sf.return_value = lambda: _TestSessionLocal()

    mock_capture = MagicMock()

    async def _fake_capture(url, page_name, run_dir, source, breakpoints, password=None, **kw):
        if page_name == "broken":
            return [_make_capture_result(page_name, bp, source, status="capture_failed") for bp in breakpoints]
        return [_make_capture_result(page_name, bp, source) for bp in breakpoints]

    mock_capture.capture_page = AsyncMock(side_effect=_fake_capture)
    mock_cap_cls.return_value = mock_capture

    mock_comparison = MagicMock()

    async def _compare(design_path, shopify_path, output_dir, page, breakpoint):
        return _make_comparison_result(page, breakpoint)

    mock_comparison.compare = AsyncMock(side_effect=_compare)
    mock_comp_cls.return_value = mock_comparison

    mock_functional = MagicMock()
    mock_functional._create_page = AsyncMock(return_value=AsyncMock())
    mock_functional.run_surface_tests = AsyncMock(return_value=[])
    mock_functional.run_shopify_flows = AsyncMock(return_value=[])
    mock_func_cls.return_value = mock_functional

    noop_publish = MagicMock()

    from app.workers.qa_tasks import _run_qa_job_async

    _run_async(_run_qa_job_async(run.id, _publish_fn=noop_publish))

    verify_db = _TestSessionLocal()
    try:
        updated_run = verify_db.query(QaRun).filter(QaRun.id == run.id).first()
        assert updated_run.status == RunStatus.completed

        captures = verify_db.query(Capture).filter(Capture.qa_run_id == run.id).all()
        broken_captures = [c for c in captures if c.page == "broken"]
        assert len(broken_captures) == 0

        home_captures = [c for c in captures if c.page == "home"]
        assert len(home_captures) == 6

        comparisons = verify_db.query(Comparison).filter(Comparison.qa_run_id == run.id).all()
        assert len(comparisons) == 3
    finally:
        verify_db.close()


@patch(_PATCHES["func"])
@patch(_PATCHES["comp"])
@patch(_PATCHES["cap"])
@patch(_PATCHES["sf"])
def test_qa_job_handles_groq_failure(mock_sf, mock_cap_cls, mock_comp_cls, mock_func_cls, db):
    """When Groq AI analysis fails, SSIM-only results are saved with ai_status=failed."""
    project, run = _seed_project_and_run(
        db, config={"page_mappings": {"/": "/"}}
    )

    mock_sf.return_value = lambda: _TestSessionLocal()

    mock_capture = MagicMock()

    async def _fake_capture(url, page_name, run_dir, source, breakpoints, password=None, **kw):
        return [_make_capture_result(page_name, bp, source) for bp in breakpoints]

    mock_capture.capture_page = AsyncMock(side_effect=_fake_capture)
    mock_cap_cls.return_value = mock_capture

    mock_comparison = MagicMock()

    async def _compare(design_path, shopify_path, output_dir, page, breakpoint):
        return _make_comparison_result(page, breakpoint, ssim=0.85, ai_status="failed", ai_issues=[])

    mock_comparison.compare = AsyncMock(side_effect=_compare)
    mock_comp_cls.return_value = mock_comparison

    mock_functional = MagicMock()
    mock_functional._create_page = AsyncMock(return_value=AsyncMock())
    mock_functional.run_surface_tests = AsyncMock(return_value=[])
    mock_functional.run_shopify_flows = AsyncMock(return_value=[])
    mock_func_cls.return_value = mock_functional

    noop_publish = MagicMock()

    from app.workers.qa_tasks import _run_qa_job_async

    _run_async(_run_qa_job_async(run.id, _publish_fn=noop_publish))

    verify_db = _TestSessionLocal()
    try:
        updated_run = verify_db.query(QaRun).filter(QaRun.id == run.id).first()
        assert updated_run.status == RunStatus.completed

        comparisons = verify_db.query(Comparison).filter(Comparison.qa_run_id == run.id).all()
        assert len(comparisons) == 3

        for comp in comparisons:
            assert comp.ai_analysis_status == AiAnalysisStatus.failed

        issues = verify_db.query(Issue).filter(Issue.qa_run_id == run.id).all()
        assert len(issues) == 0
    finally:
        verify_db.close()


@patch(_PATCHES["func"])
@patch(_PATCHES["comp"])
@patch(_PATCHES["cap"])
@patch(_PATCHES["sf"])
def test_per_page_reference_url_is_used_for_non_homepage(
    mock_sf, mock_cap_cls, mock_comp_cls, mock_func_cls, db
):
    """When page_reference_urls contains an entry for a non-homepage path,
    the design capture uses that URL directly instead of project.source_url + path."""
    project, run = _seed_project_and_run(
        db,
        config={"page_mappings": {"/": "/", "/collections/summer": "/collections/summer"}},
    )
    mock_sf.return_value = lambda: _TestSessionLocal()

    captured_urls: list[tuple[str, str]] = []  # (source, url)

    mock_capture = MagicMock()

    async def _fake_capture(url, page_name, run_dir, source, breakpoints, password=None, **kw):
        captured_urls.append((source, url))
        return [_make_capture_result(page_name, bp, source) for bp in breakpoints]

    mock_capture.capture_page = AsyncMock(side_effect=_fake_capture)
    mock_cap_cls.return_value = mock_capture

    mock_comparison = MagicMock()

    async def _compare(design_path, shopify_path, output_dir, page, breakpoint):
        return _make_comparison_result(page, breakpoint)

    mock_comparison.compare = AsyncMock(side_effect=_compare)
    mock_comp_cls.return_value = mock_comparison

    mock_functional = MagicMock()
    mock_functional._create_page = AsyncMock(return_value=AsyncMock())
    mock_functional.run_surface_tests = AsyncMock(return_value=[])
    mock_functional.run_shopify_flows = AsyncMock(return_value=[])
    mock_func_cls.return_value = mock_functional

    noop_publish = MagicMock()

    from app.workers.qa_tasks import _run_qa_job_async

    _run_async(
        _run_qa_job_async(
            run.id,
            _publish_fn=noop_publish,
            page_reference_urls={
                "/collections/summer": "https://live-site.com/collections/summer"
            },
        )
    )

    design_urls = [url for source, url in captured_urls if source == "design"]
    # The reference URL provided must be used directly — NOT project.source_url + path
    assert any("live-site.com/collections/summer" in url for url in design_urls), (
        f"Expected live-site.com/collections/summer in design captures, got: {design_urls}"
    )
    # project.source_url is https://test.vercel.app — it must NOT appear for collections
    assert not any(
        "test.vercel.app/collections" in url for url in design_urls
    ), f"Wrongly used project.source_url for collections: {design_urls}"


@patch(_PATCHES["func"])
@patch(_PATCHES["comp"])
@patch(_PATCHES["cap"])
@patch(_PATCHES["sf"])
def test_non_homepage_without_reference_url_uses_ai_only(
    mock_sf, mock_cap_cls, mock_comp_cls, mock_func_cls, db
):
    """When a non-homepage path has no entry in page_reference_urls,
    that page is captured with shopify source only (AI-only mode)."""
    project, run = _seed_project_and_run(
        db,
        config={"page_mappings": {"/": "/", "/collections/summer": "/collections/summer"}},
    )
    mock_sf.return_value = lambda: _TestSessionLocal()

    captured_sources_by_page: dict[str, set[str]] = {}

    mock_capture = MagicMock()

    async def _fake_capture(url, page_name, run_dir, source, breakpoints, password=None, **kw):
        captured_sources_by_page.setdefault(page_name, set()).add(source)
        return [_make_capture_result(page_name, bp, source) for bp in breakpoints]

    mock_capture.capture_page = AsyncMock(side_effect=_fake_capture)
    mock_cap_cls.return_value = mock_capture

    mock_comparison = MagicMock()

    async def _compare_ai(shopify_path, output_dir, page, breakpoint):
        return _make_comparison_result(page, breakpoint, ssim=0.0)

    mock_comparison.compare_ai_only = AsyncMock(side_effect=_compare_ai)
    mock_comp_cls.return_value = mock_comparison

    mock_functional = MagicMock()
    mock_functional._create_page = AsyncMock(return_value=AsyncMock())
    mock_functional.run_surface_tests = AsyncMock(return_value=[])
    mock_functional.run_shopify_flows = AsyncMock(return_value=[])
    mock_func_cls.return_value = mock_functional

    noop_publish = MagicMock()

    from app.workers.qa_tasks import _run_qa_job_async

    _run_async(
        _run_qa_job_async(
            run.id,
            _publish_fn=noop_publish,
            page_reference_urls={},  # empty — no reference URL for /collections/summer
        )
    )

    # Homepage ("/") → page_name "home" — should have BOTH shopify and design captures
    assert "shopify" in captured_sources_by_page.get("home", set())
    assert "design" in captured_sources_by_page.get("home", set())

    # Collections page → page_name "collections/summer" — shopify only (no reference URL given)
    collections_page = "collections/summer"
    assert "shopify" in captured_sources_by_page.get(collections_page, set()), (
        f"Expected shopify capture for {collections_page}"
    )
    assert "design" not in captured_sources_by_page.get(collections_page, set()), (
        f"Unexpected design capture for {collections_page} — no reference URL was provided"
    )
