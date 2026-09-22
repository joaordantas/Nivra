from __future__ import annotations

from datetime import datetime

from database.connection import DatabaseConnection, get_connection


def criar_confirmacao(
    usuario_id: int,
    token_hash: str,
    action_type: str,
    payload_json: str,
    expira_em: datetime,
    execution_eligible: bool = False,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO lumi_action_confirmations
                (usuario_id, token_hash, action_type, payload_json, status, expira_em, execution_eligible)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (usuario_id, token_hash, action_type, payload_json, expira_em, execution_eligible),
        )
        conn.commit()
    finally:
        conn.close()


def buscar_confirmacao(token_hash: str, usuario_id: int) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, action_type, payload_json, status, criado_em, expira_em,
                   confirmado_em, cancelado_em, executed_transaction_id, executed_at, execution_eligible
            FROM lumi_action_confirmations
            WHERE token_hash = ? AND usuario_id = ?
            """,
            (token_hash, usuario_id),
        ).fetchone()
    finally:
        conn.close()


def expirar_confirmacao_pendente(token_hash: str, usuario_id: int, agora: datetime) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE lumi_action_confirmations
            SET status = 'expired'
            WHERE token_hash = ? AND usuario_id = ?
              AND status = 'pending' AND expira_em <= ?
            """,
            (token_hash, usuario_id, agora),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def confirmar_confirmacao_pendente(token_hash: str, usuario_id: int, agora: datetime) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE lumi_action_confirmations
            SET status = 'confirmed', confirmado_em = ?
            WHERE token_hash = ? AND usuario_id = ?
              AND status = 'pending' AND expira_em > ?
            """,
            (agora, token_hash, usuario_id, agora),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def cancelar_confirmacao_pendente(token_hash: str, usuario_id: int, agora: datetime) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE lumi_action_confirmations
            SET status = 'cancelled', cancelado_em = ?
            WHERE token_hash = ? AND usuario_id = ?
              AND status = 'pending' AND expira_em > ?
            """,
            (agora, token_hash, usuario_id, agora),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def reivindicar_confirmacao_para_execucao(
    conn: DatabaseConnection, token_hash: str, usuario_id: int, agora: datetime
) -> tuple | None:
    """Obtém a única reivindicação; o commit pertence ao serviço."""
    return conn.execute(
        """
        UPDATE lumi_action_confirmations
        SET status = 'confirmed', confirmado_em = ?
        WHERE token_hash = ? AND usuario_id = ?
          AND status = 'pending' AND execution_eligible = TRUE AND expira_em > ?
        RETURNING id, action_type, payload_json, expira_em
        """, (agora, token_hash, usuario_id, agora),
    ).fetchone()


def finalizar_execucao(
    conn: DatabaseConnection, confirmation_db_id: int, transaction_id: int, agora: datetime
) -> None:
    cursor = conn.execute(
        """
        UPDATE lumi_action_confirmations
        SET status = 'executed', executed_transaction_id = ?, executed_at = ?
        WHERE id = ? AND status = 'confirmed'
        """, (transaction_id, agora, confirmation_db_id),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("A confirmação perdeu seu estado durante a execução.")
