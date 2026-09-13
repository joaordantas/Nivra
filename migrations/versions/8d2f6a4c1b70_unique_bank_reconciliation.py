"""unique bank reconciliation

Revision ID: 8d2f6a4c1b70
Revises: f4a7c2d9e510
Create Date: 2026-09-13 14:00:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "8d2f6a4c1b70"
down_revision: Union[str, None] = "f4a7c2d9e510"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("transacoes_bancarias") as batch_op:
        batch_op.create_unique_constraint(
            "uq_transacoes_bancarias_transacao_nivra",
            ["transacao_nivra_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("transacoes_bancarias") as batch_op:
        batch_op.drop_constraint(
            "uq_transacoes_bancarias_transacao_nivra",
            type_="unique",
        )
