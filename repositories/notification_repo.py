from database.connection import get_connection


_COLUMNS = """
    id, tipo, severidade, titulo, mensagem, metadados_json,
    chave_dedupe, lida, criada_em, lida_em
"""


def create_notification(
    usuario_id: int,
    notification_type: str,
    severity: str,
    title: str,
    message: str,
    metadata_json: str,
    dedupe_key: str | None,
) -> tuple[tuple, bool]:
    conn = get_connection()
    try:
        row = conn.execute(
            f"""
            INSERT INTO notifications
                (usuario_id, tipo, severidade, titulo, mensagem, metadados_json, chave_dedupe)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (usuario_id, chave_dedupe) DO NOTHING
            RETURNING {_COLUMNS}
            """,
            (
                usuario_id,
                notification_type,
                severity,
                title,
                message,
                metadata_json,
                dedupe_key,
            ),
        ).fetchone()
        created = row is not None
        if not created:
            row = conn.execute(
                f"""
                SELECT {_COLUMNS}
                FROM notifications
                WHERE usuario_id = ? AND chave_dedupe = ?
                """,
                (usuario_id, dedupe_key),
            ).fetchone()
        conn.commit()
        if row is None:
            raise RuntimeError("Nao foi possivel criar ou recuperar a notificacao.")
        return row, created
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_notifications(
    usuario_id: int,
    *,
    limit: int,
    offset: int,
    unread_only: bool,
    notification_type: str | None,
) -> list[tuple]:
    filters = ["usuario_id = ?"]
    parameters: list[object] = [usuario_id]
    if unread_only:
        filters.append("lida = FALSE")
    if notification_type is not None:
        filters.append("tipo = ?")
        parameters.append(notification_type)
    parameters.extend((limit, offset))
    conn = get_connection()
    try:
        return conn.execute(
            f"""
            SELECT {_COLUMNS}
            FROM notifications
            WHERE {' AND '.join(filters)}
            ORDER BY criada_em DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            parameters,
        ).fetchall()
    finally:
        conn.close()


def count_unread_notifications(usuario_id: int) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE usuario_id = ? AND lida = FALSE",
            (usuario_id,),
        ).fetchone()
        return int(row[0])
    finally:
        conn.close()


def mark_notification_read(notification_id: int, usuario_id: int) -> tuple | None:
    conn = get_connection()
    try:
        row = conn.execute(
            f"""
            UPDATE notifications
            SET lida_em = CASE WHEN lida = FALSE THEN CURRENT_TIMESTAMP ELSE lida_em END,
                lida = TRUE
            WHERE id = ? AND usuario_id = ?
            RETURNING {_COLUMNS}
            """,
            (notification_id, usuario_id),
        ).fetchone()
        conn.commit()
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_all_notifications_read(usuario_id: int) -> int:
    conn = get_connection()
    try:
        result = conn.execute(
            """
            UPDATE notifications
            SET lida = TRUE, lida_em = CURRENT_TIMESTAMP
            WHERE usuario_id = ? AND lida = FALSE
            """,
            (usuario_id,),
        )
        conn.commit()
        return result.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_notification(notification_id: int, usuario_id: int) -> bool:
    conn = get_connection()
    try:
        result = conn.execute(
            "DELETE FROM notifications WHERE id = ? AND usuario_id = ?",
            (notification_id, usuario_id),
        )
        conn.commit()
        return result.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
