from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# Use an in-memory SQLite database for tests
SQLITE_URL = "sqlite:///./test.db"

_test_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop them after."""
    # Import all models so their tables are registered on Base.metadata
    import app.models.user  # noqa: F401
    import app.models.project  # noqa: F401
    import app.models.qa_run  # noqa: F401
    import app.models.capture  # noqa: F401
    import app.models.comparison  # noqa: F401
    import app.models.issue  # noqa: F401
    import app.models.functional_test  # noqa: F401

    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture
def db():
    """Yield a test database session."""
    session = _TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _override_get_db():
    session = _TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """Return a TestClient with the DB dependency overridden to use SQLite."""
    from unittest.mock import patch

    app.dependency_overrides[get_db] = _override_get_db
    with patch("app.routers.runs._dispatch_qa_task"):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    app.dependency_overrides.clear()


@pytest.fixture
def developer_token(client: TestClient) -> str:
    """Sign up a developer and return their JWT."""
    resp = client.post(
        "/api/auth/signup",
        json={"email": "dev@example.com", "name": "Dev User", "password": "devpass123", "role": "developer"},
    )
    assert resp.status_code == 201, resp.text
    login_resp = client.post("/api/auth/login", json={"email": "dev@example.com", "password": "devpass123"})
    assert login_resp.status_code == 200, login_resp.text
    return login_resp.json()["access_token"]


@pytest.fixture
def admin_token(client: TestClient) -> str:
    """Return a JWT for the seeded admin user."""
    from app.config import settings

    login_resp = client.post(
        "/api/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert login_resp.status_code == 200, login_resp.text
    return login_resp.json()["access_token"]


def auth_header(token: str) -> dict:
    """Return an Authorization header dict for a given token."""
    return {"Authorization": f"Bearer {token}"}
