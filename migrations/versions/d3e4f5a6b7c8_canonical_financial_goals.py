"""Add canonical financial goals and movement history.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
"""

from alembic import op
import sqlalchemy as sa


revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("descricao", sa.String(length=600)),
        sa.Column("valor_alvo", sa.Numeric(14, 2), nullable=False),
        sa.Column("data_limite", sa.Date()),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.CheckConstraint("valor_alvo > 0", name="ck_goals_target_positive"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_goals_status"),
    )
    op.create_index("ix_goals_user_status", "goals", ["usuario_id", "status", "id"])
    op.create_table(
        "goal_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=16), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("data_efetiva", sa.Date(), nullable=False),
        sa.Column("descricao", sa.String(length=300)),
        sa.Column("chave_idempotencia", sa.String(length=64)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.CheckConstraint("tipo IN ('contribution', 'withdrawal')", name="ck_goal_movements_type"),
        sa.CheckConstraint("valor > 0", name="ck_goal_movements_amount_positive"),
        sa.UniqueConstraint("usuario_id", "chave_idempotencia", name="uq_goal_movements_user_idempotency"),
    )
    op.create_index("ix_goal_movements_goal_effective", "goal_movements", ["goal_id", "data_efetiva", "id"])


def downgrade() -> None:
    op.drop_index("ix_goal_movements_goal_effective", table_name="goal_movements")
    op.drop_table("goal_movements")
    op.drop_index("ix_goals_user_status", table_name="goals")
    op.drop_table("goals")
