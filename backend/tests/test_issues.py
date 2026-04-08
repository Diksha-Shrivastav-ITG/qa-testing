from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_PAYLOAD = {
    "name": "Issue Test Store",
    "shopify_url": "https://issue-test.myshopify.com",
    "source_type": "framer",
    "source_url": "https://framer.com/projects/issue-test",
}


def _setup_run_with_issues(client: TestClient, token: str, db: Session) -> tuple[int, int, int]:
    """Create a project + run + 2 issues (one critical, one minor). Returns (project_id, run_id, issue1_id)."""
    from app.models.issue import Issue, IssueSeverity, IssueStatus, IssueType
    from app.models.project import Project
    from app.models.qa_run import QaRun, RunStatus

    # Create project via API
    resp = client.post("/api/projects", json=PROJECT_PAYLOAD, headers=auth_header(token))
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]

    # Create run via API
    resp = client.post(f"/api/projects/{project_id}/runs", headers=auth_header(token))
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]

    # Add issues directly to the test DB
    issue1 = Issue(
        qa_run_id=run_id,
        page="/",
        breakpoint=1440,
        type=IssueType.visual,
        severity=IssueSeverity.critical,
        description="Critical layout shift on hero banner",
        ai_suggestion="Check flex container overflow",
        element_selector=".hero-banner",
        location_x=100,
        location_y=200,
        status=IssueStatus.open,
    )
    issue2 = Issue(
        qa_run_id=run_id,
        page="/product",
        breakpoint=375,
        type=IssueType.visual,
        severity=IssueSeverity.minor,
        description="Minor spacing issue on product card",
        status=IssueStatus.open,
    )
    db.add(issue1)
    db.add(issue2)
    db.commit()
    db.refresh(issue1)

    return project_id, run_id, issue1.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_list_issues(client: TestClient, developer_token: str, db: Session):
    """GET issues for run → total=2."""
    _project_id, run_id, _issue_id = _setup_run_with_issues(client, developer_token, db)

    resp = client.get(f"/api/runs/{run_id}/issues", headers=auth_header(developer_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


def test_filter_issues_by_severity(client: TestClient, developer_token: str, db: Session):
    """?severity=critical → total=1, severity matches."""
    _project_id, run_id, _issue_id = _setup_run_with_issues(client, developer_token, db)

    resp = client.get(
        f"/api/runs/{run_id}/issues",
        params={"severity": "critical"},
        headers=auth_header(developer_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["severity"] == "critical"


def test_get_issue_detail(client: TestClient, developer_token: str, db: Session):
    """Get single issue → 200, correct id."""
    _project_id, run_id, issue_id = _setup_run_with_issues(client, developer_token, db)

    resp = client.get(f"/api/runs/{run_id}/issues/{issue_id}", headers=auth_header(developer_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == issue_id
    assert body["qa_run_id"] == run_id
