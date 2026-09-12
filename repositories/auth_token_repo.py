from datetime import datetime, timedelta

from database.connection import get_connection


def criar_token_substituindo_anteriores(
    usuario_id: int,
    finalidade: str,
    token_hash: str,
    expira_em: datetime,
    agora: datetime,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE auth_tokens
            SET revogado_em = ?
            WHERE usuario_id = ? AND finalidade = ?
              AND usado_em IS NULL AND revogado_em IS NULL
            """,
            (agora, usuario_id, finalidade),
        )
        conn.execute(
            """
            INSERT INTO auth_tokens (usuario_id, finalidade, token_hash, criado_em, expira_em)
            VALUES (?, ?, ?, ?, ?)
            """,
            (usuario_id, finalidade, token_hash, agora, expira_em),
        )
        conn.execute(
            "DELETE FROM auth_tokens WHERE expira_em < ?",
            (agora - timedelta(days=7),),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def buscar_token(token_hash: str, finalidade: str) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, usuario_id, criado_em, expira_em, usado_em, revogado_em
            FROM auth_tokens
            WHERE token_hash = ? AND finalidade = ?
            """,
            (token_hash, finalidade),
        ).fetchone()
    finally:
        conn.close()


def buscar_ultimo_token_ativo(usuario_id: int, finalidade: str) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT criado_em, expira_em
            FROM auth_tokens
            WHERE usuario_id = ? AND finalidade = ?
              AND usado_em IS NULL AND revogado_em IS NULL
            ORDER BY criado_em DESC
            LIMIT 1
            """,
            (usuario_id, finalidade),
        ).fetchone()
    finally:
        conn.close()


def revogar_token_por_hash(token_hash: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE auth_tokens
            SET revogado_em = CURRENT_TIMESTAMP
            WHERE token_hash = ? AND usado_em IS NULL AND revogado_em IS NULL
            """,
            (token_hash,),
        )
        conn.commit()
    finally:
        conn.close()


def confirmar_email_com_token(token_hash: str, agora: datetime) -> int | None:
    conn = get_connection()
    try:
        token = conn.execute(
            """
            SELECT id, usuario_id
            FROM auth_tokens
            WHERE token_hash = ? AND finalidade = 'email_verification'
              AND usado_em IS NULL AND revogado_em IS NULL AND expira_em > ?
            """,
            (token_hash, agora),
        ).fetchone()
        if token is None:
            return None
        atualizado = conn.execute(
            """
            UPDATE auth_tokens
            SET usado_em = ?
            WHERE id = ? AND usado_em IS NULL AND revogado_em IS NULL
            """,
            (agora, int(token[0])),
        )
        if atualizado.rowcount != 1:
            conn.rollback()
            return None
        conn.execute(
            """
            UPDATE usuarios
            SET email_verificado = TRUE, email_verificado_em = ?
            WHERE id = ?
            """,
            (agora, int(token[1])),
        )
        conn.commit()
        return int(token[1])
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def redefinir_senha_com_token(
    token_hash: str,
    senha_hash: str,
    agora: datetime,
) -> int | None:
    conn = get_connection()
    try:
        token = conn.execute(
            """
            SELECT id, usuario_id
            FROM auth_tokens
            WHERE token_hash = ? AND finalidade = 'password_reset'
              AND usado_em IS NULL AND revogado_em IS NULL AND expira_em > ?
            """,
            (token_hash, agora),
        ).fetchone()
        if token is None:
            return None
        atualizado = conn.execute(
            """
            UPDATE auth_tokens
            SET usado_em = ?
            WHERE id = ? AND usado_em IS NULL AND revogado_em IS NULL
            """,
            (agora, int(token[0])),
        )
        if atualizado.rowcount != 1:
            conn.rollback()
            return None
        usuario_id = int(token[1])
        conn.execute("UPDATE usuarios SET senha = ? WHERE id = ?", (senha_hash, usuario_id))
        conn.execute(
            """
            UPDATE auth_tokens
            SET revogado_em = ?
            WHERE usuario_id = ? AND usado_em IS NULL AND revogado_em IS NULL
            """,
            (agora, usuario_id),
        )
        conn.execute(
            """
            UPDATE sessoes
            SET revogada_em = ?
            WHERE usuario_id = ? AND revogada_em IS NULL
            """,
            (agora, usuario_id),
        )
        conn.commit()
        return usuario_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
