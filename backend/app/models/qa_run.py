from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.accessibility_result import AccessibilityResult
    from app.models.capture import Capture
    from app.models.comparison import Comparison
    from app.models.functional_test import FunctionalTest
    from app.models.issue import Issue
    from app.models.link_audit import LinkAudit
    from app.models.seo_result import PerformanceResult, SeoResult
    from app.models.project import Project


class RunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class QaRun(Base):
    __tablename__ = "qa_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="runstatus"),
        nullable=False,
        default=RunStatus.running,
    )
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[str] = mapped_column(server_default=func.now())
    completed_at: Mapped[str | None] = mapped_column(nullable=True)
    # "design" = compare vs Framer/Figma, "ai" = AI-only analysis (no design reference)
    test_mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default="design")
    # Comma-separated test types that were run, e.g. "qa,functional,ada,seo,performance,link_audit"
    # NULL means Full QA mode (all tests)
    test_types: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Per-page configs for Customize tab runs: [{label, mode, shopify_url, reference_url}, ...]
    # NULL means Full QA mode (uses project-level source)
    page_configs: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Relationships
    project: Mapped[Project] = relationship("Project", back_populates="runs")
    captures: Mapped[list[Capture]] = relationship(
        "Capture", back_populates="qa_run", cascade="all, delete-orphan"
    )
    comparisons: Mapped[list[Comparison]] = relationship(
        "Comparison", back_populates="qa_run", cascade="all, delete-orphan"
    )
    issues: Mapped[list[Issue]] = relationship(
        "Issue", back_populates="qa_run", cascade="all, delete-orphan"
    )
    functional_tests: Mapped[list[FunctionalTest]] = relationship(
        "FunctionalTest", back_populates="qa_run", cascade="all, delete-orphan"
    )
    accessibility_results: Mapped[list[AccessibilityResult]] = relationship(
        "AccessibilityResult", back_populates="qa_run", cascade="all, delete-orphan"
    )
    link_audits: Mapped[list[LinkAudit]] = relationship(
        "LinkAudit", back_populates="qa_run", cascade="all, delete-orphan"
    )
    seo_results: Mapped[list[SeoResult]] = relationship(
        "SeoResult", back_populates="qa_run", cascade="all, delete-orphan"
    )
    performance_results: Mapped[list[PerformanceResult]] = relationship(
        "PerformanceResult", back_populates="qa_run", cascade="all, delete-orphan"
    )
