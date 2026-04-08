from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class PagePair(BaseModel):
    """A single explicit page mapping: reference URL path → Shopify URL path.

    Example:
        source_path = "/home"
        shopify_path = "/"
    """

    source_path: str = "/"
    shopify_path: str = "/"

    @field_validator("source_path", "shopify_path", mode="before")
    @classmethod
    def normalize_path(cls, v: str) -> str:
        v = v.strip()
        if v and not v.startswith("/"):
            v = "/" + v
        return v or "/"


class ProjectCreate(BaseModel):
    name: str
    shopify_url: str

    # Free-form platform identifier: figma / framer / vercel / webflow / url / none
    source_type: str = "none"

    # The design source URL (any platform)
    source_url: Optional[str] = None

    # Credentials
    shopify_password: Optional[str] = None
    framer_password: Optional[str] = None   # also used as generic source password
    figma_token: Optional[str] = None

    pass_threshold: float = 90.0

    # Optional explicit page pairs — stored in project.config["page_pairs"]
    # If omitted, page discovery runs automatically on first QA run
    page_pairs: Optional[List[PagePair]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    shopify_url: Optional[str] = None
    source_url: Optional[str] = None
    shopify_password: Optional[str] = None
    framer_password: Optional[str] = None
    figma_token: Optional[str] = None
    pass_threshold: Optional[float] = None
    page_pairs: Optional[List[PagePair]] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    shopify_url: str
    source_type: str          # plain string — no longer an enum
    source_url: Optional[str] = None
    pass_threshold: float
    created_by: int
    created_at: datetime
    page_pairs: List[PagePair] = []

    @classmethod
    def from_orm_with_pairs(cls, project: object) -> "ProjectResponse":
        config = getattr(project, "config", {}) or {}
        raw_pairs = config.get("page_pairs", [])
        pairs = [PagePair(source_path=p.get("source_path", "/"), shopify_path=p.get("shopify_path", "/")) for p in raw_pairs]
        data = {
            "id": project.id,           # type: ignore[attr-defined]
            "name": project.name,       # type: ignore[attr-defined]
            "shopify_url": project.shopify_url, # type: ignore[attr-defined]
            "source_type": project.source_type, # type: ignore[attr-defined]
            "source_url": project.source_url,   # type: ignore[attr-defined]
            "pass_threshold": project.pass_threshold, # type: ignore[attr-defined]
            "created_by": project.created_by,   # type: ignore[attr-defined]
            "created_at": project.created_at,   # type: ignore[attr-defined]
            "page_pairs": pairs,
        }
        return cls(**data)

    model_config = {"from_attributes": True}
