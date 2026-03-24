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
        base_score = avg(SSIM) * 100
        penalty = critical*5 + major*2 + minor*0.5
        functional_penalty = failed_tests * 3
        score = max(0, base_score - penalty - functional_penalty)
    """
    from app.models.comparison import Comparison
    from app.models.functional_test import FunctionalTest
    from app.models.issue import Issue

    # Average SSIM across comparisons for this run
    avg_ssim = (
        db.query(func.avg(Comparison.ssim_score))
        .filter(Comparison.qa_run_id == run_id)
        .scalar()
    )
    base_score = float(avg_ssim or 0.0) * 100

    # Issue penalties
    from app.models.issue import Severity  # type: ignore[attr-defined]

    critical_count = (
        db.query(func.count(Issue.id))
        .filter(Issue.qa_run_id == run_id, Issue.severity == Severity.critical)
        .scalar()
        or 0
    )
    major_count = (
        db.query(func.count(Issue.id))
        .filter(Issue.qa_run_id == run_id, Issue.severity == Severity.major)
        .scalar()
        or 0
    )
    minor_count = (
        db.query(func.count(Issue.id))
        .filter(Issue.qa_run_id == run_id, Issue.severity == Severity.minor)
        .scalar()
        or 0
    )
    penalty = critical_count * 5 + major_count * 2 + minor_count * 0.5

    # Functional test penalty
    from app.models.functional_test import TestStatus  # type: ignore[attr-defined]

    failed_tests = (
        db.query(func.count(FunctionalTest.id))
        .filter(FunctionalTest.qa_run_id == run_id, FunctionalTest.status == TestStatus.fail)
        .scalar()
        or 0
    )
    functional_penalty = failed_tests * 3

    score = max(0.0, base_score - penalty - functional_penalty)
    return score
