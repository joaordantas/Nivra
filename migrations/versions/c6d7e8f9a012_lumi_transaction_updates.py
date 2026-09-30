"""Allow Lumi transaction update proposals.

Revision ID: c6d7e8f9a012
Revises: b5c7d9e1f203
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c6d7e8f9a012"
down_revision: Union[str, None] = "b5c7d9e1f203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("lumi_action_confirmations") as batch:
        batch.drop_constraint(
            "uq_lumi_action_confirmations_executed_transaction_id", type_="unique",
        )
        batch.drop_constraint("ck_lumi_action_confirmations_type", type_="check")
        batch.create_check_constraint(
            "ck_lumi_action_confirmations_type",
            "action_type IN ('create_expense', 'create_income', 'update_transaction')",
        )
    op.create_index(
        "uq_lumi_action_confirmations_created_transaction_id",
        "lumi_action_confirmations",
        ["executed_transaction_id"],
        unique=True,
        postgresql_where=sa.text("action_type IN ('create_expense', 'create_income')"),
        sqlite_where=sa.text("action_type IN ('create_expense', 'create_income')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_lumi_action_confirmations_created_transaction_id",
        table_name="lumi_action_confirmations",
    )
    with op.batch_alter_table("lumi_action_confirmations") as batch:
        batch.drop_constraint("ck_lumi_action_confirmations_type", type_="check")
        batch.create_check_constraint(
            "ck_lumi_action_confirmations_type",
            "action_type IN ('create_expense', 'create_income')",
        )
        batch.create_unique_constraint(
            "uq_lumi_action_confirmations_executed_transaction_id",
            ["executed_transaction_id"],
        )
