from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class RunResponse(BaseModel):
    id: int
    project_id: int
    status: str
    overall_score: Optional[float] = None
    run_number: int
    started_at: str
    completed_at: Optional[str] = None

    model_config = {"from_attributes": True}
