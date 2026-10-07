from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Iterator

from database.connection import DatabaseConnection, get_connection


GOAL_COLUMNS = "g.id,g.usuario_id,g.nome,g.descricao,g.valor_alvo,g.data_limite,g.status,g.criado_em,g.atualizado_em"


def create_goal(user_id: int, name: str, description: str | None, target: Decimal, deadline: date | None) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "INSERT INTO goals (usuario_id,nome,descricao,valor_alvo,data_limite) VALUES (?,?,?,?,?) RETURNING id",
            (user_id, name, description, target, deadline),
        ).fetchone()
        conn.commit()
        return int(row[0])
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_goal(goal_id: int, user_id: int, reference: date) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            f"""SELECT {GOAL_COLUMNS}, COALESCE(SUM(CASE WHEN m.data_efetiva <= ? THEN CASE WHEN m.tipo='contribution' THEN m.valor ELSE -m.valor END ELSE 0 END),0)
            FROM goals g LEFT JOIN goal_movements m ON m.goal_id=g.id AND m.usuario_id=g.usuario_id
            WHERE g.id=? AND g.usuario_id=? GROUP BY {GOAL_COLUMNS}""",
            (reference, goal_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def list_goals(user_id: int, reference: date, include_archived: bool) -> list[tuple]:
    conn = get_connection()
    try:
        status_filter = "" if include_archived else "AND g.status='active'"
        return conn.execute(
            f"""SELECT {GOAL_COLUMNS}, COALESCE(SUM(CASE WHEN m.data_efetiva <= ? THEN CASE WHEN m.tipo='contribution' THEN m.valor ELSE -m.valor END ELSE 0 END),0)
            FROM goals g LEFT JOIN goal_movements m ON m.goal_id=g.id AND m.usuario_id=g.usuario_id
            WHERE g.usuario_id=? {status_filter} GROUP BY {GOAL_COLUMNS}
            ORDER BY CASE WHEN g.status='active' THEN 0 ELSE 1 END, g.data_limite, LOWER(g.nome), g.id""",
            (reference, user_id),
        ).fetchall()
    finally:
        conn.close()


def update_goal(goal_id: int, user_id: int, name: str, description: str | None, target: Decimal, deadline: date | None, status: str) -> bool:
    conn = get_connection()
    try:
        result = conn.execute(
            "UPDATE goals SET nome=?,descricao=?,valor_alvo=?,data_limite=?,status=?,atualizado_em=CURRENT_TIMESTAMP WHERE id=? AND usuario_id=?",
            (name, description, target, deadline, status, goal_id, user_id),
        )
        conn.commit()
        return result.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_or_archive_goal(goal_id: int, user_id: int) -> str | None:
    conn = get_connection()
    try:
        conn.lock_row("goals", "id", goal_id)
        owned = conn.execute("SELECT id FROM goals WHERE id=? AND usuario_id=?", (goal_id, user_id)).fetchone()
        if owned is None:
            conn.rollback()
            return None
        has_history = conn.execute("SELECT 1 FROM goal_movements WHERE goal_id=? LIMIT 1", (goal_id,)).fetchone() is not None
        if has_history:
            conn.execute("UPDATE goals SET status='archived',atualizado_em=CURRENT_TIMESTAMP WHERE id=?", (goal_id,))
            outcome = "archived"
        else:
            conn.execute("DELETE FROM goals WHERE id=? AND usuario_id=?", (goal_id, user_id))
            outcome = "deleted"
        conn.commit()
        return outcome
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_movements(goal_id: int, user_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id,goal_id,tipo,valor,data_efetiva,descricao,chave_idempotencia,criado_em FROM goal_movements WHERE goal_id=? AND usuario_id=? ORDER BY data_efetiva,id",
            (goal_id, user_id),
        ).fetchall()
    finally:
        conn.close()


@contextmanager
def goal_transaction(goal_id: int, user_id: int) -> Iterator[DatabaseConnection]:
    conn = get_connection()
    try:
        # UPDATE obtains a SQLite write lock; FOR UPDATE serializes PostgreSQL.
        conn.execute("UPDATE goals SET atualizado_em=atualizado_em WHERE id=? AND usuario_id=?", (goal_id, user_id))
        conn.lock_row("goals", "id", goal_id)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_goal_in_connection(conn: DatabaseConnection, goal_id: int, user_id: int) -> tuple | None:
    return conn.execute(
        "SELECT id,usuario_id,nome,descricao,valor_alvo,data_limite,status,criado_em,atualizado_em FROM goals WHERE id=? AND usuario_id=?",
        (goal_id, user_id),
    ).fetchone()


def list_movements_in_connection(conn: DatabaseConnection, goal_id: int, user_id: int) -> list[tuple]:
    return conn.execute(
        "SELECT id,goal_id,tipo,valor,data_efetiva,descricao,chave_idempotencia,criado_em FROM goal_movements WHERE goal_id=? AND usuario_id=? ORDER BY data_efetiva,id",
        (goal_id, user_id),
    ).fetchall()


def find_idempotent_movement(conn: DatabaseConnection, user_id: int, key: str) -> tuple | None:
    return conn.execute(
        "SELECT id,goal_id,tipo,valor,data_efetiva,descricao,chave_idempotencia,criado_em FROM goal_movements WHERE usuario_id=? AND chave_idempotencia=?",
        (user_id, key),
    ).fetchone()


def insert_movement(conn: DatabaseConnection, goal_id: int, user_id: int, kind: str, amount: Decimal, effective_date: date, description: str | None, idempotency_key: str | None) -> int:
    row = conn.execute(
        "INSERT INTO goal_movements (goal_id,usuario_id,tipo,valor,data_efetiva,descricao,chave_idempotencia) VALUES (?,?,?,?,?,?,?) RETURNING id",
        (goal_id, user_id, kind, amount, effective_date, description, idempotency_key),
    ).fetchone()
    return int(row[0])
