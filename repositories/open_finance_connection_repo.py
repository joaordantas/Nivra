from database.connection import get_connection


CONNECTION_SELECT = """
    SELECT id, usuario_id, provider, external_item_id, client_user_ref,
           external_connector_id, instituicao_nome, status, ambiente,
           criada_em, atualizada_em, ultima_sincronizacao_em, desconectada_em
    FROM conexoes_bancarias
"""


def criar_ou_obter_conexao_bancaria(
    usuario_id: int,
    provider: str,
    external_item_id: str,
    client_user_ref: str,
    external_connector_id: int | None,
    instituicao_nome: str,
    status: str,
    ambiente: str,
) -> tuple:
    conn = get_connection()
    try:
        inserida = conn.execute(
            """
            INSERT INTO conexoes_bancarias (
                usuario_id, provider, external_item_id, client_user_ref,
                external_connector_id, instituicao_nome, status, ambiente
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (provider, external_item_id) DO NOTHING
            RETURNING id
            """,
            (
                usuario_id,
                provider,
                external_item_id,
                client_user_ref,
                external_connector_id,
                instituicao_nome,
                status,
                ambiente,
            ),
        ).fetchone()
        if inserida is not None:
            conexao = conn.execute(
                f"{CONNECTION_SELECT} WHERE id = ?",
                (int(inserida[0]),),
            ).fetchone()
        else:
            conexao = conn.execute(
                f"{CONNECTION_SELECT} WHERE provider = ? AND external_item_id = ?",
                (provider, external_item_id),
            ).fetchone()
        conn.commit()
        if conexao is None:
            raise RuntimeError("Nao foi possivel persistir a conexao bancaria.")
        return conexao
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def listar_conexoes_bancarias(usuario_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute(
            f"""{CONNECTION_SELECT}
            WHERE usuario_id = ?
            ORDER BY desconectada_em IS NOT NULL, criada_em DESC, id DESC
            """,
            (usuario_id,),
        ).fetchall()
    finally:
        conn.close()
