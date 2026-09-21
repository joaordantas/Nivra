from database.connection import get_connection


def listar_compras_cartao_periodo(
    usuario_id: int,
    data_inicio: str,
    data_fim: str,
) -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT cp.id, cp.valor, cp.descricao, cp.data,
                   cp.categoria_id, COALESCE(cat.nome, 'Sem categoria'),
                   cat.chave_sistema, cp.cartao_id, c.nome
            FROM compras_cartao cp
            JOIN cartoes c
              ON c.id = cp.cartao_id AND c.usuario_id = cp.usuario_id
            LEFT JOIN categorias cat
              ON cat.id = cp.categoria_id AND cat.usuario_id = cp.usuario_id
            WHERE cp.usuario_id = ? AND cp.data >= ? AND cp.data <= ?
            ORDER BY cp.data DESC, cp.id DESC
            """,
            (usuario_id, data_inicio, data_fim),
        ).fetchall()
    finally:
        conn.close()
