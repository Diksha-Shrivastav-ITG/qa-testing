from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.qa_run import QaRun


class LinkAudit(Base):
    __tablename__ = "link_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    qa_run_id: Mapped[int] = mapped_column(ForeignKey("qa_runs.id"), nullable=False)
    page: Mapped[str] = mapped_column(String(512), nullable=False)
    element_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "a" or "button"
    text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    href: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    is_mail_or_tel: Mapped[bool] = mapped_column(Boolean, default=False)
    has_href: Mapped[bool] = mapped_column(Boolean, default=False)
    issue: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "missing_href", "empty_text", "no_accessible_name"
    aria_label: Mapped[str | None] = mapped_column(String(512), nullable=True)

    qa_run: Mapped[QaRun] = relationship("QaRun", back_populates="link_audits")
