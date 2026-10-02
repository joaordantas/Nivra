"""Add the internal notifications foundation.

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a012b3
"""

from alembic import op
import sqlalchemy as sa


revision = "e8f9a0b1c2d3"
down_revision = "d7e8f9a012b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("severidade", sa.String(10), nullable=False, server_default="info"),
        sa.Column("titulo", sa.String(160), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("metadados_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("chave_dedupe", sa.String(160)),
        sa.Column("lida", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "criada_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("lida_em", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "tipo IN ('financial_alert', 'card_alert', 'budget_alert', "
            "'goal_alert', 'system', 'summary')",
            name="ck_notifications_type",
        ),
        sa.CheckConstraint(
            "severidade IN ('info', 'warning', 'critical')",
            name="ck_notifications_severity",
        ),
        sa.CheckConstraint(
            "length(titulo) BETWEEN 1 AND 160",
            name="ck_notifications_title_length",
        ),
        sa.CheckConstraint(
            "length(mensagem) BETWEEN 1 AND 600",
            name="ck_notifications_message_length",
        ),
        sa.CheckConstraint(
            "length(metadados_json) <= 1000",
            name="ck_notifications_metadata_length",
        ),
        sa.CheckConstraint(
            "chave_dedupe IS NULL OR length(chave_dedupe) BETWEEN 1 AND 160",
            name="ck_notifications_dedupe_length",
        ),
        sa.CheckConstraint(
            "(lida = TRUE AND lida_em IS NOT NULL) OR "
            "(lida = FALSE AND lida_em IS NULL)",
            name="ck_notifications_read_state",
        ),
        sa.UniqueConstraint(
            "usuario_id",
            "chave_dedupe",
            name="uq_notifications_user_dedupe",
        ),
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["usuario_id", "criada_em", "id"],
    )
    op.create_index(
        "ix_notifications_user_unread_created",
        "notifications",
        ["usuario_id", "lida", "criada_em", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_unread_created", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
