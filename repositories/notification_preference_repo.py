from __future__ import annotations

from database.connection import get_connection


def list_explicit_notification_preferences(usuario_id: int) -> dict[str, bool]:
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT preference_key, enabled
            FROM notification_preferences
            WHERE usuario_id = ?
            ORDER BY preference_key
            """,
            (usuario_id,),
        ).fetchall()
        return {str(key): bool(enabled) for key, enabled in rows}
    finally:
        connection.close()


def upsert_notification_preferences(
    usuario_id: int,
    preferences: dict[str, bool],
) -> None:
    connection = get_connection()
    try:
        for key, enabled in preferences.items():
            connection.execute(
                """
                INSERT INTO notification_preferences
                    (usuario_id, preference_key, enabled)
                VALUES (?, ?, ?)
                ON CONFLICT (usuario_id, preference_key) DO UPDATE
                SET enabled = excluded.enabled,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (usuario_id, key, enabled),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def record_notification_preference_suppression(
    usuario_id: int,
    preference_key: str,
    dedupe_key: str,
) -> None:
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO notification_preference_suppressions
                (usuario_id, preference_key, dedupe_key)
            VALUES (?, ?, ?)
            ON CONFLICT (usuario_id, dedupe_key) DO NOTHING
            """,
            (usuario_id, preference_key, dedupe_key),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def notification_event_was_suppressed(usuario_id: int, dedupe_key: str) -> bool:
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT 1
            FROM notification_preference_suppressions
            WHERE usuario_id = ? AND dedupe_key = ?
            """,
            (usuario_id, dedupe_key),
        ).fetchone()
        return row is not None
    finally:
        connection.close()
