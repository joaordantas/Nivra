from datetime import datetime, timedelta

from database.connection import get_connection


def contar_eventos(escopo: str, sujeito_hash: str, desde: datetime) -> tuple[int, datetime | str | None]:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*), MIN(criado_em)
            FROM auth_rate_events
            WHERE escopo = ? AND sujeito_hash = ? AND criado_em > ?
            """,
            (escopo, sujeito_hash, desde),
        ).fetchone()
        return int(row[0]), row[1]
    finally:
        conn.close()


def registrar_evento(escopo: str, sujeito_hash: str, agora: datetime) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO auth_rate_events (escopo, sujeito_hash, criado_em)
            VALUES (?, ?, ?)
            """,
            (escopo, sujeito_hash, agora),
        )
        conn.execute(
            "DELETE FROM auth_rate_events WHERE criado_em < ?",
            (agora - timedelta(hours=24),),
        )
        conn.commit()
    finally:
        conn.close()


def limpar_eventos(escopo: str, sujeito_hash: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM auth_rate_events WHERE escopo = ? AND sujeito_hash = ?",
            (escopo, sujeito_hash),
        )
        conn.commit()
    finally:
        conn.close()
