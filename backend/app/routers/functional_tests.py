from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models.functional_test import FunctionalTest
from app.models.project import Project
from app.models.qa_run import QaRun
from app.models.user import User
from app.routers.projects import check_project_owner
from app.schemas.functional_test import FunctionalTestResponse

router = APIRouter(tags=["functional_tests"])


def _get_run_or_404(db: Session, run_id: int) -> QaRun:
    run = db.query(QaRun).filter(QaRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get(
    "/api/runs/{run_id}/functional",
    response_model=list[FunctionalTestResponse],
)
def list_functional_tests(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[FunctionalTestResponse]:
    """Return all functional test results for a run."""
    _get_run_or_404(db, run_id)
    tests = db.query(FunctionalTest).filter(FunctionalTest.qa_run_id == run_id).all()
    return tests  # type: ignore[return-value]


@router.put("/api/projects/{project_id}/flows")
def update_flows(
    project_id: int,
    payload: list[dict[str, Any]],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "developer")),
) -> dict:
    """Store custom flow definitions in project.config['custom_flows']."""
    project = _get_project_or_404(db, project_id)
    check_project_owner(project, current_user)

    config: dict[str, Any] = dict(project.config or {})
    config["custom_flows"] = payload
    project.config = config
    db.commit()
    db.refresh(project)
    return {"custom_flows": config["custom_flows"]}
