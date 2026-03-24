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
from app.models.issue import Issue
from app.models.project import Project
from app.models.qa_run import QaRun, RunStatus
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.qa_run import RunResponse
from app.services.auth_service import decode_token
from app.services.run_service import get_next_run_number

router = APIRouter(tags=["runs"])


def _dispatch_qa_task(run_id: int, partial_pages: Optional[list[str]] = None) -> None:
    """Dispatch the Celery QA task. Silently swallows errors (e.g. no broker)."""
    try:
        from app.workers.qa_tasks import run_qa_job

        run_qa_job.delay(run_id, partial_pages)
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
    _dispatch_qa_task(run.id, partial_pages)

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
