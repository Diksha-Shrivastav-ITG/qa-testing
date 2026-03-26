from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.issue import Issue
from app.models.qa_run import QaRun
from app.models.user import User
from app.schemas.issue import IssueResponse
from app.schemas.pagination import PaginatedResponse

router = APIRouter(tags=["issues"])


def _get_run_or_404(db: Session, run_id: int) -> QaRun:
    run = db.query(QaRun).filter(QaRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get(
    "/api/runs/{run_id}/issues",
    response_model=PaginatedResponse[IssueResponse],
)
def list_issues(
    run_id: int,
    severity: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    issue_page: Optional[str] = Query(default=None, alias="issue_page", description="Filter by page slug"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> PaginatedResponse[IssueResponse]:
    """List issues for a run with optional filters and pagination."""
    _get_run_or_404(db, run_id)

    query = db.query(Issue).filter(Issue.qa_run_id == run_id)

    if severity is not None:
        query = query.filter(Issue.severity == severity)
    if type is not None:
        query = query.filter(Issue.type == type)
    if issue_page is not None:
        query = query.filter(Issue.page == issue_page)

    total = query.count()
    offset = (page - 1) * per_page
    items = query.order_by(Issue.id.asc()).offset(offset).limit(per_page).all()
    pages = math.ceil(total / per_page) if total > 0 else 1

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get(
    "/api/runs/{run_id}/issues/{issue_id}",
    response_model=IssueResponse,
)
def get_issue(
    run_id: int,
    issue_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Get a single issue detail."""
    _get_run_or_404(db, run_id)

    issue = db.query(Issue).filter(Issue.id == issue_id, Issue.qa_run_id == run_id).first()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return issue  # type: ignore[return-value]
