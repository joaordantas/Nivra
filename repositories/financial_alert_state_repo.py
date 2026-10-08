from __future__ import annotations

from database.connection import get_connection


def list_financial_alert_states(
    usuario_id: int,
    source_kind: str,
) -> dict[tuple[int, str], int]:
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT source_id, period_key, highest_milestone
            FROM financial_alert_states
            WHERE usuario_id = ? AND source_kind = ?
            """,
            (usuario_id, source_kind),
        ).fetchall()
        return {
            (int(source_id), str(period_key)): int(highest_milestone)
            for source_id, period_key, highest_milestone in rows
        }
    finally:
        connection.close()


def advance_financial_alert_state(
    usuario_id: int,
    source_kind: str,
    source_id: int,
    period_key: str,
    milestone: int,
) -> None:
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO financial_alert_states
                (usuario_id, source_kind, source_id, period_key, highest_milestone)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (usuario_id, source_kind, source_id, period_key) DO UPDATE
            SET highest_milestone = CASE
                    WHEN excluded.highest_milestone > financial_alert_states.highest_milestone
                    THEN excluded.highest_milestone
                    ELSE financial_alert_states.highest_milestone
                END,
                updated_at = CASE
                    WHEN excluded.highest_milestone > financial_alert_states.highest_milestone
                    THEN CURRENT_TIMESTAMP
                    ELSE financial_alert_states.updated_at
                END
            """,
            (usuario_id, source_kind, source_id, period_key, milestone),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
