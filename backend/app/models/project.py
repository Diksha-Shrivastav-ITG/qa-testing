from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.qa_run import QaRun
    from app.models.user import User


class SourceType(str, enum.Enum):
    website = "website"
    framer = "framer"
    figma = "figma"
    none = "none"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    shopify_url: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="sourcetype"),
        nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Nullable encrypted credential fields
    shopify_password: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    figma_token: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    pass_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=90.0)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(server_default=func.now())

    # Relationships
    runs: Mapped[list[QaRun]] = relationship(
        "QaRun", back_populates="project", cascade="all, delete-orphan"
    )
    owner: Mapped[User] = relationship("User", foreign_keys=[created_by])
