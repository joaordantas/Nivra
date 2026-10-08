"""Harden notification operations and durable deduplication.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
"""

from alembic import op
import sqlalchemy as sa


revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def _replace_job_constraint(kinds: str) -> None:
    with op.batch_alter_table("periodic_summary_job_runs") as batch:
        batch.drop_constraint("ck_periodic_summary_job_type", type_="check")
        batch.create_check_constraint(
            "ck_periodic_summary_job_type",
            f"job_type IN ({kinds})",
        )


def upgrade() -> None:
    op.create_table(
        "notification_dedupe_ledger",
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(160), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "length(dedupe_key) BETWEEN 1 AND 160",
            name="ck_notification_dedupe_ledger_key",
        ),
        sa.PrimaryKeyConstraint(
            "usuario_id",
            "dedupe_key",
            name="pk_notification_dedupe_ledger",
        ),
    )
    op.execute(
        sa.text(
            "INSERT INTO notification_dedupe_ledger "
            "(usuario_id, dedupe_key, created_at) "
            "SELECT usuario_id, chave_dedupe, MIN(criada_em) "
            "FROM notifications WHERE chave_dedupe IS NOT NULL "
            "GROUP BY usuario_id, chave_dedupe "
            "ON CONFLICT (usuario_id, dedupe_key) DO NOTHING"
        )
    )

    with op.batch_alter_table("periodic_summary_job_runs") as batch:
        batch.add_column(
            sa.Column("generated_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("deduplicated_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0")
        )
        batch.create_check_constraint(
            "ck_periodic_summary_job_observability",
            "generated_count >= 0 AND deduplicated_count >= 0 AND duration_ms >= 0",
        )
    _replace_job_constraint("'weekly', 'monthly', 'financial_alerts', 'cleanup'")


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM periodic_summary_job_runs WHERE job_type = 'cleanup'"))
    _replace_job_constraint("'weekly', 'monthly', 'financial_alerts'")
    with op.batch_alter_table("periodic_summary_job_runs") as batch:
        batch.drop_constraint(
            "ck_periodic_summary_job_observability",
            type_="check",
        )
        batch.drop_column("duration_ms")
        batch.drop_column("deduplicated_count")
        batch.drop_column("generated_count")
    op.drop_table("notification_dedupe_ledger")
