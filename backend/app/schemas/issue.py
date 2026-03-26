from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class IssueResponse(BaseModel):
    id: int
    qa_run_id: int
    page: str
    breakpoint: Optional[int] = None
    type: str
    severity: str
    description: str
    ai_suggestion: Optional[str] = None
    element_selector: Optional[str] = None
    location_x: Optional[int] = None
    location_y: Optional[int] = None
    status: str
    screenshot_path: Optional[str] = None
    original_issue_id: Optional[int] = None

    model_config = {"from_attributes": True}
