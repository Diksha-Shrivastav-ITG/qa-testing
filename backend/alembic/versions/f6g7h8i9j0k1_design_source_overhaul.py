"""Design source overhaul: source_type ENUM → VARCHAR, add dom_score to comparisons

Revision ID: f6g7h8i9j0k1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-02

Changes:
  - projects.source_type: PostgreSQL ENUM (framer/figma/none) → VARCHAR(50)
    Allows any platform string: figma, framer, vercel, webflow, url, none, etc.
  - comparisons.dom_score: new nullable FLOAT column for DOM-based similarity score
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6g7h8i9j0k1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Convert projects.source_type from PgEnum → VARCHAR ────────────────
    #
    # PostgreSQL does not allow direct ALTER COLUMN type change from enum → varchar
    # using ALTER COLUMN … TYPE because the implicit cast is disallowed.
    # The safe approach: add a temp column, copy, drop original, rename.

    op.add_column(
        "projects",
        sa.Column("_src_type_tmp", sa.String(50), nullable=True),
    )
    # Cast existing enum values to text and copy
    op.execute(sa.text("UPDATE projects SET _src_type_tmp = source_type::text"))
    # Default any nulls to 'none'
    op.execute(sa.text("UPDATE projects SET _src_type_tmp = 'none' WHERE _src_type_tmp IS NULL"))
    # Make NOT NULL with default
    op.alter_column("projects", "_src_type_tmp", nullable=False, server_default="none")
    # Drop the old enum-typed column
    op.drop_column("projects", "source_type")
    # Rename temp column to source_type
    op.alter_column("projects", "_src_type_tmp", new_column_name="source_type")

    # ── 2. Add dom_score to comparisons ──────────────────────────────────────
    op.add_column(
        "comparisons",
        sa.Column("dom_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    # ── 1. Remove dom_score from comparisons ──────────────────────────────────
    op.drop_column("comparisons", "dom_score")

    # ── 2. Revert projects.source_type VARCHAR → PgEnum ──────────────────────
    # Values added post-migration (vercel, webflow, url, …) fall back to 'none'
    op.execute(sa.text("ALTER TABLE projects ADD COLUMN _src_type_old sourcetype"))
    op.execute(sa.text(
        """
        UPDATE projects SET _src_type_old =
          CASE
            WHEN source_type IN ('framer', 'figma', 'none') THEN source_type::sourcetype
            ELSE 'none'::sourcetype
          END
        """
    ))
    op.execute(sa.text("ALTER TABLE projects ALTER COLUMN _src_type_old SET NOT NULL"))
    op.drop_column("projects", "source_type")
    op.execute(sa.text("ALTER TABLE projects RENAME COLUMN _src_type_old TO source_type"))
