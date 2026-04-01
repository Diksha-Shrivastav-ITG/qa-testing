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
    config: dict = {}
    if payload.page_mappings:
        config["page_mappings"] = payload.page_mappings
        config["mappings"] = payload.page_mappings

    project = Project(
        name=payload.name,
        shopify_url=payload.shopify_url,
        source_type=payload.source_type,
        source_url=payload.source_url,
        shopify_password=payload.shopify_password,
        framer_password=payload.framer_password,
        figma_token=payload.figma_token,
        pass_threshold=payload.pass_threshold,
        created_by=current_user.id,
        config=config,
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

    # Handle page_mappings separately — stored in config, not a column
    page_mappings = update_data.pop("page_mappings", None)
    if page_mappings is not None:
        config = dict(project.config or {})
        config["page_mappings"] = page_mappings
        config["mappings"] = page_mappings
        project.config = config

    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project  # type: ignore[return-value]


# @router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
# def delete_project(
#     project_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ) -> None:
#     project = db.query(Project).filter(Project.id == project_id).first()
#     if project is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
#     check_project_owner(project, current_user)

#     db.delete(project)
#     db.commit()

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

    # Website type: mappings are manual — return stored mappings
    if project.source_type.value == "website":
        mappings = (project.config or {}).get("page_mappings", {})
        shopify_pages = [{"path": k, "name": k.strip("/") or "Homepage"} for k in mappings]
        return {
            "shopify_pages": shopify_pages,
            "source_pages": [],
            "mappings": mappings,
        }

    from app.engines.discovery_engine import DiscoveryEngine

    engine = DiscoveryEngine()

    async def _run_discovery() -> tuple[list[dict], list[dict]]:
        shopify_pages = await engine.discover_pages(
            project.shopify_url,
            password=project.shopify_password,
        )
        if project.source_type.value == "framer":
            source_pages = await engine.discover_framer_pages(project.source_url)
        else:
            # For figma or unknown source types, return empty list — no browser discovery
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
