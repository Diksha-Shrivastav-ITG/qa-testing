"""add website source type, drop framer_password

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-02 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'website' to sourcetype enum
    op.execute(sa.text("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'website'"))
    # Drop framer_password column
    op.drop_column("projects", "framer_password")


def downgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("framer_password", sa.String(1024), nullable=True),
    )
