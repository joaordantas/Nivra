"""installment plan foundation

Revision ID: f7b3c1d8e920
Revises: d41e7b9a2c60
Create Date: 2026-09-14 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7b3c1d8e920"
down_revision: Union[str, None] = "d41e7b9a2c60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parcelamentos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantidade_parcelas", sa.Integer(), nullable=False),
        sa.Column("data_inicial", sa.Date(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "usuario_id", name="uq_parcelamentos_id_usuario"),
        sa.CheckConstraint("valor_total > 0", name="ck_parcelamentos_valor_positivo"),
        sa.CheckConstraint(
            "quantidade_parcelas >= 2", name="ck_parcelamentos_quantidade"
        ),
    )
    op.create_index(
        "ix_parcelamentos_usuario_data",
        "parcelamentos",
        ["usuario_id", "data_inicial"],
    )

    with op.batch_alter_table("transacoes") as batch_op:
        batch_op.add_column(sa.Column("parcelamento_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("numero_parcela", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_transacoes_parcelamento_usuario",
            "parcelamentos",
            ["parcelamento_id", "usuario_id"],
            ["id", "usuario_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(
            "uq_transacoes_parcelamento_numero",
            ["parcelamento_id", "numero_parcela"],
        )
        batch_op.create_check_constraint(
            "ck_transacoes_parcelamento_completo",
            "(parcelamento_id IS NULL AND numero_parcela IS NULL) OR "
            "(parcelamento_id IS NOT NULL AND numero_parcela IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_transacoes_numero_parcela",
            "numero_parcela IS NULL OR numero_parcela >= 1",
        )
    op.create_index(
        "ix_transacoes_parcelamento",
        "transacoes",
        ["parcelamento_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_transacoes_parcelamento", table_name="transacoes")
    with op.batch_alter_table("transacoes") as batch_op:
        batch_op.drop_constraint("ck_transacoes_numero_parcela", type_="check")
        batch_op.drop_constraint("ck_transacoes_parcelamento_completo", type_="check")
        batch_op.drop_constraint("uq_transacoes_parcelamento_numero", type_="unique")
        batch_op.drop_constraint("fk_transacoes_parcelamento_usuario", type_="foreignkey")
        batch_op.drop_column("numero_parcela")
        batch_op.drop_column("parcelamento_id")
    op.drop_index("ix_parcelamentos_usuario_data", table_name="parcelamentos")
    op.drop_table("parcelamentos")
