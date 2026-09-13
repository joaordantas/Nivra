from database.connection import get_connection
from utils.categorias_padrao import DEFAULT_CATEGORIES


def criar_categoria(nome: str, usuario_id: int) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO categorias (nome, usuario_id) VALUES (?, ?) RETURNING id",
            (nome, usuario_id),
        )
        categoria_id = int(cursor.fetchone()[0])
        conn.commit()
        return categoria_id
    finally:
        conn.close()


def criar_categorias_padrao(conn, usuario_id: int) -> None:
    for chave_sistema, nome in DEFAULT_CATEGORIES:
        conn.execute(
            """
            INSERT INTO categorias (nome, usuario_id, chave_sistema)
            VALUES (?, ?, ?)
            ON CONFLICT (usuario_id, chave_sistema) DO NOTHING
            """,
            (nome, usuario_id, chave_sistema),
        )


def listar_categorias(usuario_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, nome, chave_sistema FROM categorias
            WHERE usuario_id = ?
            ORDER BY LOWER(nome)
            """,
            (usuario_id,),
        ).fetchall()
    finally:
        conn.close()


def buscar_categoria_por_id(categoria_id: int, usuario_id: int) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, nome, chave_sistema FROM categorias WHERE id = ? AND usuario_id = ?",
            (categoria_id, usuario_id),
        ).fetchone()
    finally:
        conn.close()


def nome_categoria_existe(nome: str, usuario_id: int, ignorar_id: int | None = None) -> bool:
    conn = get_connection()
    try:
        parametros: list[object] = [nome, usuario_id]
        filtro_id = ""
        if ignorar_id is not None:
            filtro_id = "AND id <> ?"
            parametros.append(ignorar_id)
        return conn.execute(
            f"""
            SELECT 1 FROM categorias
            WHERE LOWER(nome) = LOWER(?) AND usuario_id = ? {filtro_id}
            LIMIT 1
            """,
            parametros,
        ).fetchone() is not None
    finally:
        conn.close()


def categoria_em_uso(categoria_id: int, usuario_id: int) -> bool:
    conn = get_connection()
    try:
        em_transacao = conn.execute(
            """
            SELECT 1 FROM transacoes
            WHERE categoria_id = ? AND usuario_id = ?
            LIMIT 1
            """,
            (categoria_id, usuario_id),
        ).fetchone() is not None
        if em_transacao:
            return True
        return conn.execute(
            """
            SELECT 1 FROM compras_cartao
            WHERE categoria_id = ? AND usuario_id = ? LIMIT 1
            """,
            (categoria_id, usuario_id),
        ).fetchone() is not None
    finally:
        conn.close()


def deletar_categoria(categoria_id: int, usuario_id: int) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM categorias WHERE id = ? AND usuario_id = ?",
            (categoria_id, usuario_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def renomear_categoria(categoria_id: int, novo_nome: str, usuario_id: int) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE categorias SET nome = ?
            WHERE id = ? AND usuario_id = ?
            """,
            (novo_nome, categoria_id, usuario_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
