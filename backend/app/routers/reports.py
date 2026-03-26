from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.qa_run import QaRun
from app.services.auth_service import decode_token
from app.services.report_service import generate_html_report, generate_pdf_report

router = APIRouter(tags=["reports"])


def _get_run_or_404(db: Session, run_id: int) -> QaRun:
    run = db.query(QaRun).filter(QaRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _require_token(token: Optional[str]) -> None:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token required")
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


@router.get(
    "/api/runs/{run_id}/report/html",
    response_class=HTMLResponse,
)
def get_html_report(
    run_id: int,
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return an HTML QA report for the given run."""
    _require_token(token)
    _get_run_or_404(db, run_id)
    html = generate_html_report(db, run_id)
    return HTMLResponse(content=html)


@router.get(
    "/api/runs/{run_id}/report/pdf",
    response_class=HTMLResponse,
)
def get_pdf_report(
    run_id: int,
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return HTML report with auto-print triggered for PDF saving."""
    _require_token(token)
    _get_run_or_404(db, run_id)
    html = generate_html_report(db, run_id, auto_print=True)
    return HTMLResponse(content=html)
