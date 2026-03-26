from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.qa_run import QaRun


class AccessibilityResult(Base):
    __tablename__ = "accessibility_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    qa_run_id: Mapped[int] = mapped_column(ForeignKey("qa_runs.id"), nullable=False)
    page: Mapped[str] = mapped_column(String(512), nullable=False)
    test_name: Mapped[str] = mapped_column(String(256), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # critical / major / minor
    description: Mapped[str] = mapped_column(Text, nullable=False)
    wcag: Mapped[str | None] = mapped_column(String(512), nullable=True)
    element: Mapped[str | None] = mapped_column(Text, nullable=True)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    qa_run: Mapped[QaRun] = relationship("QaRun", back_populates="accessibility_results")
