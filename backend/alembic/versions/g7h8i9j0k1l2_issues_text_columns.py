"""issues: widen screenshot_path and element_selector from VARCHAR(1024) to TEXT

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-04-02

VARCHAR(1024) is too short for long screenshot file paths and element
descriptions that may exceed 1024 characters.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, Sequence[str], None] = "f6g7h8i9j0k1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "issues", "screenshot_path",
        existing_type=sa.String(1024),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "issues", "element_selector",
        existing_type=sa.String(1024),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Truncate to fit if reverting (data loss possible for long values)
    op.execute(sa.text(
        "UPDATE issues SET screenshot_path = LEFT(screenshot_path, 1024) "
        "WHERE LENGTH(screenshot_path) > 1024"
    ))
    op.execute(sa.text(
        "UPDATE issues SET element_selector = LEFT(element_selector, 1024) "
        "WHERE LENGTH(element_selector) > 1024"
    ))
    op.alter_column(
        "issues", "screenshot_path",
        existing_type=sa.Text(),
        type_=sa.String(1024),
        existing_nullable=True,
    )
    op.alter_column(
        "issues", "element_selector",
        existing_type=sa.Text(),
        type_=sa.String(1024),
        existing_nullable=True,
    )
