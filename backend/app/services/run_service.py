from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.qa_run import QaRun


def get_next_run_number(db: Session, project_id: int) -> int:
    """Return max run_number + 1 for the given project. Returns 1 if no runs exist."""
    max_run = db.query(func.max(QaRun.run_number)).filter(QaRun.project_id == project_id).scalar()
    return (max_run or 0) + 1


def calculate_score(db: Session, run_id: int) -> float:
    """Calculate overall score for a run.

    Formula:
        AI mode:     base = 100
        Design mode: base = avg(SSIM) * 100
        penalty = critical*5 + major*2 + minor*0.5
        functional_penalty = failed_tests * 3
        score = max(0, base - penalty - functional_penalty)
    """
    from app.models.comparison import Comparison
    from app.models.functional_test import FunctionalTest, FunctionalTestStatus
    from app.models.issue import Issue, IssueSeverity

    run = db.query(QaRun).filter(QaRun.id == run_id).first()
    test_mode = run.test_mode if run else "design"

    # Average SSIM across comparisons for this run
    avg_ssim = (
        db.query(func.avg(Comparison.ssim_score))
        .filter(Comparison.qa_run_id == run_id)
        .scalar()
    )

    # In AI mode or when no valid SSIM data, start from 100
    if test_mode == "ai" or avg_ssim is None or float(avg_ssim) < 0.01:
        base_score = 100.0
    else:
        base_score = float(avg_ssim) * 100

    # Issue penalties
    critical_count = (
        db.query(func.count(Issue.id))
        .filter(Issue.qa_run_id == run_id, Issue.severity == IssueSeverity.critical)
        .scalar() or 0
    )
    major_count = (
        db.query(func.count(Issue.id))
        .filter(Issue.qa_run_id == run_id, Issue.severity == IssueSeverity.major)
        .scalar() or 0
    )
    minor_count = (
        db.query(func.count(Issue.id))
        .filter(Issue.qa_run_id == run_id, Issue.severity == IssueSeverity.minor)
        .scalar() or 0
    )
    penalty = critical_count * 5 + major_count * 2 + minor_count * 0.5

    # Functional test penalty
    failed_tests = (
        db.query(func.count(FunctionalTest.id))
        .filter(FunctionalTest.qa_run_id == run_id, FunctionalTest.status == FunctionalTestStatus.fail)
        .scalar() or 0
    )
    functional_penalty = failed_tests * 3

    score = max(0.0, base_score - penalty - functional_penalty)
    return round(score, 1)
