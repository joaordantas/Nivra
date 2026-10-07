"""Allow weekly and monthly summary preferences.

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
"""

from alembic import op
import sqlalchemy as sa


revision = "a0b1c2d3e4f5"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


OLD_KEYS = "'invoice_due_soon', 'invoice_overdue', 'card_limit', 'unusual_expense'"
NEW_KEYS = OLD_KEYS + ", 'weekly_summary', 'monthly_summary'"


def _replace_constraints(keys: str) -> None:
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


def upgrade() -> None:
    _replace_constraints(NEW_KEYS)


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM notification_preference_suppressions "
            "WHERE preference_key IN ('weekly_summary', 'monthly_summary')"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM notification_preferences "
            "WHERE preference_key IN ('weekly_summary', 'monthly_summary')"
        )
    )
    _replace_constraints(OLD_KEYS)
