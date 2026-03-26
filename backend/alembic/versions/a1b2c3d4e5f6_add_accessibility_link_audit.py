"""add accessibility_results, link_audits, and test_mode to qa_runs

Revision ID: a1b2c3d4e5f6
Revises: 667d02af62cb
Create Date: 2026-03-25 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "667d02af62cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- accessibility_results table ----------------------------------------
    op.create_table(
        "accessibility_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qa_run_id", sa.Integer(), nullable=False),
        sa.Column("page", sa.String(512), nullable=False),
        sa.Column("test_name", sa.String(256), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("wcag", sa.String(512), nullable=True),
        sa.Column("element", sa.Text(), nullable=True),
        sa.Column("help_text", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- link_audits table --------------------------------------------------
    op.create_table(
        "link_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qa_run_id", sa.Integer(), nullable=False),
        sa.Column("page", sa.String(512), nullable=False),
        sa.Column("element_type", sa.String(20), nullable=False),
        sa.Column("text", sa.String(512), nullable=True),
        sa.Column("href", sa.String(2048), nullable=True),
        sa.Column("destination", sa.String(2048), nullable=True),
        sa.Column("is_external", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_mail_or_tel", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_href", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("issue", sa.String(100), nullable=True),
        sa.Column("aria_label", sa.String(512), nullable=True),
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- test_mode column on qa_runs ----------------------------------------
    op.add_column(
        "qa_runs",
        sa.Column("test_mode", sa.String(20), nullable=False, server_default="design"),
    )


def downgrade() -> None:
    op.drop_column("qa_runs", "test_mode")
    op.drop_table("link_audits")
    op.drop_table("accessibility_results")
