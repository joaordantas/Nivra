from datetime import datetime

from database.connection import get_connection


def criar_sessao(
    usuario_id: int,
    token_hash: str,
    csrf_hash: str,
    expira_em: datetime,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO sessoes (usuario_id, token_hash, csrf_hash, expira_em)
            VALUES (?, ?, ?, ?)
            """,
            (usuario_id, token_hash, csrf_hash, expira_em),
        )
        conn.commit()
    finally:
        conn.close()


def buscar_sessao(token_hash: str) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT u.id, u.usuario, u.email, u.tipo_perfil,
                   s.token_hash, s.csrf_hash, s.expira_em,
                   u.email_verificado, u.email_verificado_em
            FROM sessoes s
            JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.token_hash = ? AND s.revogada_em IS NULL
            """,
            (token_hash,),
        ).fetchone()
    finally:
        conn.close()


def atualizar_csrf_sessao(token_hash: str, csrf_hash: str) -> bool:
    conn = get_connection()
    try:
        resultado = conn.execute(
            """
            UPDATE sessoes
            SET csrf_hash = ?
            WHERE token_hash = ? AND revogada_em IS NULL
            """,
            (csrf_hash, token_hash),
        )
        conn.commit()
        return resultado.rowcount > 0
    finally:
        conn.close()


def revogar_sessao(token_hash: str) -> bool:
    conn = get_connection()
    try:
        resultado = conn.execute(
            """
            UPDATE sessoes
            SET revogada_em = CURRENT_TIMESTAMP
            WHERE token_hash = ? AND revogada_em IS NULL
            """,
            (token_hash,),
        )
        conn.commit()
        return resultado.rowcount > 0
    finally:
        conn.close()


def limpar_sessoes_expiradas() -> None:
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM sessoes WHERE expira_em <= CURRENT_TIMESTAMP OR revogada_em IS NOT NULL"
        )
        conn.commit()
    finally:
        conn.close()


def revogar_todas_sessoes(usuario_id: int, agora: datetime) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE sessoes
            SET revogada_em = ?
            WHERE usuario_id = ? AND revogada_em IS NULL
            """,
            (agora, usuario_id),
        )
        conn.commit()
    finally:
        conn.close()
