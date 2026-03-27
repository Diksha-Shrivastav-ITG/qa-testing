from __future__ import annotations

import asyncio
import json
import math
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models.accessibility_result import AccessibilityResult
from app.models.capture import Capture
from app.models.issue import Issue
from app.models.link_audit import LinkAudit
from app.models.project import Project
from app.models.qa_run import QaRun, RunStatus
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.qa_run import RunResponse
from app.services.auth_service import decode_token
from app.services.run_service import get_next_run_number

router = APIRouter(tags=["runs"])


def _dispatch_qa_task(
    run_id: int,
    partial_pages: Optional[list[str]] = None,
    test_mode: str = "design",
) -> None:
    """Dispatch the Celery QA task. Silently swallows errors (e.g. no broker)."""
    try:
        from app.workers.qa_tasks import run_qa_job

        run_qa_job.delay(run_id, partial_pages, test_mode)
    except Exception:
        pass


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _get_run_or_404(db: Session, run_id: int) -> QaRun:
    run = db.query(QaRun).filter(QaRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _check_owner_or_admin(project: Project, user: User) -> None:
    if user.role.value != "admin" and project.created_by != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner or an admin can perform this action.",
        )


@router.post(
    "/api/projects/{project_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_run(
    project_id: int,
    partial: bool = Query(default=False),
    pages: Optional[str] = Query(default=None, description="Comma-separated page slugs"),
    test_mode: str = Query(default="design", description="'design' = compare vs Framer/Figma, 'ai' = AI-only analysis"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "developer")),
) -> RunResponse:
    """Start a new QA run for a project. Returns 409 if a run is already in progress."""
    project = _get_project_or_404(db, project_id)
    _check_owner_or_admin(project, current_user)

    # Check for an existing running run on this project
    existing = (
        db.query(QaRun)
        .filter(QaRun.project_id == project_id, QaRun.status == RunStatus.running)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A run is already in progress for this project.",
        )

    run_number = get_next_run_number(db, project_id)
    run = QaRun(
        project_id=project_id,
        status=RunStatus.running,
        run_number=run_number,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Dispatch Celery task to execute the QA run asynchronously
    partial_pages = [p.strip() for p in pages.split(",") if p.strip()] if pages else None
    _dispatch_qa_task(run.id, partial_pages, test_mode)

    return run  # type: ignore[return-value]


@router.get(
    "/api/projects/{project_id}/runs",
    response_model=PaginatedResponse[RunResponse],
)
def list_runs(
    project_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> PaginatedResponse[RunResponse]:
    """List all runs for a project with pagination."""
    _get_project_or_404(db, project_id)

    total = db.query(QaRun).filter(QaRun.project_id == project_id).count()
    offset = (page - 1) * per_page
    items = (
        db.query(QaRun)
        .filter(QaRun.project_id == project_id)
        .order_by(QaRun.id.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )
    pages = math.ceil(total / per_page) if total > 0 else 1
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/api/runs/{run_id}", response_model=RunResponse)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> RunResponse:
    """Get detail for a single run."""
    run = _get_run_or_404(db, run_id)
    return run  # type: ignore[return-value]


@router.post("/api/runs/{run_id}/cancel", response_model=RunResponse)
def cancel_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RunResponse:
    """Cancel a running QA run. Owner/admin only."""
    run = _get_run_or_404(db, run_id)
    project = _get_project_or_404(db, run.project_id)
    _check_owner_or_admin(project, current_user)

    run.status = RunStatus.cancelled
    run.completed_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(run)
    return run  # type: ignore[return-value]


@router.delete(
    "/api/projects/{project_id}/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_run(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a run. Cannot delete a running run. Owner/admin only."""
    _get_project_or_404(db, project_id)
    run = _get_run_or_404(db, run_id)

    if run.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found in this project")

    project = _get_project_or_404(db, run.project_id)
    _check_owner_or_admin(project, current_user)

    if run.status == RunStatus.running:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a run that is currently running.",
        )

    db.delete(run)
    db.commit()


@router.get("/api/runs/{run_id}/captures")
def get_run_captures(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list:
    """Return all captures for a run with image URLs."""
    _get_run_or_404(db, run_id)
    from app.config import settings
    captures = db.query(Capture).filter(Capture.qa_run_id == run_id).order_by(Capture.page, Capture.breakpoint).all()
    storage_base = settings.storage_path.rstrip("/")
    result = []
    for c in captures:
        image_url = None
        if c.image_path:
            rel = c.image_path.replace(storage_base, "").lstrip("/")
            image_url = f"/storage/{rel}"
        result.append({
            "id": c.id,
            "page": c.page,
            "breakpoint": c.breakpoint,
            "source": c.source.value,
            "image_url": image_url,
        })
    return result


@router.get("/api/runs/{run_id}/stream")
async def stream_run(
    run_id: int,
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream SSE events for a run. Validates JWT from query param."""
    # Validate the JWT token supplied as a query parameter
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    run = _get_run_or_404(db, run_id)

    async def _event_generator() -> AsyncGenerator[str, None]:
        event_id = 0
        channel = f"qa_run:{run_id}"

        try:
            import redis.asyncio as aioredis  # type: ignore[import]
            from app.config import settings

            r = aioredis.from_url(settings.redis_url)

            # Send cached latest progress immediately so returning users see current state
            cached = await r.get(f"qa_run:{run_id}:latest")
            if cached:
                event_id += 1
                cached_str = cached.decode() if isinstance(cached, bytes) else cached
                yield f"id: {event_id}\ndata: {cached_str}\n\n"
                # Check if already terminal
                try:
                    parsed_cached = json.loads(cached_str)
                    if parsed_cached.get("step") in ("completed", "failed"):
                        return
                except Exception:
                    pass

            pubsub = r.pubsub()
            await pubsub.subscribe(channel)

            try:
                async for raw_message in pubsub.listen():
                    if raw_message["type"] != "message":
                        continue
                    data_str = raw_message["data"]
                    if isinstance(data_str, bytes):
                        data_str = data_str.decode()

                    event_id += 1
                    yield f"id: {event_id}\ndata: {data_str}\n\n"

                    # Stop on terminal steps
                    try:
                        parsed: dict[str, Any] = json.loads(data_str)
                        step = parsed.get("step", "")
                        if step in ("completed", "failed"):
                            break
                    except (json.JSONDecodeError, AttributeError):
                        pass
            finally:
                await pubsub.unsubscribe(channel)
                await r.aclose()

        except Exception:
            # Redis unavailable — yield current run status and close
            event_id += 1
            data = json.dumps({"step": run.status, "run_id": run_id})
            yield f"id: {event_id}\ndata: {data}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/runs/{run_id}/compare/{prev_run_id}")
def compare_runs(
    run_id: int,
    prev_run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict:
    """Compare current run issues against a previous run using issue_matcher."""
    from app.services.issue_matcher import match_issues

    _get_run_or_404(db, run_id)
    _get_run_or_404(db, prev_run_id)

    def _issue_to_dict(issue: Issue) -> dict:
        return {
            "id": issue.id,
            "qa_run_id": issue.qa_run_id,
            "page": issue.page,
            "breakpoint": issue.breakpoint,
            "type": issue.type.value if hasattr(issue.type, "value") else str(issue.type),
            "severity": issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity),
            "description": issue.description,
            "ai_suggestion": issue.ai_suggestion,
            "element_selector": issue.element_selector,
            "location_x": issue.location_x if issue.location_x is not None else 0,
            "location_y": issue.location_y if issue.location_y is not None else 0,
            "status": issue.status.value if hasattr(issue.status, "value") else str(issue.status),
        }

    prev_issues_raw = db.query(Issue).filter(Issue.qa_run_id == prev_run_id).all()
    curr_issues_raw = db.query(Issue).filter(Issue.qa_run_id == run_id).all()

    prev_issues = [_issue_to_dict(i) for i in prev_issues_raw]
    curr_issues = [_issue_to_dict(i) for i in curr_issues_raw]

    result = match_issues(prev_issues, curr_issues)

    return {
        "resolved_count": len(result["resolved"]),
        "still_open_count": len(result["still_open"]),
        "new_count": len(result["new"]),
        "resolved": result["resolved"],
        "still_open": result["still_open"],
        "new": result["new"],
    }


@router.get("/api/runs/{run_id}/accessibility")
def get_run_accessibility(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list:
    """Return all ADA/accessibility results for a run."""
    _get_run_or_404(db, run_id)
    results = (
        db.query(AccessibilityResult)
        .filter(AccessibilityResult.qa_run_id == run_id)
        .order_by(AccessibilityResult.page, AccessibilityResult.severity)
        .all()
    )
    return [
        {
            "id": r.id,
            "page": r.page,
            "test_name": r.test_name,
            "severity": r.severity,
            "description": r.description,
            "wcag": r.wcag,
            "element": r.element,
            "help_text": r.help_text,
        }
        for r in results
    ]


@router.get("/api/runs/{run_id}/link-audit")
def get_run_link_audit(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list:
    """Return all link/button audit items for a run."""
    _get_run_or_404(db, run_id)
    items = (
        db.query(LinkAudit)
        .filter(LinkAudit.qa_run_id == run_id)
        .order_by(LinkAudit.page, LinkAudit.element_type)
        .all()
    )
    return [
        {
            "id": item.id,
            "page": item.page,
            "element_type": item.element_type,
            "text": item.text,
            "href": item.href,
            "destination": item.destination,
            "is_external": item.is_external,
            "is_mail_or_tel": item.is_mail_or_tel,
            "has_href": item.has_href,
            "issue": item.issue,
            "aria_label": item.aria_label,
        }
        for item in items
    ]


@router.get("/api/runs/{run_id}/seo")
def get_run_seo(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list:
    """Return SEO analysis results for a run."""
    from app.models.seo_result import SeoResult as SeoResultModel
    _get_run_or_404(db, run_id)
    results = db.query(SeoResultModel).filter(SeoResultModel.qa_run_id == run_id).order_by(SeoResultModel.page).all()
    return [
        {
            "id": r.id, "page": r.page, "test": r.test, "label": r.label,
            "passed": r.passed, "value": r.value,
            "recommendation": r.recommendation, "severity": r.severity,
        }
        for r in results
    ]


@router.get("/api/runs/{run_id}/performance")
def get_run_performance(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list:
    """Return performance metrics for a run."""
    import json as _json
    from app.models.seo_result import PerformanceResult
    _get_run_or_404(db, run_id)
    results = db.query(PerformanceResult).filter(PerformanceResult.qa_run_id == run_id).order_by(PerformanceResult.page).all()
    return [
        {
            "id": r.id, "page": r.page,
            "load_time_ms": r.load_time_ms, "dom_ready_ms": r.dom_ready_ms,
            "ttfb_ms": r.ttfb_ms, "total_resources": r.total_resources,
            "total_size_bytes": r.total_size_bytes,
            "js_count": r.js_count, "js_size_bytes": r.js_size_bytes,
            "css_count": r.css_count, "css_size_bytes": r.css_size_bytes,
            "img_count": r.img_count, "img_size_bytes": r.img_size_bytes,
            "dom_nodes": r.dom_nodes,
            "issues": _json.loads(r.issues_json) if r.issues_json else [],
        }
        for r in results
    ]


# ---------------------------------------------------------------------------
# AI Prompt Generation
# ---------------------------------------------------------------------------

from pydantic import BaseModel


class PromptGenerateRequest(BaseModel):
    issue_ids: list[int] = []
    acc_ids: list[int] = []
    project_name: str | None = None
    shopify_url: str | None = None


@router.post("/api/runs/{run_id}/generate-prompt")
async def generate_fix_prompt(
    run_id: int,
    body: PromptGenerateRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict:
    """Use Groq AI to generate a Claude Code fix prompt from selected issues."""
    from app.config import settings
    from app.models.accessibility_result import AccessibilityResult

    _get_run_or_404(db, run_id)

    # Gather selected issues
    issues_text = ""
    if body.issue_ids:
        issues = db.query(Issue).filter(Issue.id.in_(body.issue_ids)).all()
        for i, issue in enumerate(issues, 1):
            sev = issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity)
            issues_text += f"\n{i}. [{sev.upper()}] {issue.description}"
            if issue.element_selector:
                issues_text += f"\n   Element: {issue.element_selector}"
            if issue.ai_suggestion:
                issues_text += f"\n   Suggestion: {issue.ai_suggestion}"
            issues_text += f"\n   Page: {issue.page}"

    # Gather selected accessibility issues
    acc_text = ""
    if body.acc_ids:
        acc_items = db.query(AccessibilityResult).filter(AccessibilityResult.id.in_(body.acc_ids)).all()
        for i, a in enumerate(acc_items, 1):
            acc_text += f"\n{i}. [{a.severity.upper()}] {a.description}"
            if a.element:
                acc_text += f"\n   Element: {a.element}"
            if a.wcag:
                acc_text += f"\n   WCAG: {a.wcag}"
            acc_text += f"\n   Page: {a.page}"

    # Build the prompt for Groq
    groq_prompt = f"""You are an expert Shopify theme developer. A QA team has found issues on a Shopify store and needs you to generate a detailed, actionable prompt that another AI developer (Claude Code / VS Code Claude) can use to fix ALL the issues.

Store: {body.shopify_url or "Shopify store"}
Project: {body.project_name or "QA Project"}

=== QA ISSUES FOUND ===
{issues_text if issues_text else "(none)"}

=== ACCESSIBILITY ISSUES ===
{acc_text if acc_text else "(none)"}

Generate a comprehensive prompt that:
1. Lists every issue with the EXACT file to edit (e.g., sections/header.liquid, assets/theme.css)
2. Provides specific CSS/Liquid/JS code fixes for each issue
3. Groups fixes by file so the developer can work file-by-file
4. Includes before/after examples where helpful
5. Prioritizes critical issues first
6. Warns about potential side effects of each fix

Format the output as a ready-to-paste prompt for Claude Code. Start with a clear instruction line, then list all fixes. Use markdown formatting.

IMPORTANT: The prompt should be self-contained — the developer should be able to paste it directly into Claude Code and get all issues fixed without needing additional context."""

    # Call Groq AI
    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=settings.groq_api_key)
        response = await client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": groq_prompt}],
            temperature=0.3,
            max_tokens=4096,
        )
        ai_prompt = response.choices[0].message.content.strip()
    except Exception as exc:
        # Fallback: generate a basic prompt without AI
        ai_prompt = _fallback_prompt(body, issues_text, acc_text)

    return {"prompt": ai_prompt}


def _fallback_prompt(body: PromptGenerateRequest, issues_text: str, acc_text: str) -> str:
    """Generate a basic prompt without AI if Groq fails."""
    prompt = f"Fix the following QA issues on my Shopify store ({body.shopify_url or 'my store'}):\n"
    if issues_text:
        prompt += f"\n## QA Issues\n{issues_text}\n"
    if acc_text:
        prompt += f"\n## Accessibility Issues\n{acc_text}\n"
    prompt += "\nFor each issue, find the relevant Liquid/CSS/JS file and apply the fix. Explain what you changed and why."
    return prompt
