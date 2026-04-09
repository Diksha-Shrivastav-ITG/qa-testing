from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PageConfigSchema(BaseModel):
    label: str
    mode: str  # "ai" or "design"
    shopify_url: str
    reference_url: Optional[str] = None


class StartRunRequest(BaseModel):
    page_configs: Optional[list[PageConfigSchema]] = None
    test_mode: Optional[str] = "ai"  # only used for Full QA (when page_configs is None)
    test_types: Optional[list[str]] = None


class RunResponse(BaseModel):
    id: int
    project_id: int
    status: str
    overall_score: Optional[float] = None
    run_number: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    test_mode: str = "design"
    test_types: Optional[str] = None  # comma-separated, None = Full QA (all tests)
    page_configs: Optional[list] = None  # per-page configs, None = Full QA

    model_config = {"from_attributes": True}
