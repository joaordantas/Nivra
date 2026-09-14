"""advanced open finance reconciliation

Revision ID: d41e7b9a2c60
Revises: a93c7e4d5f21
Create Date: 2026-09-14 02:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d41e7b9a2c60"
down_revision: Union[str, None] = "a93c7e4d5f21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("transacoes_bancarias") as batch_op:
        batch_op.drop_constraint("ck_transacoes_bancarias_conciliacao", type_="check")
        batch_op.add_column(sa.Column("removida_em", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_check_constraint(
            "ck_transacoes_bancarias_conciliacao",
            "status_conciliacao IN ('pendente', 'possivel_correspondencia', 'ambigua', 'conciliada', 'ignorada', 'reaberta')",
        )

    op.create_table(
        "correspondencias_conciliacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("transacao_bancaria_id", sa.Integer(), nullable=False),
        sa.Column("transacao_nivra_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="sugerida", nullable=False),
        sa.Column("confianca", sa.String(length=10), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("motivos", sa.Text(), nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizada_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decidida_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transacao_bancaria_id"], ["transacoes_bancarias.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transacao_nivra_id"], ["transacoes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transacao_bancaria_id", "transacao_nivra_id", name="uq_correspondencias_par"),
        sa.CheckConstraint(
            "status IN ('sugerida', 'confirmada', 'rejeitada', 'reaberta')",
            name="ck_correspondencias_status",
        ),
        sa.CheckConstraint(
            "confianca IN ('alta', 'media', 'baixa')",
            name="ck_correspondencias_confianca",
        ),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="ck_correspondencias_score"),
    )
    op.create_index(
        "ix_correspondencias_usuario_status",
        "correspondencias_conciliacao",
        ["usuario_id", "status"],
    )
    op.create_index(
        "uq_correspondencias_bancaria_confirmada",
        "correspondencias_conciliacao",
        ["transacao_bancaria_id"],
        unique=True,
        postgresql_where=sa.text("status = 'confirmada'"),
        sqlite_where=sa.text("status = 'confirmada'"),
    )
    op.create_index(
        "uq_correspondencias_manual_confirmada",
        "correspondencias_conciliacao",
        ["transacao_nivra_id"],
        unique=True,
        postgresql_where=sa.text("status = 'confirmada'"),
        sqlite_where=sa.text("status = 'confirmada'"),
    )
    op.execute(
        """
        INSERT INTO correspondencias_conciliacao (
            usuario_id, transacao_bancaria_id, transacao_nivra_id,
            status, confianca, score, motivos, decidida_em
        )
        SELECT cb.usuario_id, tb.id, tb.transacao_nivra_id,
               CASE WHEN tb.status_conciliacao = 'conciliada' THEN 'confirmada' ELSE 'sugerida' END,
               'alta', 90, '["mesma_conta", "mesmo_valor", "mesma_direcao", "data_proxima"]',
               CASE WHEN tb.status_conciliacao = 'conciliada' THEN CURRENT_TIMESTAMP ELSE NULL END
        FROM transacoes_bancarias tb
        JOIN contas_bancarias_externas ce ON ce.id = tb.conta_bancaria_externa_id
        JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
        WHERE tb.transacao_nivra_id IS NOT NULL
          AND tb.status_conciliacao IN ('possivel_correspondencia', 'conciliada')
        """
    )


def downgrade() -> None:
    op.drop_index("uq_correspondencias_manual_confirmada", table_name="correspondencias_conciliacao")
    op.drop_index("uq_correspondencias_bancaria_confirmada", table_name="correspondencias_conciliacao")
    op.drop_index("ix_correspondencias_usuario_status", table_name="correspondencias_conciliacao")
    op.drop_table("correspondencias_conciliacao")
    with op.batch_alter_table("transacoes_bancarias") as batch_op:
        batch_op.drop_constraint("ck_transacoes_bancarias_conciliacao", type_="check")
        batch_op.drop_column("removida_em")
        batch_op.create_check_constraint(
            "ck_transacoes_bancarias_conciliacao",
            "status_conciliacao IN ('pendente', 'possivel_correspondencia', 'conciliada', 'ignorada')",
        )
