from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.models.project import SourceType


class ProjectCreate(BaseModel):
    name: str
    shopify_url: str
    source_type: SourceType
    source_url: str
    shopify_password: Optional[str] = None
    framer_password: Optional[str] = None
    figma_token: Optional[str] = None
    pass_threshold: float = 90.0


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    shopify_url: Optional[str] = None
    source_url: Optional[str] = None
    shopify_password: Optional[str] = None
    framer_password: Optional[str] = None
    figma_token: Optional[str] = None
    pass_threshold: Optional[float] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    shopify_url: str
    source_type: SourceType
    source_url: str
    pass_threshold: float
    created_by: int
    created_at: str

    model_config = {"from_attributes": True}
