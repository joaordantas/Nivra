"""Record atomic Lumi financial action execution.

Revision ID: b5c7d9e1f203
Revises: e9a2d6c3b4f1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b5c7d9e1f203"
down_revision: Union[str, None] = "e9a2d6c3b4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("lumi_action_confirmations") as batch:
        batch.add_column(sa.Column("execution_eligible", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch.add_column(sa.Column("executed_transaction_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_unique_constraint(
            "uq_lumi_action_confirmations_executed_transaction_id", ["executed_transaction_id"],
        )
        batch.drop_constraint("ck_lumi_action_confirmations_status", type_="check")
        batch.create_check_constraint(
            "ck_lumi_action_confirmations_status",
            "status IN ('pending', 'confirmed', 'cancelled', 'expired', 'executed')",
        )
        batch.create_check_constraint(
            "ck_lumi_action_confirmations_execution",
            "(status = 'executed') = (executed_transaction_id IS NOT NULL AND executed_at IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("lumi_action_confirmations") as batch:
        batch.drop_constraint("ck_lumi_action_confirmations_execution", type_="check")
        batch.drop_constraint("ck_lumi_action_confirmations_status", type_="check")
        batch.create_check_constraint(
            "ck_lumi_action_confirmations_status",
            "status IN ('pending', 'confirmed', 'cancelled', 'expired')",
        )
        batch.drop_constraint("uq_lumi_action_confirmations_executed_transaction_id", type_="unique")
        batch.drop_column("executed_at")
        batch.drop_column("executed_transaction_id")
        batch.drop_column("execution_eligible")
