"""open finance persistence

Revision ID: e81f72c4a93b
Revises: b92d8f3a6c10
Create Date: 2026-09-12 21:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e81f72c4a93b"
down_revision: Union[str, None] = "b92d8f3a6c10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conexoes_bancarias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("external_item_id", sa.String(length=80), nullable=False),
        sa.Column("client_user_ref", sa.String(length=120), nullable=False),
        sa.Column("external_connector_id", sa.Integer(), nullable=True),
        sa.Column("instituicao_nome", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("ambiente", sa.String(length=20), server_default="sandbox", nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("atualizada_em", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("ultima_sincronizacao_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("desconectada_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("ambiente IN ('sandbox', 'production')", name="ck_conexoes_ambiente"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_item_id", name="uq_conexoes_provider_item"),
    )
    op.create_index("ix_conexoes_usuario_status", "conexoes_bancarias", ["usuario_id", "status"], unique=False)

    op.create_table(
        "contas_bancarias_externas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conexao_id", sa.Integer(), nullable=False),
        sa.Column("external_account_id", sa.String(length=80), nullable=False),
        sa.Column("conta_nivra_id", sa.Integer(), nullable=True),
        sa.Column("nome", sa.String(length=160), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("subtipo", sa.String(length=60), nullable=True),
        sa.Column("moeda", sa.String(length=3), server_default="BRL", nullable=False),
        sa.Column("saldo", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("criada_em", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("atualizada_em", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["conexao_id"], ["conexoes_bancarias.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conta_nivra_id"], ["contas.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conexao_id", "external_account_id", name="uq_contas_externas_conexao_conta"),
    )
    op.create_index("ix_contas_externas_conexao", "contas_bancarias_externas", ["conexao_id"], unique=False)
    op.create_index("ix_contas_externas_conta_nivra", "contas_bancarias_externas", ["conta_nivra_id"], unique=False)

    provider_metadata_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "transacoes_bancarias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conta_bancaria_externa_id", sa.Integer(), nullable=False),
        sa.Column("external_transaction_id", sa.String(length=80), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("valor", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("direcao", sa.String(length=20), nullable=False),
        sa.Column("status_conciliacao", sa.String(length=30), server_default="pendente", nullable=False),
        sa.Column("transacao_nivra_id", sa.Integer(), nullable=True),
        sa.Column("metadata_provider", provider_metadata_type, nullable=True),
        sa.Column("criada_em", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("atualizada_em", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("direcao IN ('entrada', 'saida')", name="ck_transacoes_bancarias_direcao"),
        sa.CheckConstraint(
            "status_conciliacao IN ('pendente', 'possivel_correspondencia', 'conciliada', 'ignorada')",
            name="ck_transacoes_bancarias_conciliacao",
        ),
        sa.ForeignKeyConstraint(["conta_bancaria_externa_id"], ["contas_bancarias_externas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transacao_nivra_id"], ["transacoes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conta_bancaria_externa_id",
            "external_transaction_id",
            name="uq_transacoes_bancarias_conta_transacao",
        ),
    )
    op.create_index(
        "ix_transacoes_bancarias_conta_data",
        "transacoes_bancarias",
        ["conta_bancaria_externa_id", "data"],
        unique=False,
    )
    op.create_index(
        "ix_transacoes_bancarias_transacao_nivra",
        "transacoes_bancarias",
        ["transacao_nivra_id"],
        unique=False,
    )

    op.create_table(
        "eventos_sincronizacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conexao_id", sa.Integer(), nullable=False),
        sa.Column("provider_event_id", sa.String(length=100), nullable=True),
        sa.Column("tipo", sa.String(length=60), nullable=False),
        sa.Column("origem", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("iniciada_em", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("finalizada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quantidade_processada", sa.Integer(), server_default="0", nullable=False),
        sa.Column("codigo_erro", sa.String(length=80), nullable=True),
        sa.Column("mensagem_erro", sa.Text(), nullable=True),
        sa.CheckConstraint("quantidade_processada >= 0", name="ck_eventos_sync_quantidade"),
        sa.ForeignKeyConstraint(["conexao_id"], ["conexoes_bancarias.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_eventos_sync_conexao_inicio",
        "eventos_sincronizacao",
        ["conexao_id", "iniciada_em"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_eventos_sync_conexao_inicio", table_name="eventos_sincronizacao")
    op.drop_table("eventos_sincronizacao")
    op.drop_index("ix_transacoes_bancarias_transacao_nivra", table_name="transacoes_bancarias")
    op.drop_index("ix_transacoes_bancarias_conta_data", table_name="transacoes_bancarias")
    op.drop_table("transacoes_bancarias")
    op.drop_index("ix_contas_externas_conta_nivra", table_name="contas_bancarias_externas")
    op.drop_index("ix_contas_externas_conexao", table_name="contas_bancarias_externas")
    op.drop_table("contas_bancarias_externas")
    op.drop_index("ix_conexoes_usuario_status", table_name="conexoes_bancarias")
    op.drop_table("conexoes_bancarias")
