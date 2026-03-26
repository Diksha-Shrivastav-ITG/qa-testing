from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.qa_run import QaRun


class IssueType(str, enum.Enum):
    visual = "visual"
    functional = "functional"
    content = "content"


class IssueSeverity(str, enum.Enum):
    critical = "critical"
    major = "major"
    minor = "minor"


class IssueStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    new = "new"


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    qa_run_id: Mapped[int] = mapped_column(ForeignKey("qa_runs.id"), nullable=False)
    page: Mapped[str] = mapped_column(String(512), nullable=False)
    breakpoint: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[IssueType] = mapped_column(
        Enum(IssueType, name="issuetype"),
        nullable=False,
    )
    severity: Mapped[IssueSeverity] = mapped_column(
        Enum(IssueSeverity, name="issueseverity"),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    ai_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    element_selector: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    location_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, name="issuestatus"),
        nullable=False,
        default=IssueStatus.open,
    )
    screenshot_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    original_issue_id: Mapped[int | None] = mapped_column(
        ForeignKey("issues.id"), nullable=True
    )

    # Relationship
    qa_run: Mapped[QaRun] = relationship("QaRun", back_populates="issues")


# Alias used by run_service.calculate_score
Severity = IssueSeverity
