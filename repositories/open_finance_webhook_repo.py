import json

from database.connection import get_connection
from repositories.open_finance_reconciliation_repo import reabrir_correspondencias


def buscar_conexao_por_item(provider: str, external_item_id: str) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, usuario_id, client_user_ref, status, desconectada_em
            FROM conexoes_bancarias
            WHERE provider = ? AND external_item_id = ?
            """,
            (provider, external_item_id),
        ).fetchone()
    finally:
        conn.close()


def registrar_evento_webhook(
    provider: str,
    provider_event_id: str,
    tipo: str,
    external_item_id: str | None,
    conexao_id: int | None,
    payload_hash: str,
) -> tuple:
    conn = get_connection()
    try:
        inserted = conn.execute(
            """
            INSERT INTO eventos_webhook_open_finance (
                provider, provider_event_id, tipo, external_item_id,
                conexao_id, status, payload_hash
            ) VALUES (?, ?, ?, ?, ?, 'recebido', ?)
            ON CONFLICT (provider, provider_event_id) DO NOTHING
            RETURNING id
            """,
            (
                provider,
                provider_event_id,
                tipo,
                external_item_id,
                conexao_id,
                payload_hash,
            ),
        ).fetchone()
        row = conn.execute(
            """
            SELECT id, status, payload_hash, tentativas, conexao_id
            FROM eventos_webhook_open_finance
            WHERE provider = ? AND provider_event_id = ?
            """,
            (provider, provider_event_id),
        ).fetchone()
        conn.commit()
        if row is None:
            raise RuntimeError("Nao foi possivel registrar o evento do webhook.")
        return (*row, inserted is not None)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reivindicar_evento_webhook(
    evento_id: int,
    conexao_id: int | None,
) -> bool:
    conn = get_connection()
    try:
        stale_expression = (
            "CURRENT_TIMESTAMP - INTERVAL '5 minutes'"
            if conn.dialect_name == "postgresql"
            else "datetime('now', '-5 minutes')"
        )
        result = conn.execute(
            f"""
            UPDATE eventos_webhook_open_finance
            SET status = 'processando',
                tentativas = CASE
                    WHEN status = 'recebido' THEN tentativas
                    ELSE tentativas + 1
                END,
                conexao_id = COALESCE(?, conexao_id),
                ultima_tentativa_em = CURRENT_TIMESTAMP,
                processado_em = NULL, codigo_erro = NULL, mensagem_erro = NULL
            WHERE id = ?
              AND (
                  status IN ('recebido', 'erro')
                  OR (
                      status = 'processando'
                      AND ultima_tentativa_em < {stale_expression}
                  )
              )
            """,
            (conexao_id, evento_id),
        )
        conn.commit()
        return result.rowcount == 1
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def finalizar_evento_webhook(
    evento_id: int,
    status: str,
    quantidade_processada: int = 0,
    codigo_erro: str | None = None,
    mensagem_erro: str | None = None,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE eventos_webhook_open_finance
            SET status = ?, quantidade_processada = ?,
                codigo_erro = ?, mensagem_erro = ?,
                processado_em = CURRENT_TIMESTAMP,
                ultima_tentativa_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                quantidade_processada,
                codigo_erro[:80] if codigo_erro else None,
                mensagem_erro[:500] if mensagem_erro else None,
                evento_id,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def buscar_conta_externa_por_identificador(
    conexao_id: int,
    external_account_id: str,
) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, tipo
            FROM contas_bancarias_externas
            WHERE conexao_id = ? AND external_account_id = ?
            """,
            (conexao_id, external_account_id),
        ).fetchone()
    finally:
        conn.close()


def persistir_transacoes_webhook(
    conexao_id: int,
    conta_externa_id: int,
    transacoes: list[dict],
) -> dict[str, int]:
    conn = get_connection()
    try:
        conn.lock_row("conexoes_bancarias", "id", conexao_id)
        existing = {
            str(row[0]): row[1:]
            for row in conn.execute(
                """
                SELECT external_transaction_id, id, valor, data, direcao, removida_em
                FROM transacoes_bancarias
                WHERE conta_bancaria_externa_id = ?
                """,
                (conta_externa_id,),
            ).fetchall()
        }
        metadata_placeholder = "CAST(? AS JSONB)" if conn.dialect_name == "postgresql" else "?"
        created = 0
        updated = 0
        for transaction in transacoes:
            external_transaction_id = str(transaction["external_transaction_id"])
            previous = existing.get(external_transaction_id)
            persisted = conn.execute(
                f"""
                INSERT INTO transacoes_bancarias (
                    conta_bancaria_externa_id, external_transaction_id,
                    descricao, valor, data, direcao, metadata_provider
                ) VALUES (?, ?, ?, ?, ?, ?, {metadata_placeholder})
                ON CONFLICT (
                    conta_bancaria_externa_id, external_transaction_id
                ) DO UPDATE SET
                    descricao = excluded.descricao,
                    valor = excluded.valor,
                    data = excluded.data,
                    direcao = excluded.direcao,
                    metadata_provider = excluded.metadata_provider,
                    removida_em = NULL,
                    status_conciliacao = CASE
                        WHEN transacoes_bancarias.valor <> excluded.valor
                          OR transacoes_bancarias.data <> excluded.data
                          OR transacoes_bancarias.direcao <> excluded.direcao
                        THEN 'pendente'
                        ELSE transacoes_bancarias.status_conciliacao
                    END,
                    transacao_nivra_id = CASE
                        WHEN transacoes_bancarias.valor <> excluded.valor
                          OR transacoes_bancarias.data <> excluded.data
                          OR transacoes_bancarias.direcao <> excluded.direcao
                        THEN NULL
                        ELSE transacoes_bancarias.transacao_nivra_id
                    END,
                    atualizada_em = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (
                    conta_externa_id,
                    external_transaction_id,
                    transaction["descricao"],
                    str(transaction["valor"]),
                    transaction["data"],
                    transaction["direcao"],
                    json.dumps(transaction["metadata_provider"], ensure_ascii=False),
                ),
            ).fetchone()
            if persisted is None:
                raise RuntimeError("Nao foi possivel persistir a transacao externa.")
            if previous is not None:
                _, old_value, old_date, old_direction, old_removed = previous
                changed = (
                    float(old_value) != float(transaction["valor"])
                    or str(old_date) != str(transaction["data"])
                    or str(old_direction) != str(transaction["direcao"])
                    or old_removed is not None
                )
                if changed:
                    reabrir_correspondencias(conn, [int(persisted[0])])
            if external_transaction_id in existing:
                updated += 1
            else:
                created += 1
        conn.execute(
            """
            UPDATE conexoes_bancarias
            SET ultima_sincronizacao_em = CURRENT_TIMESTAMP,
                atualizada_em = CURRENT_TIMESTAMP,
                status = 'active'
            WHERE id = ?
            """,
            (conexao_id,),
        )
        conn.commit()
        return {"criadas": created, "atualizadas": updated}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def excluir_transacoes_webhook(
    conexao_id: int,
    conta_externa_id: int,
    external_transaction_ids: list[str],
) -> int:
    if not external_transaction_ids:
        return 0
    conn = get_connection()
    try:
        conn.lock_row("conexoes_bancarias", "id", conexao_id)
        placeholders = ", ".join("?" for _ in external_transaction_ids)
        rows = conn.execute(
            f"""
            SELECT id FROM transacoes_bancarias
            WHERE conta_bancaria_externa_id = ?
              AND external_transaction_id IN ({placeholders})
              AND removida_em IS NULL
            """,
            (conta_externa_id, *external_transaction_ids),
        ).fetchall()
        bank_ids = [int(row[0]) for row in rows]
        if bank_ids:
            id_placeholders = ", ".join("?" for _ in bank_ids)
            reabrir_correspondencias(conn, bank_ids)
            conn.execute(
                f"""
                UPDATE transacoes_bancarias
                SET removida_em = CURRENT_TIMESTAMP, status_conciliacao = 'reaberta',
                    transacao_nivra_id = NULL, atualizada_em = CURRENT_TIMESTAMP
                WHERE id IN ({id_placeholders})
                """,
                bank_ids,
            )
        conn.execute(
            """
            UPDATE conexoes_bancarias
            SET ultima_sincronizacao_em = CURRENT_TIMESTAMP,
                atualizada_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (conexao_id,),
        )
        conn.commit()
        return len(bank_ids)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def registrar_erro_conexao_webhook(
    conexao_id: int,
    codigo: str,
    mensagem: str,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE conexoes_bancarias
            SET status = 'error', atualizada_em = CURRENT_TIMESTAMP
            WHERE id = ? AND desconectada_em IS NULL
            """,
            (conexao_id,),
        )
        conn.execute(
            """
            INSERT INTO eventos_sincronizacao (
                conexao_id, tipo, origem, status, finalizada_em,
                codigo_erro, mensagem_erro
            ) VALUES (?, 'item/error', 'webhook', 'erro', CURRENT_TIMESTAMP, ?, ?)
            """,
            (conexao_id, codigo[:80], mensagem[:500]),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def marcar_conexao_externa_excluida(conexao_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE conexoes_bancarias
            SET status = 'disconnected', desconectada_em = CURRENT_TIMESTAMP,
                atualizada_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (conexao_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
