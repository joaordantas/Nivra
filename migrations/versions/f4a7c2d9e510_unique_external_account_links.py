"""unique external account links

Revision ID: f4a7c2d9e510
Revises: c64e8a1f9b2d
Create Date: 2026-09-13 09:30:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f4a7c2d9e510"
down_revision: Union[str, None] = "c64e8a1f9b2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("contas_bancarias_externas") as batch_op:
        batch_op.create_unique_constraint(
            "uq_contas_externas_conta_nivra",
            ["conta_nivra_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("contas_bancarias_externas") as batch_op:
        batch_op.drop_constraint(
            "uq_contas_externas_conta_nivra",
            type_="unique",
        )
