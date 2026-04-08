from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.qa_run import QaRun


class AiAnalysisStatus(str, enum.Enum):
    completed = "completed"
    pending = "pending"
    failed = "failed"


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    qa_run_id: Mapped[int] = mapped_column(ForeignKey("qa_runs.id"), nullable=False)
    page: Mapped[str] = mapped_column(String(512), nullable=False)
    breakpoint: Mapped[int] = mapped_column(Integer, nullable=False)

    # Visual similarity score (SSIM, 0.0–1.0)
    ssim_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # DOM / style similarity score (0.0–100.0)
    dom_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    diff_image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    heatmap_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    ai_analysis_status: Mapped[AiAnalysisStatus] = mapped_column(
        Enum(AiAnalysisStatus, name="aianalysisstatus"),
        nullable=False,
        default=AiAnalysisStatus.pending,
    )

    # Relationship
    qa_run: Mapped[QaRun] = relationship("QaRun", back_populates="comparisons")
