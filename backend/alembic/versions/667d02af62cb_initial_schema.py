"""initial schema

Revision ID: 667d02af62cb
Revises:
Create Date: 2026-03-24 15:05:55.278371

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "667d02af62cb"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema."""
    # --- Enum types (idempotent via DO blocks) --------------------------------
    op.execute(sa.text("DO $$ BEGIN CREATE TYPE userrole AS ENUM ('admin', 'developer', 'pm'); EXCEPTION WHEN duplicate_object THEN null; END $$"))
    op.execute(sa.text("DO $$ BEGIN CREATE TYPE sourcetype AS ENUM ('framer', 'figma'); EXCEPTION WHEN duplicate_object THEN null; END $$"))
    op.execute(sa.text("DO $$ BEGIN CREATE TYPE runstatus AS ENUM ('running', 'completed', 'failed', 'cancelled'); EXCEPTION WHEN duplicate_object THEN null; END $$"))
    op.execute(sa.text("DO $$ BEGIN CREATE TYPE capturesource AS ENUM ('shopify', 'design'); EXCEPTION WHEN duplicate_object THEN null; END $$"))
    op.execute(sa.text("DO $$ BEGIN CREATE TYPE aianalysisstatus AS ENUM ('completed', 'pending', 'failed'); EXCEPTION WHEN duplicate_object THEN null; END $$"))
    op.execute(sa.text("DO $$ BEGIN CREATE TYPE issuetype AS ENUM ('visual', 'functional', 'content'); EXCEPTION WHEN duplicate_object THEN null; END $$"))
    op.execute(sa.text("DO $$ BEGIN CREATE TYPE issueseverity AS ENUM ('critical', 'major', 'minor'); EXCEPTION WHEN duplicate_object THEN null; END $$"))
    op.execute(sa.text("DO $$ BEGIN CREATE TYPE issuestatus AS ENUM ('open', 'resolved', 'new'); EXCEPTION WHEN duplicate_object THEN null; END $$"))
    op.execute(sa.text("DO $$ BEGIN CREATE TYPE functionalteststs AS ENUM ('pass', 'fail'); EXCEPTION WHEN duplicate_object THEN null; END $$"))

    # --- users ----------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", PgEnum("admin", "developer", "pm", name="userrole", create_type=False), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # --- projects -------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("shopify_url", sa.String(512), nullable=False),
        sa.Column("source_type", PgEnum("framer", "figma", name="sourcetype", create_type=False), nullable=False),
        sa.Column("source_url", sa.String(512), nullable=False),
        sa.Column("shopify_password", sa.String(1024), nullable=True),
        sa.Column("framer_password", sa.String(1024), nullable=True),
        sa.Column("figma_token", sa.String(1024), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("pass_threshold", sa.Float(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- qa_runs --------------------------------------------------------------
    op.create_table(
        "qa_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("status", PgEnum("running", "completed", "failed", "cancelled", name="runstatus", create_type=False), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- captures -------------------------------------------------------------
    op.create_table(
        "captures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qa_run_id", sa.Integer(), nullable=False),
        sa.Column("source", PgEnum("shopify", "design", name="capturesource", create_type=False), nullable=False),
        sa.Column("page", sa.String(512), nullable=False),
        sa.Column("breakpoint", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(1024), nullable=False),
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- comparisons ----------------------------------------------------------
    op.create_table(
        "comparisons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qa_run_id", sa.Integer(), nullable=False),
        sa.Column("page", sa.String(512), nullable=False),
        sa.Column("breakpoint", sa.Integer(), nullable=False),
        sa.Column("ssim_score", sa.Float(), nullable=True),
        sa.Column("diff_image_path", sa.String(1024), nullable=True),
        sa.Column("heatmap_path", sa.String(1024), nullable=True),
        sa.Column("ai_analysis_status", PgEnum("completed", "pending", "failed", name="aianalysisstatus", create_type=False), nullable=False),
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- issues ---------------------------------------------------------------
    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qa_run_id", sa.Integer(), nullable=False),
        sa.Column("page", sa.String(512), nullable=False),
        sa.Column("breakpoint", sa.Integer(), nullable=True),
        sa.Column("type", PgEnum("visual", "functional", "content", name="issuetype", create_type=False), nullable=False),
        sa.Column("severity", PgEnum("critical", "major", "minor", name="issueseverity", create_type=False), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("ai_suggestion", sa.Text(), nullable=True),
        sa.Column("element_selector", sa.String(1024), nullable=True),
        sa.Column("location_x", sa.Integer(), nullable=True),
        sa.Column("location_y", sa.Integer(), nullable=True),
        sa.Column("status", PgEnum("open", "resolved", "new", name="issuestatus", create_type=False), nullable=False),
        sa.Column("original_issue_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["original_issue_id"], ["issues.id"]),
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- functional_tests -----------------------------------------------------
    op.create_table(
        "functional_tests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qa_run_id", sa.Integer(), nullable=False),
        sa.Column("test_name", sa.String(512), nullable=False),
        sa.Column("status", PgEnum("pass", "fail", name="functionalteststs", create_type=False), nullable=False),
        sa.Column("severity", sa.String(50), nullable=True),
        sa.Column("step_failed", sa.String(512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("screenshot_path", sa.String(1024), nullable=True),
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop all tables and enum types."""
    op.drop_table("functional_tests")
    op.drop_table("issues")
    op.drop_table("comparisons")
    op.drop_table("captures")
    op.drop_table("qa_runs")
    op.drop_table("projects")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.execute(sa.text("DROP TYPE IF EXISTS functionalteststs"))
    op.execute(sa.text("DROP TYPE IF EXISTS issuestatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS issueseverity"))
    op.execute(sa.text("DROP TYPE IF EXISTS issuetype"))
    op.execute(sa.text("DROP TYPE IF EXISTS aianalysisstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS capturesource"))
    op.execute(sa.text("DROP TYPE IF EXISTS runstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS sourcetype"))
    op.execute(sa.text("DROP TYPE IF EXISTS userrole"))
