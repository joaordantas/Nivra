from database.connection import get_connection


def listar_transacoes_bancarias_pendentes(
    usuario_id: int,
    conexao_id: int | None = None,
) -> list[tuple]:
    conn = get_connection()
    try:
        filtro_conexao = "AND cb.id = ?" if conexao_id is not None else ""
        parametros = (usuario_id, conexao_id) if conexao_id is not None else (usuario_id,)
        return conn.execute(
            f"""
            SELECT tb.id, ce.conta_nivra_id, tb.direcao, tb.valor, tb.data
            FROM transacoes_bancarias tb
            JOIN contas_bancarias_externas ce
              ON ce.id = tb.conta_bancaria_externa_id
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            WHERE cb.usuario_id = ?
              AND cb.desconectada_em IS NULL
              AND ce.conta_nivra_id IS NOT NULL
              AND tb.status_conciliacao = 'pendente'
              {filtro_conexao}
            ORDER BY tb.data, tb.id
            """,
            parametros,
        ).fetchall()
    finally:
        conn.close()


def listar_transacoes_manuais_para_conciliacao(usuario_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT t.id, t.conta_id, t.tipo, t.valor, t.data
            FROM transacoes t
            WHERE t.usuario_id = ?
              AND t.conta_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM transacoes_bancarias tb
                  WHERE tb.transacao_nivra_id = t.id
                    AND tb.status_conciliacao IN (
                        'possivel_correspondencia', 'conciliada'
                    )
              )
            ORDER BY t.data, t.id
            """,
            (usuario_id,),
        ).fetchall()
    finally:
        conn.close()


def marcar_possiveis_correspondencias(
    usuario_id: int,
    correspondencias: list[tuple[int, int]],
) -> int:
    if not correspondencias:
        return 0
    conn = get_connection()
    try:
        atualizadas = 0
        for transacao_bancaria_id, transacao_nivra_id in correspondencias:
            conn.lock_row("transacoes_bancarias", "id", transacao_bancaria_id)
            resultado = conn.execute(
                """
                UPDATE transacoes_bancarias
                SET status_conciliacao = 'possivel_correspondencia',
                    transacao_nivra_id = ?,
                    atualizada_em = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND status_conciliacao = 'pendente'
                  AND conta_bancaria_externa_id IN (
                      SELECT ce.id
                      FROM contas_bancarias_externas ce
                      JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
                      WHERE cb.usuario_id = ?
                        AND cb.desconectada_em IS NULL
                  )
                  AND EXISTS (
                      SELECT 1 FROM transacoes t
                      WHERE t.id = ? AND t.usuario_id = ?
                  )
                """,
                (
                    transacao_nivra_id,
                    transacao_bancaria_id,
                    usuario_id,
                    transacao_nivra_id,
                    usuario_id,
                ),
            )
            atualizadas += resultado.rowcount
        conn.commit()
        return atualizadas
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def buscar_correspondencia(
    transacao_bancaria_id: int,
    usuario_id: int,
) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT tb.id, tb.status_conciliacao, tb.transacao_nivra_id,
                   ce.conta_nivra_id, tb.direcao, tb.valor, tb.data,
                   t.conta_id, t.tipo, t.valor, t.data
            FROM transacoes_bancarias tb
            JOIN contas_bancarias_externas ce
              ON ce.id = tb.conta_bancaria_externa_id
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            LEFT JOIN transacoes t
              ON t.id = tb.transacao_nivra_id AND t.usuario_id = cb.usuario_id
            WHERE tb.id = ?
              AND cb.usuario_id = ?
              AND cb.desconectada_em IS NULL
            """,
            (transacao_bancaria_id, usuario_id),
        ).fetchone()
    finally:
        conn.close()


def confirmar_correspondencia(
    transacao_bancaria_id: int,
    usuario_id: int,
) -> bool:
    conn = get_connection()
    try:
        conn.lock_row("transacoes_bancarias", "id", transacao_bancaria_id)
        resultado = conn.execute(
            """
            UPDATE transacoes_bancarias
            SET status_conciliacao = 'conciliada',
                atualizada_em = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status_conciliacao = 'possivel_correspondencia'
              AND transacao_nivra_id IS NOT NULL
              AND conta_bancaria_externa_id IN (
                  SELECT ce.id
                  FROM contas_bancarias_externas ce
                  JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
                  WHERE cb.usuario_id = ?
                    AND cb.desconectada_em IS NULL
              )
            """,
            (transacao_bancaria_id, usuario_id),
        )
        if resultado.rowcount != 1:
            conn.rollback()
            return False
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rejeitar_correspondencia(
    transacao_bancaria_id: int,
    usuario_id: int,
) -> bool:
    conn = get_connection()
    try:
        conn.lock_row("transacoes_bancarias", "id", transacao_bancaria_id)
        resultado = conn.execute(
            """
            UPDATE transacoes_bancarias
            SET status_conciliacao = 'ignorada',
                transacao_nivra_id = NULL,
                atualizada_em = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status_conciliacao = 'possivel_correspondencia'
              AND conta_bancaria_externa_id IN (
                  SELECT ce.id
                  FROM contas_bancarias_externas ce
                  JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
                  WHERE cb.usuario_id = ?
                    AND cb.desconectada_em IS NULL
              )
            """,
            (transacao_bancaria_id, usuario_id),
        )
        if resultado.rowcount != 1:
            conn.rollback()
            return False
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
