from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.qa_run import QaRun
from app.models.user import User
from app.services.report_service import generate_html_report, generate_pdf_report

router = APIRouter(tags=["reports"])


def _get_run_or_404(db: Session, run_id: int) -> QaRun:
    run = db.query(QaRun).filter(QaRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get(
    "/api/runs/{run_id}/report/html",
    response_class=HTMLResponse,
)
def get_html_report(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Return an HTML QA report for the given run."""
    _get_run_or_404(db, run_id)
    html = generate_html_report(db, run_id)
    return HTMLResponse(content=html)


@router.get(
    "/api/runs/{run_id}/report/pdf",
)
def get_pdf_report(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Response:
    """Return a PDF QA report for the given run."""
    _get_run_or_404(db, run_id)
    try:
        pdf_bytes = generate_pdf_report(db, run_id)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=qa_report_run_{run_id}.pdf"},
    )
