"""Add scoped Lumi conversations and memories."""

from alembic import op
import sqlalchemy as sa

revision = "d7e8f9a012b3"
down_revision = "c6d7e8f9a012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lumi_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False, unique=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("titulo", sa.String(160)),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lumi_conversations_user_updated", "lumi_conversations", ["usuario_id", "atualizada_em"])
    op.create_table(
        "lumi_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("lumi_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="completed"),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_lumi_messages_role"),
        sa.CheckConstraint("status IN ('completed', 'failed')", name="ck_lumi_messages_status"),
    )
    op.create_index("ix_lumi_messages_conversation_created", "lumi_messages", ["conversation_id", "criada_em", "id"])
    op.create_table(
        "lumi_memories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False, unique=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("categoria", sa.String(32), nullable=False),
        sa.Column("conteudo", sa.String(600), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("origem", sa.String(32), nullable=False, server_default="explicit_user"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("categoria IN ('preference', 'goal', 'personal_context')", name="ck_lumi_memories_category"),
        sa.CheckConstraint("origem = 'explicit_user'", name="ck_lumi_memories_origin"),
        sa.UniqueConstraint("usuario_id", "fingerprint", name="uq_lumi_memories_user_fingerprint"),
    )
    op.create_index("ix_lumi_memories_user_active", "lumi_memories", ["usuario_id", "ativo", "atualizada_em"])


def downgrade() -> None:
    op.drop_index("ix_lumi_memories_user_active", table_name="lumi_memories")
    op.drop_table("lumi_memories")
    op.drop_index("ix_lumi_messages_conversation_created", table_name="lumi_messages")
    op.drop_table("lumi_messages")
    op.drop_index("ix_lumi_conversations_user_updated", table_name="lumi_conversations")
    op.drop_table("lumi_conversations")
