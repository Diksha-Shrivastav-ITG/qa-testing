from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models.project import Project
from app.models.qa_run import QaRun, RunStatus
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.qa_run import RunResponse
from app.services.run_service import get_next_run_number

router = APIRouter(tags=["runs"])


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

    # TODO: dispatch Celery task to execute the QA run asynchronously

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
