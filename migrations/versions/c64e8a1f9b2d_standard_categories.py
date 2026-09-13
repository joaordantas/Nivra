"""standard categories per user

Revision ID: c64e8a1f9b2d
Revises: e81f72c4a93b
Create Date: 2026-09-12 23:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c64e8a1f9b2d"
down_revision: Union[str, None] = "e81f72c4a93b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_CATEGORIES = (
    ("income", "Renda"),
    ("transfers", "Transferências"),
    ("investments", "Investimentos"),
    ("loans_financing", "Empréstimos e Financiamentos"),
    ("housing", "Moradia"),
    ("groceries", "Mercado"),
    ("food", "Alimentação"),
    ("transport", "Transporte"),
    ("vehicle", "Veículo"),
    ("health", "Saúde"),
    ("education", "Educação"),
    ("shopping", "Compras"),
    ("subscriptions", "Serviços e Assinaturas"),
    ("leisure", "Lazer"),
    ("travel", "Viagens"),
    ("taxes", "Impostos e Taxas"),
    ("insurance", "Seguros"),
    ("pets", "Pets"),
    ("donations", "Doações"),
    ("other", "Outros"),
)


def _sql_literal(value: str) -> str:
    """Render a fixed migration value safely in online and offline SQL."""
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    with op.batch_alter_table("categorias") as batch_op:
        batch_op.add_column(sa.Column("chave_sistema", sa.String(length=50), nullable=True))
        batch_op.create_unique_constraint(
            "uq_categorias_usuario_chave_sistema",
            ["usuario_id", "chave_sistema"],
        )

    for chave_sistema, nome in DEFAULT_CATEGORIES:
        nome_sql = _sql_literal(nome)
        chave_sql = _sql_literal(chave_sistema)
        op.execute(
            f"""
            INSERT INTO categorias (nome, usuario_id, chave_sistema)
            SELECT {nome_sql}, usuarios.id, {chave_sql}
            FROM usuarios
            WHERE NOT EXISTS (
                SELECT 1
                FROM categorias
                WHERE categorias.usuario_id = usuarios.id
                  AND categorias.chave_sistema = {chave_sql}
            )
            """
        )


def downgrade() -> None:
    # Mantém os nomes já semeados para não apagar categorias que possam ter sido
    # renomeadas ou usadas em transações. A identidade interna é removida.
    with op.batch_alter_table("categorias") as batch_op:
        batch_op.drop_constraint("uq_categorias_usuario_chave_sistema", type_="unique")
        batch_op.drop_column("chave_sistema")
