"""open finance webhook inbox

Revision ID: a93c7e4d5f21
Revises: 8d2f6a4c1b70
Create Date: 2026-09-13 18:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a93c7e4d5f21"
down_revision: Union[str, None] = "8d2f6a4c1b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eventos_webhook_open_finance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=30), server_default="pluggy", nullable=False),
        sa.Column("provider_event_id", sa.String(length=100), nullable=False),
        sa.Column("tipo", sa.String(length=60), nullable=False),
        sa.Column("external_item_id", sa.String(length=120), nullable=True),
        sa.Column("conexao_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="recebido", nullable=False),
        sa.Column("tentativas", sa.Integer(), server_default="1", nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("quantidade_processada", sa.Integer(), server_default="0", nullable=False),
        sa.Column("codigo_erro", sa.String(length=80), nullable=True),
        sa.Column("mensagem_erro", sa.Text(), nullable=True),
        sa.Column(
            "recebido_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "ultima_tentativa_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("processado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('recebido', 'processando', 'sucesso', 'ignorado', 'erro')",
            name="ck_eventos_webhook_status",
        ),
        sa.CheckConstraint("tentativas >= 1", name="ck_eventos_webhook_tentativas"),
        sa.CheckConstraint(
            "quantidade_processada >= 0",
            name="ck_eventos_webhook_quantidade",
        ),
        sa.ForeignKeyConstraint(
            ["conexao_id"],
            ["conexoes_bancarias.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_eventos_webhook_provider_evento",
        ),
    )
    op.create_index(
        "ix_eventos_webhook_item_recebido",
        "eventos_webhook_open_finance",
        ["external_item_id", "recebido_em"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_eventos_webhook_item_recebido",
        table_name="eventos_webhook_open_finance",
    )
    op.drop_table("eventos_webhook_open_finance")
