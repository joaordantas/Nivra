"""Track and lease periodic summary job runs.

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
"""

from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5a6"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "periodic_summary_job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_type", sa.String(length=16), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("lease_token", sa.String(length=36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suppressed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=48), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("job_type IN ('weekly', 'monthly')", name="ck_periodic_summary_job_type"),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'partial_success', 'failed')",
            name="ck_periodic_summary_job_status",
        ),
        sa.CheckConstraint("period_end >= period_start", name="ck_periodic_summary_job_period"),
        sa.CheckConstraint("attempt >= 1", name="ck_periodic_summary_job_attempt"),
        sa.CheckConstraint(
            "processed_count >= 0 AND success_count >= 0 AND suppressed_count >= 0 "
            "AND skipped_count >= 0 AND failure_count >= 0 AND retry_count >= 0",
            name="ck_periodic_summary_job_counts",
        ),
        sa.CheckConstraint(
            "(status = 'running' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND finished_at IS NULL) OR "
            "(status <> 'running' AND lease_token IS NULL AND lease_expires_at IS NULL "
            "AND finished_at IS NOT NULL)",
            name="ck_periodic_summary_job_lifecycle",
        ),
        sa.UniqueConstraint("job_type", "period_start", name="uq_periodic_summary_job_period"),
    )
    op.create_index(
        "ix_periodic_summary_job_status_lease",
        "periodic_summary_job_runs",
        ["status", "lease_expires_at"],
    )
    op.create_index(
        "ix_periodic_summary_job_started",
        "periodic_summary_job_runs",
        ["started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_periodic_summary_job_started", table_name="periodic_summary_job_runs")
    op.drop_index("ix_periodic_summary_job_status_lease", table_name="periodic_summary_job_runs")
    op.drop_table("periodic_summary_job_runs")
