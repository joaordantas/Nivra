from database.connection import get_connection
from repositories.categoria_repo import criar_categorias_padrao
from utils.security import hash_senha

def cadastrar_usuario(usuario: str, email: str, senha: str, tipo_perfil: str):
    conn = get_connection()
    try:
        resultado = conn.execute("""
            INSERT INTO usuarios (usuario, email, senha, tipo_perfil)
            VALUES (?, ?, ?, ?)
            RETURNING id
        """, (usuario, email, hash_senha(senha), tipo_perfil)).fetchone()
        usuario_id = int(resultado[0])
        criar_categorias_padrao(conn, usuario_id)
        conn.commit()
        return usuario_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def buscar_usuario_por_email(email: str):
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, usuario, email, senha, tipo_perfil,
                   email_verificado, email_verificado_em
            FROM usuarios
            WHERE LOWER(email) = LOWER(?)
            """,
            (email,),
        ).fetchone()
    finally:
        conn.close()

def buscar_perfil(usuario_id: int) -> str | None:
    conn = get_connection()
    try:
        resultado = conn.execute(
            "SELECT tipo_perfil FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
        return resultado[0] if resultado else None
    finally:
        conn.close()


def buscar_usuario_por_id(usuario_id: int) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, usuario, email, senha, tipo_perfil,
                   email_verificado, email_verificado_em
            FROM usuarios
            WHERE id = ?
            """,
            (usuario_id,),
        ).fetchone()
    finally:
        conn.close()


def atualizar_senha_e_revogar_acessos(
    usuario_id: int,
    senha_hash: str,
    agora,
) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE usuarios SET senha = ? WHERE id = ?", (senha_hash, usuario_id))
        conn.execute(
            "UPDATE sessoes SET revogada_em = ? WHERE usuario_id = ? AND revogada_em IS NULL",
            (agora, usuario_id),
        )
        conn.execute(
            """
            UPDATE auth_tokens
            SET revogado_em = ?
            WHERE usuario_id = ? AND usado_em IS NULL AND revogado_em IS NULL
            """,
            (agora, usuario_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
