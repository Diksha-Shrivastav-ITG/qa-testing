from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# Signup tests
# ---------------------------------------------------------------------------


def test_signup_developer(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/signup",
        json={"email": "alice@example.com", "name": "Alice", "password": "secret123", "role": "developer"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert data["name"] == "Alice"
    assert data["role"] == "developer"
    assert "id" in data


def test_signup_pm(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "name": "Bob", "password": "secret123", "role": "pm"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "pm"


def test_signup_admin_rejected(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/signup",
        json={"email": "hacker@example.com", "name": "Hacker", "password": "secret123", "role": "admin"},
    )
    assert resp.status_code == 400


def test_signup_duplicate_email(client: TestClient) -> None:
    payload = {"email": "dup@example.com", "name": "Dup", "password": "secret123", "role": "developer"}
    resp1 = client.post("/api/auth/signup", json=payload)
    assert resp1.status_code == 201
    resp2 = client.post("/api/auth/signup", json=payload)
    assert resp2.status_code == 400


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


def test_login_success(client: TestClient) -> None:
    client.post(
        "/api/auth/signup",
        json={"email": "carol@example.com", "name": "Carol", "password": "mypassword", "role": "developer"},
    )
    resp = client.post("/api/auth/login", json={"email": "carol@example.com", "password": "mypassword"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "developer"


def test_login_wrong_password(client: TestClient) -> None:
    client.post(
        "/api/auth/signup",
        json={"email": "dave@example.com", "name": "Dave", "password": "correct", "role": "developer"},
    )
    resp = client.post("/api/auth/login", json={"email": "dave@example.com", "password": "wrong"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Admin seeding test
# ---------------------------------------------------------------------------


def test_admin_seeded_on_startup(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"


# ---------------------------------------------------------------------------
# /api/users/me tests
# ---------------------------------------------------------------------------


def test_get_me(client: TestClient, developer_token: str) -> None:
    resp = client.get("/api/users/me", headers=auth_header(developer_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "dev@example.com"
    assert data["role"] == "developer"


def test_get_me_unauthorized(client: TestClient) -> None:
    resp = client.get("/api/users/me")
    assert resp.status_code == 401
