from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.qa_run import QaRun
    from app.models.user import User


class SourceType:
    """String constants for project source_type.

    Replaces the old PostgreSQL ENUM so any platform URL is supported.
    Usage: project.source_type == SourceType.figma
    """

    framer = "framer"
    figma = "figma"
    none = "none"
    url = "url"           # Generic web URL (Vercel, Webflow, static site, etc.)
    webflow = "webflow"
    vercel = "vercel"
    shopify_preview = "shopify_preview"

    @classmethod
    def is_web_capturable(cls, value: str) -> bool:
        """Return True if this source type is captured via Playwright screenshot."""
        return value in (cls.framer, cls.url, cls.webflow, cls.vercel, cls.shopify_preview)

    @classmethod
    def requires_api(cls, value: str) -> bool:
        """Return True if this source type uses a dedicated API (not Playwright)."""
        return value == cls.figma


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    shopify_url: Mapped[str] = mapped_column(String(512), nullable=False)

    # Free-form string — accepts any platform identifier (figma/framer/vercel/url/none/…)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Nullable credential fields
    shopify_password: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    framer_password: Mapped[str | None] = mapped_column(String(1024), nullable=True)
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
