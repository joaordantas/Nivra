"""Replace legacy limits with canonical monthly budgets.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from alembic import op
import sqlalchemy as sa


revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None

_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_CENT = Decimal("0.01")


def _legacy_rows(connection) -> list[dict]:
    return [
        dict(row)
        for row in connection.execute(
            sa.text(
                "SELECT l.id, l.usuario_id, l.categoria_id, l.mes, l.valor, "
                "c.usuario_id AS categoria_usuario_id "
                "FROM limites l LEFT JOIN categorias c ON c.id = l.categoria_id "
                "ORDER BY l.id"
            )
        ).mappings()
    ]


def _validate_legacy(row: dict) -> tuple[date, Decimal]:
    month = str(row["mes"] or "")
    if not _MONTH.fullmatch(month):
        raise RuntimeError(f"limites.id={row['id']} possui período inválido")
    if row["categoria_usuario_id"] is None or int(row["categoria_usuario_id"]) != int(row["usuario_id"]):
        raise RuntimeError(f"limites.id={row['id']} possui ownership de categoria inválido")
    try:
        amount = Decimal(str(row["valor"]))
    except (InvalidOperation, TypeError) as exc:
        raise RuntimeError(f"limites.id={row['id']} possui valor inválido") from exc
    if not amount.is_finite() or amount <= 0 or amount != amount.quantize(_CENT):
        raise RuntimeError(f"limites.id={row['id']} possui valor monetário inválido")
    return date.fromisoformat(f"{month}-01"), amount


def upgrade() -> None:
    connection = op.get_bind()
    legacy = [(*_validate_legacy(row), row) for row in _legacy_rows(connection)]
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("categoria_id", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("limite", sa.Numeric(14, 2), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["categoria_id"], ["categorias.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("limite > 0", name="ck_budgets_limit_positive"),
        sa.UniqueConstraint(
            "usuario_id", "categoria_id", "periodo",
            name="uq_budgets_user_category_period",
        ),
    )
    op.create_index("ix_budgets_user_period", "budgets", ["usuario_id", "periodo"])
    if legacy:
        table = sa.table(
            "budgets",
            sa.column("id", sa.Integer()),
            sa.column("usuario_id", sa.Integer()),
            sa.column("categoria_id", sa.Integer()),
            sa.column("periodo", sa.Date()),
            sa.column("limite", sa.Numeric(14, 2)),
        )
        op.bulk_insert(
            table,
            [
                {
                    "id": int(row["id"]),
                    "usuario_id": int(row["usuario_id"]),
                    "categoria_id": int(row["categoria_id"]),
                    "periodo": period,
                    "limite": amount,
                }
                for period, amount, row in legacy
            ],
        )
    if connection.dialect.name == "postgresql":
        connection.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('budgets', 'id'), "
                "COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM budgets"
            )
        )
    op.drop_index("ix_limites_usuario_mes", table_name="limites")
    op.drop_table("limites")


def downgrade() -> None:
    connection = op.get_bind()
    rows = list(
        connection.execute(
            sa.text(
                "SELECT id, usuario_id, categoria_id, periodo, limite "
                "FROM budgets ORDER BY id"
            )
        ).mappings()
    )
    op.create_table(
        "limites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("categoria_id", sa.Integer(), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("mes", sa.String(length=7), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["categoria_id"], ["categorias.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.CheckConstraint("valor > 0", name="ck_limites_valor_positivo"),
        sa.UniqueConstraint(
            "categoria_id", "mes", "usuario_id",
            name="uq_limites_categoria_mes_usuario",
        ),
    )
    op.create_index("ix_limites_usuario_mes", "limites", ["usuario_id", "mes"])
    if rows:
        table = sa.table(
            "limites",
            sa.column("id", sa.Integer()),
            sa.column("categoria_id", sa.Integer()),
            sa.column("valor", sa.Numeric(14, 2)),
            sa.column("mes", sa.String()),
            sa.column("usuario_id", sa.Integer()),
        )
        op.bulk_insert(
            table,
            [
                {
                    "id": int(row["id"]),
                    "categoria_id": int(row["categoria_id"]),
                    "valor": Decimal(str(row["limite"])),
                    "mes": str(row["periodo"])[:7],
                    "usuario_id": int(row["usuario_id"]),
                }
                for row in rows
            ],
        )
    if connection.dialect.name == "postgresql":
        connection.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('limites', 'id'), "
                "COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM limites"
            )
        )
    op.drop_index("ix_budgets_user_period", table_name="budgets")
    op.drop_table("budgets")
