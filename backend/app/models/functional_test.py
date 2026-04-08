from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.qa_run import QaRun


class FunctionalTestStatus(str, enum.Enum):
    pass_ = "pass"
    fail = "fail"


class FunctionalTest(Base):
    __tablename__ = "functional_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    qa_run_id: Mapped[int] = mapped_column(ForeignKey("qa_runs.id"), nullable=False)
    test_name: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[FunctionalTestStatus] = mapped_column(
        Enum(FunctionalTestStatus, name="functionalteststs", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    step_failed: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    page: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Relationship
    qa_run: Mapped[QaRun] = relationship("QaRun", back_populates="functional_tests")


# Alias used by run_service.calculate_score
TestStatus = FunctionalTestStatus
