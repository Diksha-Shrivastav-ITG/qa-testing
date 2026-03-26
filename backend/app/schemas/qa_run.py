from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RunResponse(BaseModel):
    id: int
    project_id: int
    status: str
    overall_score: Optional[float] = None
    run_number: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    test_mode: str = "design"

    model_config = {"from_attributes": True}
