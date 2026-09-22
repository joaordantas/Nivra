"""lumi action confirmations

Revision ID: e9a2d6c3b4f1
Revises: f7b3c1d8e920
Create Date: 2026-09-22 15:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e9a2d6c3b4f1"
down_revision: Union[str, None] = "f7b3c1d8e920"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lumi_action_confirmations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "action_type IN ('create_expense', 'create_income')",
            name="ck_lumi_action_confirmations_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled', 'expired')",
            name="ck_lumi_action_confirmations_status",
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_lumi_action_confirmations_token_hash"),
    )
    op.create_index(
        "ix_lumi_action_confirmations_user_status_expiry",
        "lumi_action_confirmations",
        ["usuario_id", "status", "expira_em"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lumi_action_confirmations_user_status_expiry",
        table_name="lumi_action_confirmations",
    )
    op.drop_table("lumi_action_confirmations")
