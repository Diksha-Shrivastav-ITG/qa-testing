"""add 'other' value to sourcetype enum

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-06 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'other'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from enums directly.
    # To fully reverse, you'd need to recreate the enum without 'other'.
    pass
