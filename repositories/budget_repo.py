from datetime import date
from decimal import Decimal

from database.connection import get_connection


def create_budget(user_id: int, category_id: int, period: date, limit: Decimal) -> int:
    conn = get_connection()
    try:
        result = conn.execute(
            """
            INSERT INTO budgets (usuario_id, categoria_id, periodo, limite)
            VALUES (?, ?, ?, ?) RETURNING id
            """,
            (user_id, category_id, period, limit),
        )
        budget_id = int(result.fetchone()[0])
        conn.commit()
        return budget_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_budget(budget_id: int, user_id: int) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT b.id, b.usuario_id, b.categoria_id, c.nome, c.chave_sistema,
                   b.periodo, b.limite, b.criado_em, b.atualizado_em
            FROM budgets b
            JOIN categorias c ON c.id = b.categoria_id AND c.usuario_id = b.usuario_id
            WHERE b.id = ? AND b.usuario_id = ?
            """,
            (budget_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def list_budgets(user_id: int, period: date) -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT b.id, b.usuario_id, b.categoria_id, c.nome, c.chave_sistema,
                   b.periodo, b.limite, b.criado_em, b.atualizado_em
            FROM budgets b
            JOIN categorias c ON c.id = b.categoria_id AND c.usuario_id = b.usuario_id
            WHERE b.usuario_id = ? AND b.periodo = ?
            ORDER BY LOWER(c.nome), b.id
            """,
            (user_id, period),
        ).fetchall()
    finally:
        conn.close()


def update_budget_limit(budget_id: int, user_id: int, limit: Decimal) -> bool:
    conn = get_connection()
    try:
        result = conn.execute(
            """
            UPDATE budgets SET limite = ?, atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ? AND usuario_id = ?
            """,
            (limit, budget_id, user_id),
        )
        conn.commit()
        return result.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_budget(budget_id: int, user_id: int) -> bool:
    conn = get_connection()
    try:
        result = conn.execute(
            "DELETE FROM budgets WHERE id = ? AND usuario_id = ?",
            (budget_id, user_id),
        )
        conn.commit()
        return result.rowcount > 0
    finally:
        conn.close()
