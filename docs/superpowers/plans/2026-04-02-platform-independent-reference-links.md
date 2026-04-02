# Platform-Independent Reference Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the app accept any URL as a design reference (Vercel, Webflow, static HTML, etc.) by treating all URLs as generic web pages, with Figma kept as a special case using its API.

**Architecture:** Add `website` to the `SourceType` enum. Auto-detect `source_type` from the URL on the backend (Figma URLs -> `figma`, everything else -> `website`). Remove the platform dropdown from the frontend. Rename `discover_framer_pages()` to `discover_source_pages()`. Wire up the existing `FigmaCapture` engine for Figma URLs. Remove `framer_password` support.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Alembic, PostgreSQL, Playwright, React/TypeScript, Tailwind CSS

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/app/utils/source_detect.py` | Auto-detect source type from URL, extract Figma file key |
| Create | `backend/tests/test_source_detect.py` | Tests for source detection utility |
| Create | `backend/alembic/versions/f6a7b8c9d0e1_add_website_source_type.py` | DB migration: add `website` enum value, drop `framer_password` |
| Modify | `backend/app/models/project.py` | Add `website` to enum, remove `framer_password` column |
| Modify | `backend/app/schemas/project.py` | Remove `source_type` from Create, remove `framer_password` |
| Modify | `backend/app/routers/projects.py` | Auto-detect source_type on create/update, generic discovery |
| Modify | `backend/app/engines/discovery_engine.py` | Rename `discover_framer_pages` -> `discover_source_pages` |
| Modify | `backend/app/workers/qa_tasks.py` | Generic capture for website/framer, Figma API capture |
| Modify | `backend/tests/test_projects.py` | Update tests for new schema (no source_type in payload) |
| Modify | `backend/tests/test_discovery_engine.py` | Update test for renamed method |
| Modify | `backend/tests/test_qa_tasks.py` | Update tests for new flow |
| Modify | `frontend/src/components/projects/ProjectForm.tsx` | Remove dropdown, generic URL field, conditional Figma token |

---

### Task 1: Source Detection Utility

**Files:**
- Create: `backend/app/utils/__init__.py`
- Create: `backend/app/utils/source_detect.py`
- Create: `backend/tests/test_source_detect.py`

- [ ] **Step 1: Create the utils package**

Create an empty `__init__.py`:

```python
# backend/app/utils/__init__.py
```

- [ ] **Step 2: Write failing tests for source detection**

Create `backend/tests/test_source_detect.py`:

```python
from __future__ import annotations

import pytest

from app.utils.source_detect import detect_source_type, extract_figma_file_key
from app.models.project import SourceType


# ---------------------------------------------------------------------------
# detect_source_type
# ---------------------------------------------------------------------------


def test_detect_none_when_url_is_none():
    assert detect_source_type(None) == SourceType.none


def test_detect_none_when_url_is_empty():
    assert detect_source_type("") == SourceType.none


def test_detect_none_when_url_is_whitespace():
    assert detect_source_type("   ") == SourceType.none


def test_detect_figma_design_url():
    url = "https://www.figma.com/design/ABC123xyz/MyDesign"
    assert detect_source_type(url) == SourceType.figma


def test_detect_figma_file_url():
    url = "https://figma.com/file/ABC123xyz/MyDesign"
    assert detect_source_type(url) == SourceType.figma


def test_detect_website_for_vercel():
    url = "https://my-project.vercel.app"
    assert detect_source_type(url) == SourceType.website


def test_detect_website_for_framer():
    url = "https://mysite.framer.app"
    assert detect_source_type(url) == SourceType.website


def test_detect_website_for_netlify():
    url = "https://mysite.netlify.app"
    assert detect_source_type(url) == SourceType.website


def test_detect_website_for_plain_html():
    url = "https://example.com/mockup.html"
    assert detect_source_type(url) == SourceType.website


def test_detect_website_for_webflow():
    url = "https://mysite.webflow.io"
    assert detect_source_type(url) == SourceType.website


# ---------------------------------------------------------------------------
# extract_figma_file_key
# ---------------------------------------------------------------------------


def test_extract_figma_file_key_design_url():
    url = "https://www.figma.com/design/ABC123xyz/MyDesign?node-id=0-1"
    assert extract_figma_file_key(url) == "ABC123xyz"


def test_extract_figma_file_key_file_url():
    url = "https://figma.com/file/XYZ789abc/Another"
    assert extract_figma_file_key(url) == "XYZ789abc"


def test_extract_figma_file_key_returns_none_for_non_figma():
    url = "https://example.com/design/ABC123"
    assert extract_figma_file_key(url) is None


def test_extract_figma_file_key_returns_none_for_empty():
    assert extract_figma_file_key("") is None


def test_extract_figma_file_key_board_url():
    url = "https://figma.com/board/DEF456ghi/MyBoard"
    assert extract_figma_file_key(url) is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_source_detect.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.utils.source_detect'`

- [ ] **Step 4: Implement source detection**

Create `backend/app/utils/source_detect.py`:

```python
from __future__ import annotations

import re

from app.models.project import SourceType


def detect_source_type(url: str | None) -> SourceType:
    """Auto-detect the source type from a URL.

    Returns SourceType.figma for Figma URLs, SourceType.website for any
    other valid URL, or SourceType.none if the URL is empty/missing.
    """
    if not url or not url.strip():
        return SourceType.none
    if "figma.com/" in url:
        return SourceType.figma
    return SourceType.website


def extract_figma_file_key(url: str) -> str | None:
    """Extract the Figma file key from a Figma URL.

    Supports:
      - https://figma.com/design/FILE_KEY/...
      - https://figma.com/file/FILE_KEY/...
      - https://www.figma.com/design/FILE_KEY/...

    Returns None if the URL doesn't match a known Figma pattern.
    """
    if not url:
        return None
    match = re.match(
        r"https?://(?:www\.)?figma\.com/(?:design|file)/([a-zA-Z0-9]+)",
        url,
    )
    return match.group(1) if match else None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_source_detect.py -v`
Expected: All 13 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/utils/__init__.py backend/app/utils/source_detect.py backend/tests/test_source_detect.py
git commit -m "feat: add source URL auto-detection utility"
```

---

### Task 2: Database Model & Migration

**Files:**
- Modify: `backend/app/models/project.py`
- Create: `backend/alembic/versions/f6a7b8c9d0e1_add_website_source_type.py`

- [ ] **Step 1: Update the SourceType enum and remove framer_password**

Edit `backend/app/models/project.py` — add `website` to the enum and remove the `framer_password` column:

```python
class SourceType(str, enum.Enum):
    website = "website"
    figma = "figma"
    framer = "framer"  # kept for backward compat, treated as website
    none = "none"
```

Remove this line from the `Project` class:

```python
    framer_password: Mapped[str | None] = mapped_column(String(1024), nullable=True)
```

- [ ] **Step 2: Create the Alembic migration**

Create `backend/alembic/versions/f6a7b8c9d0e1_add_website_source_type.py`:

```python
"""add website source type, drop framer_password

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-02 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'website' to sourcetype enum
    op.execute(sa.text("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'website'"))
    # Drop framer_password column
    op.drop_column("projects", "framer_password")


def downgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("framer_password", sa.String(1024), nullable=True),
    )
```

- [ ] **Step 3: Run existing tests to ensure model change doesn't break anything**

Run: `cd backend && python -m pytest tests/test_projects.py -v`
Expected: Tests may fail because `test_projects.py` still sends `source_type: "framer"`. That's expected — we fix those tests in Task 4.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/project.py backend/alembic/versions/f6a7b8c9d0e1_add_website_source_type.py
git commit -m "feat: add website source type enum, drop framer_password column"
```

---

### Task 3: API Schema Changes

**Files:**
- Modify: `backend/app/schemas/project.py`

- [ ] **Step 1: Update Pydantic schemas**

Edit `backend/app/schemas/project.py` to remove `source_type` and `framer_password` from `ProjectCreate`, remove `framer_password` from `ProjectUpdate`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.project import SourceType


class ProjectCreate(BaseModel):
    name: str
    shopify_url: str
    source_url: Optional[str] = None
    shopify_password: Optional[str] = None
    figma_token: Optional[str] = None
    pass_threshold: float = 90.0


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    shopify_url: Optional[str] = None
    source_url: Optional[str] = None
    shopify_password: Optional[str] = None
    figma_token: Optional[str] = None
    pass_threshold: Optional[float] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    shopify_url: str
    source_type: SourceType
    source_url: Optional[str] = None
    pass_threshold: float
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/project.py
git commit -m "feat: remove source_type and framer_password from API schemas"
```

---

### Task 4: Router Changes (Auto-Detection + Generic Discovery)

**Files:**
- Modify: `backend/app/routers/projects.py`
- Modify: `backend/tests/test_projects.py`

- [ ] **Step 1: Update test payloads to match new schema**

Edit `backend/tests/test_projects.py` — update `PROJECT_PAYLOAD` and all test payloads to remove `source_type`, and add tests for auto-detection:

```python
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


def test_create_project_pm_rejected(client: TestClient):
    """PM cannot create a project -> 403."""
    signup_resp = client.post(
        "/api/auth/signup",
        json={"email": "pm@example.com", "name": "PM User", "password": "pmpass123", "role": "pm"},
    )
    assert signup_resp.status_code == 201, signup_resp.text
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
```

- [ ] **Step 2: Run updated tests to verify they fail (schema mismatch)**

Run: `cd backend && python -m pytest tests/test_projects.py -v`
Expected: FAIL — router still expects `source_type` in payload

- [ ] **Step 3: Update the router to auto-detect source_type**

Edit `backend/app/routers/projects.py` — update `create_project` and `update_project` to use `detect_source_type`, and update `discover_project` for generic discovery:

```python
from __future__ import annotations

import asyncio
import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models.project import Project
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.utils.source_detect import detect_source_type

router = APIRouter(prefix="/api/projects", tags=["projects"])


def check_project_owner(project: Project, user: User) -> None:
    """Raise 403 if user is not admin and not the project owner."""
    if user.role.value != "admin" and project.created_by != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner or an admin can perform this action.",
        )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "developer")),
) -> ProjectResponse:
    project = Project(
        name=payload.name,
        shopify_url=payload.shopify_url,
        source_type=detect_source_type(payload.source_url),
        source_url=payload.source_url,
        shopify_password=payload.shopify_password,
        figma_token=payload.figma_token,
        pass_threshold=payload.pass_threshold,
        created_by=current_user.id,
        config={},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project  # type: ignore[return-value]


@router.get("", response_model=PaginatedResponse[ProjectResponse])
def list_projects(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> PaginatedResponse[ProjectResponse]:
    total = db.query(Project).count()
    offset = (page - 1) * per_page
    items = db.query(Project).offset(offset).limit(per_page).all()
    pages = math.ceil(total / per_page) if total > 0 else 1
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project  # type: ignore[return-value]


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    check_project_owner(project, current_user)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    # Re-derive source_type if source_url was updated
    if "source_url" in update_data:
        project.source_type = detect_source_type(project.source_url)

    db.commit()
    db.refresh(project)
    return project  # type: ignore[return-value]


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    check_project_owner(project, current_user)

    db.delete(project)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/{project_id}/discover")
def discover_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "developer")),
) -> dict:
    """Discover pages for both Shopify and source sites, auto-map them,
    persist mappings in project.config, and return the result."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    check_project_owner(project, current_user)

    from app.engines.discovery_engine import DiscoveryEngine
    from app.models.project import SourceType

    engine = DiscoveryEngine()

    async def _run_discovery() -> tuple[list[dict], list[dict]]:
        shopify_pages = await engine.discover_pages(
            project.shopify_url,
            password=project.shopify_password,
        )
        if project.source_type in (SourceType.website, SourceType.framer):
            source_pages = await engine.discover_source_pages(project.source_url)
        else:
            # For figma or none — no browser discovery
            source_pages = []
        return shopify_pages, source_pages

    try:
        shopify_pages, source_pages = asyncio.run(_run_discovery())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Discovery failed: {exc}",
        ) from exc

    mappings = engine.auto_map(shopify_pages, source_pages)

    # Persist mappings into project.config
    config: dict[str, Any] = dict(project.config or {})
    config["mappings"] = mappings
    project.config = config
    db.commit()
    db.refresh(project)

    return {
        "shopify_pages": shopify_pages,
        "source_pages": source_pages,
        "mappings": mappings,
    }


@router.get("/{project_id}/mappings")
def get_mappings(
    project_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict:
    """Return the stored page mappings for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return (project.config or {}).get("mappings", {})


@router.put("/{project_id}/mappings")
def update_mappings(
    project_id: int,
    payload: dict[str, str],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "developer")),
) -> dict:
    """Replace the stored page mappings for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    check_project_owner(project, current_user)

    config: dict[str, Any] = dict(project.config or {})
    config["mappings"] = payload
    project.config = config
    db.commit()
    db.refresh(project)
    return config["mappings"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_projects.py -v`
Expected: All tests PASS including the two new auto-detection tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/projects.py backend/app/schemas/project.py backend/tests/test_projects.py
git commit -m "feat: auto-detect source_type from URL in project endpoints"
```

---

### Task 5: Rename discover_framer_pages -> discover_source_pages

**Files:**
- Modify: `backend/app/engines/discovery_engine.py`
- Modify: `backend/tests/test_discovery_engine.py`

- [ ] **Step 1: Update the test to use the new method name**

Edit `backend/tests/test_discovery_engine.py` — change `discover_framer_pages` to `discover_source_pages` in the test at line 87-104:

Replace:

```python
async def test_discover_framer_pages():
    """discover_framer_pages should return internal links as {path, name} dicts."""
    engine = DiscoveryEngine()

    raw_links = [
        {"href": "https://mysite.framer.app/", "text": "Home"},
        {"href": "https://mysite.framer.app/about", "text": "About"},
        {"href": "https://mysite.framer.app/contact", "text": "Contact"},
    ]

    mock_page = _make_mock_page(raw_links)

    with patch.object(engine, "_create_page", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_page

        pages = await engine.discover_framer_pages("https://mysite.framer.app")
```

With:

```python
async def test_discover_source_pages():
    """discover_source_pages should return internal links as {path, name} dicts for any URL."""
    engine = DiscoveryEngine()

    raw_links = [
        {"href": "https://mysite.vercel.app/", "text": "Home"},
        {"href": "https://mysite.vercel.app/about", "text": "About"},
        {"href": "https://mysite.vercel.app/contact", "text": "Contact"},
    ]

    mock_page = _make_mock_page(raw_links)

    with patch.object(engine, "_create_page", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_page

        pages = await engine.discover_source_pages("https://mysite.vercel.app")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && python -m pytest tests/test_discovery_engine.py::test_discover_source_pages -v`
Expected: FAIL with `AttributeError: 'DiscoveryEngine' object has no attribute 'discover_source_pages'`

- [ ] **Step 3: Rename the method in discovery_engine.py**

Edit `backend/app/engines/discovery_engine.py` — rename `discover_framer_pages` to `discover_source_pages` at line 192:

Replace:

```python
    async def discover_framer_pages(self, framer_url: str) -> list[dict]:
        """Discover internal pages of a Framer site.

        Same approach as :meth:`discover_pages` but without Shopify-specific
        path filtering.
        """
        page = await self._create_page(framer_url)
```

With:

```python
    async def discover_source_pages(self, source_url: str) -> list[dict]:
        """Discover internal pages of any web-based source site.

        Same approach as :meth:`discover_pages` but without Shopify-specific
        path filtering. Works for any URL (Vercel, Webflow, Framer, static HTML, etc.).
        """
        page = await self._create_page(source_url)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_discovery_engine.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/discovery_engine.py backend/tests/test_discovery_engine.py
git commit -m "refactor: rename discover_framer_pages to discover_source_pages"
```

---

### Task 6: Update QA Tasks for Generic Capture + Figma Wiring

**Files:**
- Modify: `backend/app/workers/qa_tasks.py`
- Modify: `backend/tests/test_qa_tasks.py`

- [ ] **Step 1: Update test_qa_tasks.py to use website source_type**

Edit `backend/tests/test_qa_tasks.py` — in `_seed_project_and_run` at line 81, change `source_type=SourceType.framer` to `source_type=SourceType.website` and remove `framer_password` if present:

Replace:

```python
    project = Project(
        name="Test Shop",
        shopify_url="https://test.myshopify.com",
        source_type=SourceType.framer,
        source_url="https://test.framer.app",
        created_by=user.id,
        config=config or {"page_mappings": {"/": "/", "/about": "/about"}},
    )
```

With:

```python
    project = Project(
        name="Test Shop",
        shopify_url="https://test.myshopify.com",
        source_type=SourceType.website,
        source_url="https://test.vercel.app",
        created_by=user.id,
        config=config or {"page_mappings": {"/": "/", "/about": "/about"}},
    )
```

- [ ] **Step 2: Run tests to confirm they still pass (capture logic uses SourceType check)**

Run: `cd backend && python -m pytest tests/test_qa_tasks.py -v`
Expected: Tests may fail because the qa_tasks.py code still checks `SourceType.framer`. That's expected — we fix it next.

- [ ] **Step 3: Update qa_tasks.py Phase 1 (Discovery)**

Edit `backend/app/workers/qa_tasks.py` — replace the Phase 1 discovery logic at lines 246-252:

Replace:

```python
            if test_mode == "ai" or not has_design_source:
                # AI-only mode or no design source — map Shopify pages to themselves
                source_pages = shopify_pages
            elif project.source_type == SourceType.framer:
                source_pages = await discovery.discover_framer_pages(project.source_url)
            else:
                source_pages = shopify_pages  # Figma handled differently
```

With:

```python
            if test_mode == "ai" or not has_design_source:
                # AI-only mode or no design source — map Shopify pages to themselves
                source_pages = shopify_pages
            elif project.source_type in (SourceType.website, SourceType.framer):
                source_pages = await discovery.discover_source_pages(project.source_url)
            elif project.source_type == SourceType.figma:
                # Figma: use API to list frames, then map them as source pages
                from app.utils.source_detect import extract_figma_file_key
                from app.engines.figma_capture import FigmaCapture

                file_key = extract_figma_file_key(project.source_url or "")
                if file_key and project.figma_token:
                    figma = FigmaCapture(token=project.figma_token, storage_path=settings.storage_path)
                    frames = await figma.list_frames(file_key)
                    source_pages = [{"path": f"/{f['name'].lower().replace(' ', '-')}", "name": f["name"]} for f in frames]
                else:
                    source_pages = shopify_pages
            else:
                source_pages = shopify_pages
```

- [ ] **Step 4: Update qa_tasks.py Phase 2 (Capture) — remove framer_password, add Figma capture**

Edit `backend/app/workers/qa_tasks.py` — replace the design capture block at lines 334-354:

Replace:

```python
            else:
                # Capture Shopify + Design simultaneously
                source_url = (project.source_url or "").rstrip("/") + source_path
                shopify_results, design_results = await asyncio.gather(
                    capture_engine.capture_page(
                        url=shopify_url,
                        page_name=page_name,
                        run_dir=run_dir,
                        source="shopify",
                        breakpoints=BREAKPOINTS,
                        password=project.shopify_password,
                    ),
                    capture_engine.capture_page(
                        url=source_url,
                        page_name=page_name,
                        run_dir=run_dir,
                        source="design",
                        breakpoints=BREAKPOINTS,
                        password=project.framer_password,
                    ),
                )
```

With:

```python
            else:
                # Capture Shopify + Design simultaneously
                source_url = (project.source_url or "").rstrip("/") + source_path
                shopify_results, design_results = await asyncio.gather(
                    capture_engine.capture_page(
                        url=shopify_url,
                        page_name=page_name,
                        run_dir=run_dir,
                        source="shopify",
                        breakpoints=BREAKPOINTS,
                        password=project.shopify_password,
                    ),
                    capture_engine.capture_page(
                        url=source_url,
                        page_name=page_name,
                        run_dir=run_dir,
                        source="design",
                        breakpoints=BREAKPOINTS,
                    ),
                )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_qa_tasks.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/workers/qa_tasks.py backend/tests/test_qa_tasks.py
git commit -m "feat: generic browser capture for all URLs, wire up Figma API discovery"
```

---

### Task 7: Frontend — Remove Dropdown, Generic URL Field

**Files:**
- Modify: `frontend/src/components/projects/ProjectForm.tsx`

- [ ] **Step 1: Update ProjectForm.tsx**

Replace the entire file content of `frontend/src/components/projects/ProjectForm.tsx`:

```tsx
import { useState } from "react";

interface ProjectFormData {
  name: string;
  shopify_url: string;
  source_url?: string;
  shopify_password?: string;
  figma_token?: string;
}

interface ProjectFormProps {
  onSubmit: (data: ProjectFormData) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const ProjectForm = ({ onSubmit, onCancel, isLoading }: ProjectFormProps) => {
  const [form, setForm] = useState<ProjectFormData>({
    name: "",
    shopify_url: "",
    source_url: "",
    shopify_password: "",
    figma_token: "",
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const data: ProjectFormData = {
      name: form.name,
      shopify_url: form.shopify_url,
    };
    if (form.source_url) data.source_url = form.source_url;
    if (form.shopify_password) data.shopify_password = form.shopify_password;
    if (form.figma_token) data.figma_token = form.figma_token;
    onSubmit(data);
  };

  const isFigmaUrl = (form.source_url || "").includes("figma.com/");
  const hasSourceUrl = !!(form.source_url && form.source_url.trim());

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">
          New Project
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Project Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              name="name"
              value={form.name}
              onChange={handleChange}
              required
              placeholder="My Shopify Store"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Shopify URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Shopify URL <span className="text-red-500">*</span>
            </label>
            <input
              type="url"
              name="shopify_url"
              value={form.shopify_url}
              onChange={handleChange}
              required
              placeholder="https://mystore.myshopify.com"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Optional: Shopify Password */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Shopify Password{" "}
              <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="password"
              name="shopify_password"
              value={form.shopify_password}
              onChange={handleChange}
              placeholder="Password-protected store access"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Reference URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Reference URL{" "}
              <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="url"
              name="source_url"
              value={form.source_url}
              onChange={handleChange}
              placeholder="https://my-design.vercel.app"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            {!hasSourceUrl && (
              <p className="mt-1 text-xs text-gray-400">
                No reference — QA will use AI analysis to review your Shopify site
              </p>
            )}
            {hasSourceUrl && !isFigmaUrl && (
              <p className="mt-1 text-xs text-gray-400">
                Any live site URL works — Vercel, Webflow, Netlify, static HTML, etc.
              </p>
            )}
            {isFigmaUrl && (
              <p className="mt-1 text-xs text-gray-400">
                Figma design detected — provide a token below for API access
              </p>
            )}
          </div>

          {/* Figma Token — only shown when URL contains figma.com/ */}
          {isFigmaUrl && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Figma Token{" "}
                <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <input
                type="password"
                name="figma_token"
                value={form.figma_token}
                onChange={handleChange}
                placeholder="figd_..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}

          {/* Buttons */}
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={isLoading}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
            >
              {isLoading ? "Creating..." : "Create Project"}
            </button>
            <button
              type="button"
              onClick={onCancel}
              disabled={isLoading}
              className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-60 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ProjectForm;
```

- [ ] **Step 2: Verify the frontend compiles**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/projects/ProjectForm.tsx
git commit -m "feat: replace platform dropdown with generic reference URL field"
```

---

### Task 8: Run Full Test Suite & Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Run the Alembic migration (if database is available)**

Run: `cd backend && alembic upgrade head`
Expected: Migration applies successfully

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address test/build issues from platform-independent refactor"
```
