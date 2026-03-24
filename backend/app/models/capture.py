from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.qa_run import QaRun


class CaptureSource(str, enum.Enum):
    shopify = "shopify"
    design = "design"


class Capture(Base):
    __tablename__ = "captures"

    id: Mapped[int] = mapped_column(primary_key=True)
    qa_run_id: Mapped[int] = mapped_column(ForeignKey("qa_runs.id"), nullable=False)
    source: Mapped[CaptureSource] = mapped_column(
        Enum(CaptureSource, name="capturesource"),
        nullable=False,
    )
    page: Mapped[str] = mapped_column(String(512), nullable=False)
    breakpoint: Mapped[int] = mapped_column(Integer, nullable=False)
    image_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    # Relationship
    qa_run: Mapped[QaRun] = relationship("QaRun", back_populates="captures")
