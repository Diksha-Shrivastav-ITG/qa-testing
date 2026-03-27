"""add seo_results and performance_results tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-27 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seo_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("qa_run_id", sa.Integer(), sa.ForeignKey("qa_runs.id"), nullable=False),
        sa.Column("page", sa.String(512), nullable=False),
        sa.Column("test", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
    )
    op.create_table(
        "performance_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("qa_run_id", sa.Integer(), sa.ForeignKey("qa_runs.id"), nullable=False),
        sa.Column("page", sa.String(512), nullable=False),
        sa.Column("load_time_ms", sa.Integer(), default=0),
        sa.Column("dom_ready_ms", sa.Integer(), default=0),
        sa.Column("ttfb_ms", sa.Integer(), default=0),
        sa.Column("total_resources", sa.Integer(), default=0),
        sa.Column("total_size_bytes", sa.Integer(), default=0),
        sa.Column("js_count", sa.Integer(), default=0),
        sa.Column("js_size_bytes", sa.Integer(), default=0),
        sa.Column("css_count", sa.Integer(), default=0),
        sa.Column("css_size_bytes", sa.Integer(), default=0),
        sa.Column("img_count", sa.Integer(), default=0),
        sa.Column("img_size_bytes", sa.Integer(), default=0),
        sa.Column("dom_nodes", sa.Integer(), default=0),
        sa.Column("issues_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("performance_results")
    op.drop_table("seo_results")
