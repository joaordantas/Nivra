"""Add budget and goal threshold alert state.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
"""

from alembic import op
import sqlalchemy as sa


revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


OLD_PREFERENCE_KEYS = (
    "'invoice_due_soon', 'invoice_overdue', 'card_limit', 'unusual_expense', "
    "'weekly_summary', 'monthly_summary'"
)
NEW_PREFERENCE_KEYS = OLD_PREFERENCE_KEYS + ", 'budget_threshold', 'goal_progress'"


def _replace_preference_constraints(keys: str) -> None:
    with op.batch_alter_table("notification_preferences") as batch:
        batch.drop_constraint("ck_notification_preferences_key", type_="check")
        batch.create_check_constraint(
            "ck_notification_preferences_key",
            f"preference_key IN ({keys})",
        )
    with op.batch_alter_table("notification_preference_suppressions") as batch:
        batch.drop_constraint("ck_notification_suppressions_key", type_="check")
        batch.create_check_constraint(
            "ck_notification_suppressions_key",
            f"preference_key IN ({keys})",
        )


def _replace_job_constraint(kinds: str) -> None:
    with op.batch_alter_table("periodic_summary_job_runs") as batch:
        batch.drop_constraint("ck_periodic_summary_job_type", type_="check")
        batch.create_check_constraint(
            "ck_periodic_summary_job_type",
            f"job_type IN ({kinds})",
        )


def upgrade() -> None:
    _replace_preference_constraints(NEW_PREFERENCE_KEYS)
    _replace_job_constraint("'weekly', 'monthly', 'financial_alerts'")
    op.create_table(
        "financial_alert_states",
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(16), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("period_key", sa.String(10), nullable=False),
        sa.Column(
            "highest_milestone",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint(
            "usuario_id",
            "source_kind",
            "source_id",
            "period_key",
            name="pk_financial_alert_states",
        ),
        sa.CheckConstraint(
            "source_kind IN ('budget', 'goal')",
            name="ck_financial_alert_states_kind",
        ),
        sa.CheckConstraint(
            "highest_milestone BETWEEN 0 AND 100",
            name="ck_financial_alert_states_milestone",
        ),
        sa.CheckConstraint(
            "length(period_key) BETWEEN 1 AND 10",
            name="ck_financial_alert_states_period",
        ),
    )
    op.create_index(
        "ix_financial_alert_states_user_kind_period",
        "financial_alert_states",
        ["usuario_id", "source_kind", "period_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_financial_alert_states_user_kind_period",
        table_name="financial_alert_states",
    )
    op.drop_table("financial_alert_states")
    op.execute(
        sa.text(
            "DELETE FROM notification_preference_suppressions "
            "WHERE preference_key IN ('budget_threshold', 'goal_progress')"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM notification_preferences "
            "WHERE preference_key IN ('budget_threshold', 'goal_progress')"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM periodic_summary_job_runs "
            "WHERE job_type = 'financial_alerts'"
        )
    )
    _replace_job_constraint("'weekly', 'monthly'")
    _replace_preference_constraints(OLD_PREFERENCE_KEYS)
