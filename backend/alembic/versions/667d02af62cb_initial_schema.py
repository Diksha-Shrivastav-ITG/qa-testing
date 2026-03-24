"""initial schema

Revision ID: 667d02af62cb
Revises:
Create Date: 2026-03-24 15:05:55.278371

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "667d02af62cb"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema."""
    # --- Enum types -------------------------------------------------------
    userrole = sa.Enum("admin", "developer", "pm", name="userrole")
    sourcetype = sa.Enum("framer", "figma", name="sourcetype")
    runstatus = sa.Enum("running", "completed", "failed", "cancelled", name="runstatus")
    capturesource = sa.Enum("shopify", "design", name="capturesource")
    aianalysisstatus = sa.Enum("completed", "pending", "failed", name="aianalysisstatus")
    issuetype = sa.Enum("visual", "functional", "content", name="issuetype")
    issueseverity = sa.Enum("critical", "major", "minor", name="issueseverity")
    issuestatus = sa.Enum("open", "resolved", "new", name="issuestatus")
    functionalteststs = sa.Enum("pass", "fail", name="functionalteststs")

    userrole.create(op.get_bind(), checkfirst=True)
    sourcetype.create(op.get_bind(), checkfirst=True)
    runstatus.create(op.get_bind(), checkfirst=True)
    capturesource.create(op.get_bind(), checkfirst=True)
    aianalysisstatus.create(op.get_bind(), checkfirst=True)
    issuetype.create(op.get_bind(), checkfirst=True)
    issueseverity.create(op.get_bind(), checkfirst=True)
    issuestatus.create(op.get_bind(), checkfirst=True)
    functionalteststs.create(op.get_bind(), checkfirst=True)

    # --- users ------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "developer", "pm", name="userrole"),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # --- projects ---------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("shopify_url", sa.String(512), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum("framer", "figma", name="sourcetype"),
            nullable=False,
        ),
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

    # --- qa_runs ----------------------------------------------------------
    op.create_table(
        "qa_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("running", "completed", "failed", "cancelled", name="runstatus"),
            nullable=False,
        ),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- captures ---------------------------------------------------------
    op.create_table(
        "captures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qa_run_id", sa.Integer(), nullable=False),
        sa.Column(
            "source",
            sa.Enum("shopify", "design", name="capturesource"),
            nullable=False,
        ),
        sa.Column("page", sa.String(512), nullable=False),
        sa.Column("breakpoint", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(1024), nullable=False),
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- comparisons ------------------------------------------------------
    op.create_table(
        "comparisons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qa_run_id", sa.Integer(), nullable=False),
        sa.Column("page", sa.String(512), nullable=False),
        sa.Column("breakpoint", sa.Integer(), nullable=False),
        sa.Column("ssim_score", sa.Float(), nullable=True),
        sa.Column("diff_image_path", sa.String(1024), nullable=True),
        sa.Column("heatmap_path", sa.String(1024), nullable=True),
        sa.Column(
            "ai_analysis_status",
            sa.Enum("completed", "pending", "failed", name="aianalysisstatus"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- issues -----------------------------------------------------------
    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qa_run_id", sa.Integer(), nullable=False),
        sa.Column("page", sa.String(512), nullable=False),
        sa.Column("breakpoint", sa.Integer(), nullable=True),
        sa.Column(
            "type",
            sa.Enum("visual", "functional", "content", name="issuetype"),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum("critical", "major", "minor", name="issueseverity"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("ai_suggestion", sa.Text(), nullable=True),
        sa.Column("element_selector", sa.String(1024), nullable=True),
        sa.Column("location_x", sa.Integer(), nullable=True),
        sa.Column("location_y", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "resolved", "new", name="issuestatus"),
            nullable=False,
        ),
        sa.Column("original_issue_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["original_issue_id"], ["issues.id"]),
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- functional_tests -------------------------------------------------
    op.create_table(
        "functional_tests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qa_run_id", sa.Integer(), nullable=False),
        sa.Column("test_name", sa.String(512), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pass", "fail", name="functionalteststs"),
            nullable=False,
        ),
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

    # Drop enum types
    sa.Enum(name="functionalteststs").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="issuestatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="issueseverity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="issuetype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="aianalysisstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="capturesource").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="runstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="sourcetype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
