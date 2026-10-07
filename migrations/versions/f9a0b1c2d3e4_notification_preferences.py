"""Add per-user notification preferences.

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
"""

from alembic import op
import sqlalchemy as sa


revision = "f9a0b1c2d3e4"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("preference_key", sa.String(40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "preference_key IN ('invoice_due_soon', 'invoice_overdue', "
            "'card_limit', 'unusual_expense')",
            name="ck_notification_preferences_key",
        ),
        sa.PrimaryKeyConstraint(
            "usuario_id",
            "preference_key",
            name="pk_notification_preferences",
        ),
    )
    op.create_table(
        "notification_preference_suppressions",
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("preference_key", sa.String(40), nullable=False),
        sa.Column("dedupe_key", sa.String(160), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "preference_key IN ('invoice_due_soon', 'invoice_overdue', "
            "'card_limit', 'unusual_expense')",
            name="ck_notification_suppressions_key",
        ),
        sa.CheckConstraint(
            "length(dedupe_key) BETWEEN 1 AND 160",
            name="ck_notification_suppressions_dedupe",
        ),
        sa.PrimaryKeyConstraint(
            "usuario_id",
            "dedupe_key",
            name="pk_notification_preference_suppressions",
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_preference_suppressions")
    op.drop_table("notification_preferences")
