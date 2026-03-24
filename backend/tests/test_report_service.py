from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import auth_header


PROJECT_PAYLOAD = {
    "name": "Report Test Store",
    "shopify_url": "https://report-test.myshopify.com",
    "source_type": "framer",
    "source_url": "https://framer.com/projects/report-test",
}


def _setup_run_with_data(client: TestClient, token: str, db: Session) -> int:
    """Create a project + run + issues + functional tests. Returns run_id."""
    from app.models.functional_test import FunctionalTest, FunctionalTestStatus
    from app.models.issue import Issue, IssueSeverity, IssueStatus, IssueType

    resp = client.post("/api/projects", json=PROJECT_PAYLOAD, headers=auth_header(token))
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]

    resp = client.post(f"/api/projects/{project_id}/runs", headers=auth_header(token))
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]

    issue = Issue(
        qa_run_id=run_id,
        page="/home",
        breakpoint=1440,
        type=IssueType.visual,
        severity=IssueSeverity.critical,
        description="Critical layout shift",
        ai_suggestion="Fix the flex container",
        status=IssueStatus.open,
    )
    ft = FunctionalTest(
        qa_run_id=run_id,
        test_name="Add to cart flow",
        status=FunctionalTestStatus.fail,
        severity="critical",
        error_message="Button not found",
    )
    db.add(issue)
    db.add(ft)
    db.commit()

    return run_id


def test_generate_html_report(client: TestClient, developer_token: str, db: Session):
    """Generate HTML report → contains 'QA Report' and 'Critical'."""
    from app.services.report_service import generate_html_report

    run_id = _setup_run_with_data(client, developer_token, db)
    html = generate_html_report(db, run_id)

    assert "QA Report" in html
    assert "Critical" in html or "critical" in html
