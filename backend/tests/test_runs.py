from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import auth_header

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_PAYLOAD = {
    "name": "Test Store",
    "shopify_url": "https://test.myshopify.com",
    "source_type": "framer",
    "source_url": "https://framer.com/projects/test",
}


def _create_project(client: TestClient, token: str) -> int:
    resp = client.post("/api/projects", json=PROJECT_PAYLOAD, headers=auth_header(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_start_run(client: TestClient, developer_token: str):
    """Start a new QA run → 201, run_number=1, status=running."""
    project_id = _create_project(client, developer_token)
    resp = client.post(
        f"/api/projects/{project_id}/runs",
        headers=auth_header(developer_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["run_number"] == 1
    assert body["status"] == "running"
    assert body["project_id"] == project_id
    assert "id" in body


def test_start_run_increments_number(client: TestClient, developer_token: str):
    """Cancel first run, start second → run_number=2."""
    project_id = _create_project(client, developer_token)

    # Start first run
    resp1 = client.post(
        f"/api/projects/{project_id}/runs",
        headers=auth_header(developer_token),
    )
    assert resp1.status_code == 201, resp1.text
    run_id = resp1.json()["id"]

    # Cancel first run
    cancel_resp = client.post(
        f"/api/runs/{run_id}/cancel",
        headers=auth_header(developer_token),
    )
    assert cancel_resp.status_code == 200, cancel_resp.text

    # Start second run
    resp2 = client.post(
        f"/api/projects/{project_id}/runs",
        headers=auth_header(developer_token),
    )
    assert resp2.status_code == 201, resp2.text
    body = resp2.json()
    assert body["run_number"] == 2


def test_concurrent_run_rejected(client: TestClient, developer_token: str):
    """Start run, try start another without cancelling → 409."""
    project_id = _create_project(client, developer_token)

    # Start first run
    resp1 = client.post(
        f"/api/projects/{project_id}/runs",
        headers=auth_header(developer_token),
    )
    assert resp1.status_code == 201, resp1.text

    # Attempt to start another run while one is still running
    resp2 = client.post(
        f"/api/projects/{project_id}/runs",
        headers=auth_header(developer_token),
    )
    assert resp2.status_code == 409, resp2.text


def test_list_runs(client: TestClient, developer_token: str):
    """Create 2 runs (cancel first between), list → total=2."""
    project_id = _create_project(client, developer_token)

    # Start first run
    resp1 = client.post(
        f"/api/projects/{project_id}/runs",
        headers=auth_header(developer_token),
    )
    assert resp1.status_code == 201, resp1.text
    run1_id = resp1.json()["id"]

    # Cancel first run
    cancel_resp = client.post(
        f"/api/runs/{run1_id}/cancel",
        headers=auth_header(developer_token),
    )
    assert cancel_resp.status_code == 200, cancel_resp.text

    # Start second run
    resp2 = client.post(
        f"/api/projects/{project_id}/runs",
        headers=auth_header(developer_token),
    )
    assert resp2.status_code == 201, resp2.text

    # List runs
    list_resp = client.get(
        f"/api/projects/{project_id}/runs",
        headers=auth_header(developer_token),
    )
    assert list_resp.status_code == 200, list_resp.text
    body = list_resp.json()
    assert body["total"] == 2


def test_get_run_detail(client: TestClient, developer_token: str):
    """Get run detail → 200."""
    project_id = _create_project(client, developer_token)
    start_resp = client.post(
        f"/api/projects/{project_id}/runs",
        headers=auth_header(developer_token),
    )
    assert start_resp.status_code == 201, start_resp.text
    run_id = start_resp.json()["id"]

    detail_resp = client.get(
        f"/api/runs/{run_id}",
        headers=auth_header(developer_token),
    )
    assert detail_resp.status_code == 200, detail_resp.text
    body = detail_resp.json()
    assert body["id"] == run_id
    assert body["project_id"] == project_id


def test_cancel_run(client: TestClient, developer_token: str):
    """Cancel run → 200, status=cancelled."""
    project_id = _create_project(client, developer_token)
    start_resp = client.post(
        f"/api/projects/{project_id}/runs",
        headers=auth_header(developer_token),
    )
    assert start_resp.status_code == 201, start_resp.text
    run_id = start_resp.json()["id"]

    cancel_resp = client.post(
        f"/api/runs/{run_id}/cancel",
        headers=auth_header(developer_token),
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    body = cancel_resp.json()
    assert body["status"] == "cancelled"
    assert body["completed_at"] is not None


def test_delete_run(client: TestClient, developer_token: str):
    """Cancel first run, then delete → 204."""
    project_id = _create_project(client, developer_token)
    start_resp = client.post(
        f"/api/projects/{project_id}/runs",
        headers=auth_header(developer_token),
    )
    assert start_resp.status_code == 201, start_resp.text
    run_id = start_resp.json()["id"]

    # Cancel first
    cancel_resp = client.post(
        f"/api/runs/{run_id}/cancel",
        headers=auth_header(developer_token),
    )
    assert cancel_resp.status_code == 200, cancel_resp.text

    # Delete
    del_resp = client.delete(
        f"/api/projects/{project_id}/runs/{run_id}",
        headers=auth_header(developer_token),
    )
    assert del_resp.status_code == 204, del_resp.text
