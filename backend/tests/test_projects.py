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
    "source_url": "https://my-design.vercel.app",
}


def create_project(client: TestClient, token: str, payload: dict | None = None) -> dict:
    data = payload or PROJECT_PAYLOAD
    resp = client.post("/api/projects", json=data, headers=auth_header(token))
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_project(client: TestClient, developer_token: str):
    """Developer can create a project -> 201, source_type auto-detected as website."""
    resp = create_project(client, developer_token)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == PROJECT_PAYLOAD["name"]
    assert body["shopify_url"] == PROJECT_PAYLOAD["shopify_url"]
    assert body["source_type"] == "website"
    assert "id" in body
    assert "created_by" in body


def test_create_project_auto_detects_figma(client: TestClient, developer_token: str):
    """Figma URL auto-detected as source_type=figma."""
    payload = {
        "name": "Figma Project",
        "shopify_url": "https://test.myshopify.com",
        "source_url": "https://figma.com/design/ABC123/MyDesign",
        "figma_token": "figd_test_token",
    }
    resp = create_project(client, developer_token, payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source_type"] == "figma"


def test_create_project_no_source_url(client: TestClient, developer_token: str):
    """No source_url -> source_type=none."""
    payload = {
        "name": "AI Only",
        "shopify_url": "https://test.myshopify.com",
    }
    resp = create_project(client, developer_token, payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source_type"] == "none"


def test_create_project_pm_rejected(client: TestClient, admin_token: str):
    """PM cannot create a project -> 403."""
    # Sign up as developer first (only allowed role for self-signup)
    signup_resp = client.post(
        "/api/auth/signup",
        json={"email": "pm@example.com", "name": "PM User", "password": "pmpass123", "role": "developer"},
    )
    assert signup_resp.status_code == 201, signup_resp.text
    pm_user_id = signup_resp.json()["id"]

    # Admin promotes the user to PM role
    patch_resp = client.patch(
        f"/api/users/{pm_user_id}",
        json={"role": "pm"},
        headers=auth_header(admin_token),
    )
    assert patch_resp.status_code == 200, patch_resp.text

    login_resp = client.post("/api/auth/login", json={"email": "pm@example.com", "password": "pmpass123"})
    assert login_resp.status_code == 200, login_resp.text
    pm_token = login_resp.json()["access_token"]

    resp = create_project(client, pm_token)
    assert resp.status_code == 403, resp.text


def test_list_projects_paginated(client: TestClient, developer_token: str):
    """Create 5 projects, get page=1&per_page=2 -> 2 items, total=5, pages=3."""
    for i in range(5):
        payload = {
            "name": f"Store {i}",
            "shopify_url": f"https://store{i}.myshopify.com",
            "source_url": f"https://store{i}.vercel.app",
        }
        r = create_project(client, developer_token, payload)
        assert r.status_code == 201, r.text

    resp = client.get(
        "/api/projects?page=1&per_page=2",
        headers=auth_header(developer_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["per_page"] == 2
    assert body["pages"] == 3


def test_get_project(client: TestClient, developer_token: str):
    """Get single project by id -> 200."""
    create_resp = create_project(client, developer_token)
    assert create_resp.status_code == 201, create_resp.text
    project_id = create_resp.json()["id"]

    resp = client.get(f"/api/projects/{project_id}", headers=auth_header(developer_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == project_id
    assert body["name"] == PROJECT_PAYLOAD["name"]


def test_update_project_owner_only(client: TestClient, developer_token: str, admin_token: str):
    """Owner can update project -> 200; non-owner non-admin cannot -> 403."""
    create_resp = create_project(client, developer_token)
    assert create_resp.status_code == 201, create_resp.text
    project_id = create_resp.json()["id"]

    update_resp = client.put(
        f"/api/projects/{project_id}",
        json={"name": "Updated Store"},
        headers=auth_header(developer_token),
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["name"] == "Updated Store"

    signup_resp = client.post(
        "/api/auth/signup",
        json={"email": "other@example.com", "name": "Other Dev", "password": "otherpass123", "role": "developer"},
    )
    assert signup_resp.status_code == 201, signup_resp.text
    login_resp = client.post("/api/auth/login", json={"email": "other@example.com", "password": "otherpass123"})
    other_token = login_resp.json()["access_token"]

    forbidden_resp = client.put(
        f"/api/projects/{project_id}",
        json={"name": "Hacked"},
        headers=auth_header(other_token),
    )
    assert forbidden_resp.status_code == 403, forbidden_resp.text

    admin_resp = client.put(
        f"/api/projects/{project_id}",
        json={"name": "Admin Updated"},
        headers=auth_header(admin_token),
    )
    assert admin_resp.status_code == 200, admin_resp.text


def test_update_project_source_url_re_detects_type(client: TestClient, developer_token: str):
    """Updating source_url re-derives source_type."""
    create_resp = create_project(client, developer_token)
    assert create_resp.status_code == 201, create_resp.text
    project_id = create_resp.json()["id"]
    assert create_resp.json()["source_type"] == "website"

    # Update to Figma URL
    update_resp = client.put(
        f"/api/projects/{project_id}",
        json={"source_url": "https://figma.com/design/ABC123/Test"},
        headers=auth_header(developer_token),
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["source_type"] == "figma"

    # Update to clear source_url
    update_resp2 = client.put(
        f"/api/projects/{project_id}",
        json={"source_url": ""},
        headers=auth_header(developer_token),
    )
    assert update_resp2.status_code == 200, update_resp2.text
    assert update_resp2.json()["source_type"] == "none"


def test_delete_project(client: TestClient, developer_token: str):
    """Owner can delete project -> 204; project no longer exists -> 404."""
    create_resp = create_project(client, developer_token)
    assert create_resp.status_code == 201, create_resp.text
    project_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/projects/{project_id}", headers=auth_header(developer_token))
    assert del_resp.status_code == 204, del_resp.text

    get_resp = client.get(f"/api/projects/{project_id}", headers=auth_header(developer_token))
    assert get_resp.status_code == 404, get_resp.text
