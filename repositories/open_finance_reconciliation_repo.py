import json

from database.connection import DatabaseConnection, get_connection


def listar_transacoes_bancarias_para_conciliacao(usuario_id: int, conexao_id: int | None = None) -> list[tuple]:
    conn = get_connection()
    try:
        filtro = "AND cb.id = ?" if conexao_id is not None else ""
        params = (usuario_id, conexao_id) if conexao_id is not None else (usuario_id,)
        return conn.execute(f"""
            SELECT tb.id, ce.conta_nivra_id, tb.direcao, tb.valor, tb.data,
                   tb.descricao, tb.metadata_provider
            FROM transacoes_bancarias tb
            JOIN contas_bancarias_externas ce ON ce.id = tb.conta_bancaria_externa_id
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            WHERE cb.usuario_id = ? AND cb.desconectada_em IS NULL
              AND ce.conta_nivra_id IS NOT NULL AND tb.removida_em IS NULL
              AND tb.status_conciliacao <> 'conciliada' {filtro}
            ORDER BY tb.data, tb.id
        """, params).fetchall()
    finally:
        conn.close()


def listar_transacoes_manuais_para_conciliacao(usuario_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT t.id, t.conta_id, t.tipo, t.valor, t.data, t.comentario
            FROM transacoes t
            WHERE t.usuario_id = ? AND t.conta_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM correspondencias_conciliacao cc
                  WHERE cc.transacao_nivra_id = t.id AND cc.status = 'confirmada'
              )
            ORDER BY t.data, t.id
        """, (usuario_id,)).fetchall()
    finally:
        conn.close()


def salvar_sugestoes_conciliacao(usuario_id: int, transacao_bancaria_id: int, sugestoes: list[dict]) -> int:
    conn = get_connection()
    try:
        conn.lock_row("transacoes_bancarias", "id", transacao_bancaria_id)
        owner = conn.execute("""
            SELECT tb.id FROM transacoes_bancarias tb
            JOIN contas_bancarias_externas ce ON ce.id = tb.conta_bancaria_externa_id
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            WHERE tb.id = ? AND cb.usuario_id = ? AND tb.removida_em IS NULL
              AND tb.status_conciliacao <> 'conciliada'
        """, (transacao_bancaria_id, usuario_id)).fetchone()
        if owner is None:
            conn.rollback()
            return 0

        current_ids = [int(item["transacao_nivra_id"]) for item in sugestoes]
        for item in sugestoes:
            conn.execute("""
                INSERT INTO correspondencias_conciliacao (
                    usuario_id, transacao_bancaria_id, transacao_nivra_id,
                    status, confianca, score, motivos
                ) VALUES (?, ?, ?, 'sugerida', ?, ?, ?)
                ON CONFLICT (transacao_bancaria_id, transacao_nivra_id) DO UPDATE SET
                    confianca = excluded.confianca, score = excluded.score,
                    motivos = excluded.motivos,
                    status = CASE
                        WHEN correspondencias_conciliacao.status IN ('confirmada', 'rejeitada')
                        THEN correspondencias_conciliacao.status ELSE 'sugerida' END,
                    atualizada_em = CURRENT_TIMESTAMP
            """, (usuario_id, transacao_bancaria_id, item["transacao_nivra_id"], item["confianca"], item["score"], json.dumps(item["motivos"], ensure_ascii=False)))

        if current_ids:
            placeholders = ", ".join("?" for _ in current_ids)
            conn.execute(f"""
                UPDATE correspondencias_conciliacao
                SET status = 'reaberta', atualizada_em = CURRENT_TIMESTAMP
                WHERE usuario_id = ? AND transacao_bancaria_id = ?
                  AND status = 'sugerida' AND transacao_nivra_id NOT IN ({placeholders})
            """, (usuario_id, transacao_bancaria_id, *current_ids))
        else:
            conn.execute("""
                UPDATE correspondencias_conciliacao
                SET status = 'reaberta', atualizada_em = CURRENT_TIMESTAMP
                WHERE usuario_id = ? AND transacao_bancaria_id = ? AND status = 'sugerida'
            """, (usuario_id, transacao_bancaria_id))

        active = conn.execute("""
            SELECT transacao_nivra_id FROM correspondencias_conciliacao
            WHERE usuario_id = ? AND transacao_bancaria_id = ? AND status = 'sugerida'
            ORDER BY score DESC, transacao_nivra_id
        """, (usuario_id, transacao_bancaria_id)).fetchall()
        if len(active) == 1:
            bank_status, target = "possivel_correspondencia", int(active[0][0])
        elif len(active) > 1:
            bank_status, target = "ambigua", None
        else:
            rejected = conn.execute("""
                SELECT 1 FROM correspondencias_conciliacao
                WHERE usuario_id = ? AND transacao_bancaria_id = ? AND status = 'rejeitada'
            """, (usuario_id, transacao_bancaria_id)).fetchone()
            bank_status, target = ("ignorada" if rejected else "pendente"), None
        conn.execute("""
            UPDATE transacoes_bancarias SET status_conciliacao = ?, transacao_nivra_id = ?,
                atualizada_em = CURRENT_TIMESTAMP WHERE id = ?
        """, (bank_status, target, transacao_bancaria_id))
        conn.commit()
        return len(active)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def listar_sugestoes_conciliacao(usuario_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT tb.id, tb.descricao, tb.valor, tb.data, tb.direcao,
                   ce.conta_nivra_id, conta.nome, cb.instituicao_nome,
                   tb.status_conciliacao, cc.transacao_nivra_id, t.comentario,
                   t.valor, t.data, t.tipo, cc.confianca, cc.score, cc.motivos
            FROM correspondencias_conciliacao cc
            JOIN transacoes_bancarias tb ON tb.id = cc.transacao_bancaria_id
            JOIN contas_bancarias_externas ce ON ce.id = tb.conta_bancaria_externa_id
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            JOIN contas conta ON conta.id = ce.conta_nivra_id AND conta.usuario_id = cb.usuario_id
            JOIN transacoes t ON t.id = cc.transacao_nivra_id AND t.usuario_id = cc.usuario_id
            WHERE cc.usuario_id = ? AND cc.status = 'sugerida' AND cb.usuario_id = ?
              AND cb.desconectada_em IS NULL AND tb.removida_em IS NULL
            ORDER BY tb.data DESC, tb.id DESC, cc.score DESC, t.id
        """, (usuario_id, usuario_id)).fetchall()
    finally:
        conn.close()


def buscar_candidato(bank_id: int, manual_id: int, usuario_id: int) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT tb.id, tb.status_conciliacao, t.id, ce.conta_nivra_id,
                   tb.direcao, tb.valor, tb.data, t.conta_id, t.tipo, t.valor,
                   t.data, cc.status, cc.confianca
            FROM correspondencias_conciliacao cc
            JOIN transacoes_bancarias tb ON tb.id = cc.transacao_bancaria_id
            JOIN contas_bancarias_externas ce ON ce.id = tb.conta_bancaria_externa_id
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            JOIN transacoes t ON t.id = cc.transacao_nivra_id AND t.usuario_id = cc.usuario_id
            WHERE cc.transacao_bancaria_id = ? AND cc.transacao_nivra_id = ?
              AND cc.usuario_id = ? AND cb.usuario_id = ? AND cc.status = 'sugerida'
              AND tb.removida_em IS NULL AND cb.desconectada_em IS NULL
        """, (bank_id, manual_id, usuario_id, usuario_id)).fetchone()
    finally:
        conn.close()


def listar_ids_candidatos(bank_id: int, usuario_id: int) -> list[int]:
    conn = get_connection()
    try:
        return [int(row[0]) for row in conn.execute("""
            SELECT cc.transacao_nivra_id FROM correspondencias_conciliacao cc
            JOIN transacoes_bancarias tb ON tb.id = cc.transacao_bancaria_id
            JOIN contas_bancarias_externas ce ON ce.id = tb.conta_bancaria_externa_id
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            WHERE cc.transacao_bancaria_id = ? AND cc.usuario_id = ? AND cb.usuario_id = ?
              AND cc.status = 'sugerida' AND tb.removida_em IS NULL
            ORDER BY cc.score DESC, cc.transacao_nivra_id
        """, (bank_id, usuario_id, usuario_id)).fetchall()]
    finally:
        conn.close()


def confirmar_correspondencia(bank_id: int, manual_id: int, usuario_id: int) -> bool:
    conn = get_connection()
    try:
        conn.lock_row("transacoes_bancarias", "id", bank_id)
        row = conn.execute("""
            SELECT cc.id FROM correspondencias_conciliacao cc
            JOIN transacoes_bancarias tb ON tb.id = cc.transacao_bancaria_id
            JOIN contas_bancarias_externas ce ON ce.id = tb.conta_bancaria_externa_id
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            WHERE cc.transacao_bancaria_id = ? AND cc.transacao_nivra_id = ?
              AND cc.usuario_id = ? AND cb.usuario_id = ? AND cc.status = 'sugerida'
              AND tb.removida_em IS NULL
        """, (bank_id, manual_id, usuario_id, usuario_id)).fetchone()
        if row is None:
            conn.rollback()
            return False
        conn.execute("""
            UPDATE correspondencias_conciliacao SET status = 'reaberta',
                atualizada_em = CURRENT_TIMESTAMP
            WHERE transacao_bancaria_id = ? AND status = 'sugerida'
              AND transacao_nivra_id <> ?
        """, (bank_id, manual_id))
        chosen = conn.execute("""
            UPDATE correspondencias_conciliacao SET status = 'confirmada',
                decidida_em = CURRENT_TIMESTAMP, atualizada_em = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'sugerida'
        """, (int(row[0]),))
        bank = conn.execute("""
            UPDATE transacoes_bancarias SET status_conciliacao = 'conciliada',
                transacao_nivra_id = ?, atualizada_em = CURRENT_TIMESTAMP
            WHERE id = ? AND removida_em IS NULL AND status_conciliacao <> 'conciliada'
        """, (manual_id, bank_id))
        if chosen.rowcount != 1 or bank.rowcount != 1:
            conn.rollback()
            return False
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def rejeitar_correspondencia(bank_id: int, manual_id: int, usuario_id: int) -> bool:
    conn = get_connection()
    try:
        conn.lock_row("transacoes_bancarias", "id", bank_id)
        updated = conn.execute("""
            UPDATE correspondencias_conciliacao SET status = 'rejeitada',
                decidida_em = CURRENT_TIMESTAMP, atualizada_em = CURRENT_TIMESTAMP
            WHERE transacao_bancaria_id = ? AND transacao_nivra_id = ?
              AND usuario_id = ? AND status = 'sugerida'
              AND EXISTS (
                SELECT 1 FROM transacoes_bancarias tb
                JOIN contas_bancarias_externas ce ON ce.id = tb.conta_bancaria_externa_id
                JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
                WHERE tb.id = ? AND cb.usuario_id = ? AND tb.removida_em IS NULL
              )
        """, (bank_id, manual_id, usuario_id, bank_id, usuario_id))
        if updated.rowcount != 1:
            conn.rollback()
            return False
        remaining = conn.execute("""
            SELECT transacao_nivra_id FROM correspondencias_conciliacao
            WHERE transacao_bancaria_id = ? AND status = 'sugerida'
            ORDER BY score DESC, transacao_nivra_id
        """, (bank_id,)).fetchall()
        bank_status = "possivel_correspondencia" if len(remaining) == 1 else "ambigua" if remaining else "ignorada"
        target = int(remaining[0][0]) if len(remaining) == 1 else None
        conn.execute("""
            UPDATE transacoes_bancarias SET status_conciliacao = ?,
                transacao_nivra_id = ?, atualizada_em = CURRENT_TIMESTAMP WHERE id = ?
        """, (bank_status, target, bank_id))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reabrir_correspondencias(conn: DatabaseConnection, bank_ids: list[int]) -> None:
    if not bank_ids:
        return
    placeholders = ", ".join("?" for _ in bank_ids)
    conn.execute(f"""
        UPDATE correspondencias_conciliacao SET status = 'reaberta',
            atualizada_em = CURRENT_TIMESTAMP
        WHERE transacao_bancaria_id IN ({placeholders})
          AND status IN ('sugerida', 'confirmada', 'rejeitada')
    """, bank_ids)


def marcar_bancos_ambiguos(usuario_id: int, bank_ids: list[int]) -> None:
    if not bank_ids:
        return
    conn = get_connection()
    try:
        placeholders = ", ".join("?" for _ in bank_ids)
        conn.execute(f"""
            UPDATE transacoes_bancarias SET status_conciliacao = 'ambigua',
                transacao_nivra_id = NULL, atualizada_em = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders}) AND removida_em IS NULL
              AND id IN (
                SELECT cc.transacao_bancaria_id FROM correspondencias_conciliacao cc
                WHERE cc.usuario_id = ? AND cc.status = 'sugerida'
              )
        """, (*bank_ids, usuario_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Compatibilidade com a API básica anterior.
listar_transacoes_bancarias_pendentes = listar_transacoes_bancarias_para_conciliacao


def buscar_correspondencia(bank_id: int, usuario_id: int) -> tuple | None:
    ids = listar_ids_candidatos(bank_id, usuario_id)
    return buscar_candidato(bank_id, ids[0], usuario_id) if len(ids) == 1 else None


def marcar_possiveis_correspondencias(usuario_id: int, correspondencias: list[tuple[int, int]]) -> int:
    total = 0
    for bank_id, manual_id in correspondencias:
        total += int(salvar_sugestoes_conciliacao(usuario_id, bank_id, [{
            "transacao_nivra_id": manual_id, "confianca": "alta", "score": 90,
            "motivos": ["mesma_conta", "mesmo_valor", "mesma_direcao", "data_proxima"],
        }]) > 0)
    return total
