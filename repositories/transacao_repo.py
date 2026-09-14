from database.connection import get_connection


TRANSACTION_SELECT = """
    SELECT t.id, t.valor, t.tipo, t.categoria_id,
           COALESCE(c.nome, 'Sem categoria') AS categoria,
           t.comentario, t.data, t.conta_id,
           COALESCE(conta.nome, 'Sem conta') AS conta,
           tb.id AS transacao_bancaria_id,
           cb.instituicao_nome,
           cb.ultima_sincronizacao_em,
           t.parcelamento_id, t.numero_parcela, p.quantidade_parcelas
    FROM transacoes t
    LEFT JOIN categorias c ON c.id = t.categoria_id
    LEFT JOIN contas conta ON conta.id = t.conta_id
    LEFT JOIN transacoes_bancarias tb
      ON tb.transacao_nivra_id = t.id
     AND tb.status_conciliacao = 'conciliada'
     AND tb.removida_em IS NULL
    LEFT JOIN contas_bancarias_externas ce
      ON ce.id = tb.conta_bancaria_externa_id
    LEFT JOIN conexoes_bancarias cb
      ON cb.id = ce.conexao_id AND cb.usuario_id = t.usuario_id
    LEFT JOIN parcelamentos p
      ON p.id = t.parcelamento_id AND p.usuario_id = t.usuario_id
"""


def adicionar_transacao(
    valor: float,
    tipo: str,
    categoria_id: int | None,
    comentario: str | None,
    data: str,
    usuario_id: int,
    conta_id: int | None = None,
) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO transacoes (
                valor, tipo, categoria_id, comentario, data, usuario_id, conta_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id
            """,
            (valor, tipo, categoria_id, comentario, data, usuario_id, conta_id),
        )
        transacao_id = int(cursor.fetchone()[0])
        conn.commit()
        return transacao_id
    finally:
        conn.close()


def listar_transacoes(
    usuario_id: int,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> list[tuple]:
    conn = get_connection()
    try:
        filtros = ["t.usuario_id = ?"]
        parametros: list[object] = [usuario_id]
        if data_inicio is not None:
            filtros.append("t.data >= ?")
            parametros.append(data_inicio)
        if data_fim is not None:
            filtros.append("t.data <= ?")
            parametros.append(data_fim)
        return conn.execute(
            f"""
            {TRANSACTION_SELECT}
            WHERE {' AND '.join(filtros)}
            ORDER BY t.data DESC, t.id DESC
            """,
            parametros,
        ).fetchall()
    finally:
        conn.close()


def listar_transacoes_bancarias_vinculadas(
    usuario_id: int,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> list[tuple]:
    conn = get_connection()
    try:
        filtros = [
            "cb.usuario_id = ?",
            "cb.desconectada_em IS NULL",
            "ce.conta_nivra_id IS NOT NULL",
            "NOT (tb.status_conciliacao = 'conciliada' AND tb.transacao_nivra_id IS NOT NULL)",
            "tb.removida_em IS NULL",
        ]
        parametros: list[object] = [usuario_id]
        if data_inicio is not None:
            filtros.append("tb.data >= ?")
            parametros.append(data_inicio)
        if data_fim is not None:
            filtros.append("tb.data <= ?")
            parametros.append(data_fim)
        return conn.execute(
            f"""
            SELECT tb.id, tb.valor, tb.direcao, tb.descricao, tb.data,
                   ce.conta_nivra_id, c.nome, tb.metadata_provider,
                   tb.status_conciliacao, tb.transacao_nivra_id,
                   cb.instituicao_nome, cb.ultima_sincronizacao_em
            FROM transacoes_bancarias tb
            JOIN contas_bancarias_externas ce
              ON ce.id = tb.conta_bancaria_externa_id
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            JOIN contas c
              ON c.id = ce.conta_nivra_id AND c.usuario_id = cb.usuario_id
            WHERE {' AND '.join(filtros)}
            ORDER BY tb.data DESC, tb.id DESC
            """,
            parametros,
        ).fetchall()
    finally:
        conn.close()


def buscar_transacao_por_id(transacao_id: int, usuario_id: int) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            f"""{TRANSACTION_SELECT}
            WHERE t.id = ? AND t.usuario_id = ?
            """,
            (transacao_id, usuario_id),
        ).fetchone()
    finally:
        conn.close()


def buscar_parcelamento_da_transacao(
    transacao_id: int, usuario_id: int
) -> tuple[int, int] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT parcelamento_id, numero_parcela
            FROM transacoes
            WHERE id = ? AND usuario_id = ? AND parcelamento_id IS NOT NULL
            """,
            (transacao_id, usuario_id),
        ).fetchone()
        if row is None:
            return None
        return int(row[0]), int(row[1])
    finally:
        conn.close()


def atualizar_transacao(
    transacao_id: int,
    valor: float,
    tipo: str,
    categoria_id: int | None,
    comentario: str | None,
    data: str,
    conta_id: int | None,
    usuario_id: int,
) -> bool:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE correspondencias_conciliacao
            SET status = 'reaberta', atualizada_em = CURRENT_TIMESTAMP
            WHERE transacao_nivra_id = ? AND status IN ('sugerida', 'confirmada')
            """,
            (transacao_id,),
        )
        conn.execute(
            """
            UPDATE transacoes_bancarias
            SET status_conciliacao = 'pendente',
                transacao_nivra_id = NULL,
                atualizada_em = CURRENT_TIMESTAMP
            WHERE transacao_nivra_id = ?
            """,
            (transacao_id,),
        )
        cursor = conn.execute(
            """
            UPDATE transacoes
            SET valor = ?, tipo = ?, categoria_id = ?, comentario = ?, data = ?, conta_id = ?
            WHERE id = ? AND usuario_id = ?
            """,
            (
                valor,
                tipo,
                categoria_id,
                comentario,
                data,
                conta_id,
                transacao_id,
                usuario_id,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def deletar_transacao(transacao_id: int, usuario_id: int) -> bool:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE correspondencias_conciliacao
            SET status = 'reaberta', atualizada_em = CURRENT_TIMESTAMP
            WHERE transacao_nivra_id = ? AND status IN ('sugerida', 'confirmada')
            """,
            (transacao_id,),
        )
        conn.execute(
            """
            UPDATE transacoes_bancarias
            SET status_conciliacao = 'pendente',
                transacao_nivra_id = NULL,
                atualizada_em = CURRENT_TIMESTAMP
            WHERE transacao_nivra_id = ?
              AND EXISTS (
                  SELECT 1 FROM transacoes
                  WHERE id = ? AND usuario_id = ?
              )
            """,
            (transacao_id, transacao_id, usuario_id),
        )
        cursor = conn.execute(
            "DELETE FROM transacoes WHERE id = ? AND usuario_id = ?",
            (transacao_id, usuario_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def calcular_total_compras_cartao(
    usuario_id: int,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> float:
    conn = get_connection()
    try:
        filtros = ["usuario_id = ?"]
        parametros: list[object] = [usuario_id]
        if data_inicio is not None:
            filtros.append("data >= ?")
            parametros.append(data_inicio)
        if data_fim is not None:
            filtros.append("data <= ?")
            parametros.append(data_fim)
        row = conn.execute(
            f"""
            SELECT COALESCE(SUM(valor), 0)
            FROM compras_cartao
            WHERE {' AND '.join(filtros)}
            """,
            parametros,
        ).fetchone()
        return float(row[0] if row else 0)
    finally:
        conn.close()
