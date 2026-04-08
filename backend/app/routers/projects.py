from __future__ import annotations

import asyncio
import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models.project import Project, SourceType
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
    # Auto-detect platform from source_url if source_type not explicitly set
    resolved_type = payload.source_type
    if resolved_type == "none" and payload.source_url:
        from app.engines.platform_detector import detect_platform
        resolved_type = detect_platform(payload.source_url)

    # Build initial config — store explicit page pairs if provided
    config: dict[str, Any] = {}
    if payload.page_pairs:
        config["page_pairs"] = [
            {"source_path": pp.source_path, "shopify_path": pp.shopify_path}
            for pp in payload.page_pairs
        ]

    project = Project(
        name=payload.name,
        shopify_url=payload.shopify_url,
        source_type=resolved_type,
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
    return ProjectResponse.from_orm_with_pairs(project)


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
        items=[ProjectResponse.from_orm_with_pairs(p) for p in items],
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
    return ProjectResponse.from_orm_with_pairs(project)


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

    # Handle page_pairs separately — stored in project.config, not a direct column
    new_pairs = update_data.pop("page_pairs", None)
    if new_pairs is not None:
        current_config = dict(project.config or {})
        current_config["page_pairs"] = [
            {"source_path": pp["source_path"], "shopify_path": pp["shopify_path"]}
            for pp in new_pairs
        ]
        project.config = current_config

    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return ProjectResponse.from_orm_with_pairs(project)


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
    """Discover pages for both Shopify and the design source, auto-map them,
    persist the mappings in project.config, and return the result."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    check_project_owner(project, current_user)

    from app.engines.discovery_engine import DiscoveryEngine

    engine = DiscoveryEngine()

    async def _run_discovery() -> tuple[list[dict], list[dict]]:
        shopify_pages = await engine.discover_pages(
            project.shopify_url,
            password=project.shopify_password,
        )

        # Platform-aware source discovery
        if not project.source_url or project.source_type == SourceType.none:
            # No design source — map Shopify pages to themselves
            source_pages = shopify_pages
        elif project.source_type == SourceType.framer:
            source_pages = await engine.discover_framer_pages(project.source_url)
        elif project.source_type == SourceType.figma:
            # Figma uses API-based frame listing, not browser discovery
            source_pages = shopify_pages
        else:
            # Generic web URL (Vercel, Webflow, static site, etc.)
            # Crawl the source URL the same way we crawl Shopify
            try:
                source_pages = await engine.discover_pages(project.source_url)
            except Exception:
                source_pages = shopify_pages

        return shopify_pages, source_pages

    try:
        shopify_pages, source_pages = asyncio.run(_run_discovery())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Discovery failed: {exc}",
        ) from exc

    mappings = engine.auto_map(shopify_pages, source_pages)

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
