"""account security hardening

Revision ID: b92d8f3a6c10
Revises: 7a4c9d2e1f30
Create Date: 2026-09-11 23:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b92d8f3a6c10"
down_revision: Union[str, None] = "7a4c9d2e1f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column(
            "email_verificado",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "usuarios",
        sa.Column("email_verificado_em", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("finalidade", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revogado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "finalidade IN ('email_verification', 'password_reset')",
            name="ck_auth_tokens_finalidade",
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
    )
    op.create_index(
        "ix_auth_tokens_usuario_finalidade",
        "auth_tokens",
        ["usuario_id", "finalidade"],
        unique=False,
    )
    op.create_index(
        "ix_auth_tokens_expiracao", "auth_tokens", ["expira_em"], unique=False
    )

    op.create_table(
        "auth_rate_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("escopo", sa.String(length=40), nullable=False),
        sa.Column("sujeito_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_rate_events_lookup",
        "auth_rate_events",
        ["escopo", "sujeito_hash", "criado_em"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_rate_events_lookup", table_name="auth_rate_events")
    op.drop_table("auth_rate_events")
    op.drop_index("ix_auth_tokens_expiracao", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_usuario_finalidade", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.drop_column("usuarios", "email_verificado_em")
    op.drop_column("usuarios", "email_verificado")
