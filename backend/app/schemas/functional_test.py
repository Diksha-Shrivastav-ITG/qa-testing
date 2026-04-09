from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class FunctionalTestResponse(BaseModel):
    id: int
    qa_run_id: int
    test_name: str
    status: str
    severity: Optional[str] = None
    step_failed: Optional[str] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    page: Optional[str] = None

    model_config = {"from_attributes": True}
