"""make source_url optional, add 'none' to sourcetype enum

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-25 13:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'none' to sourcetype enum
    op.execute(sa.text("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'none'"))
    # Make source_url nullable
    op.alter_column("projects", "source_url", existing_type=sa.String(512), nullable=True)


def downgrade() -> None:
    op.alter_column("projects", "source_url", existing_type=sa.String(512), nullable=False)
