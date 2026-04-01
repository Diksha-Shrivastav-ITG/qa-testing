from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.project import SourceType


class ProjectCreate(BaseModel):
    name: str
    shopify_url: str
    source_type: SourceType = SourceType.none
    source_url: Optional[str] = None
    shopify_password: Optional[str] = None
    framer_password: Optional[str] = None
    figma_token: Optional[str] = None
    pass_threshold: float = 90.0
    page_mappings: Optional[dict[str, str]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    shopify_url: Optional[str] = None
    source_url: Optional[str] = None
    shopify_password: Optional[str] = None
    framer_password: Optional[str] = None
    figma_token: Optional[str] = None
    pass_threshold: Optional[float] = None
    page_mappings: Optional[dict[str, str]] = None


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
