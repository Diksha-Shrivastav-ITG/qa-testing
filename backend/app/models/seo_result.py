from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.qa_run import QaRun


class SeoResult(Base):
    __tablename__ = "seo_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    qa_run_id: Mapped[int] = mapped_column(ForeignKey("qa_runs.id"), nullable=False)
    page: Mapped[str] = mapped_column(String(512), nullable=False)
    test: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)

    qa_run: Mapped[QaRun] = relationship("QaRun", back_populates="seo_results")


class PerformanceResult(Base):
    __tablename__ = "performance_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    qa_run_id: Mapped[int] = mapped_column(ForeignKey("qa_runs.id"), nullable=False)
    page: Mapped[str] = mapped_column(String(512), nullable=False)
    load_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    dom_ready_ms: Mapped[int] = mapped_column(Integer, default=0)
    ttfb_ms: Mapped[int] = mapped_column(Integer, default=0)
    total_resources: Mapped[int] = mapped_column(Integer, default=0)
    total_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    js_count: Mapped[int] = mapped_column(Integer, default=0)
    js_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    css_count: Mapped[int] = mapped_column(Integer, default=0)
    css_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    img_count: Mapped[int] = mapped_column(Integer, default=0)
    img_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    dom_nodes: Mapped[int] = mapped_column(Integer, default=0)
    # Performance issues stored as JSON text
    issues_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    qa_run: Mapped[QaRun] = relationship("QaRun", back_populates="performance_results")
