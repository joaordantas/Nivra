import json

from database.connection import get_connection
from repositories.open_finance_reconciliation_repo import reabrir_correspondencias


def buscar_conexao_para_sincronizacao(conexao_id: int, usuario_id: int) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, usuario_id, provider, external_item_id, client_user_ref,
                   instituicao_nome, status
            FROM conexoes_bancarias
            WHERE id = ? AND usuario_id = ? AND desconectada_em IS NULL
            """,
            (conexao_id, usuario_id),
        ).fetchone()
    finally:
        conn.close()


def iniciar_evento_sincronizacao(conexao_id: int, usuario_id: int) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            INSERT INTO eventos_sincronizacao (conexao_id, tipo, origem, status)
            SELECT id, 'full_sync', 'manual', 'em_andamento'
            FROM conexoes_bancarias
            WHERE id = ? AND usuario_id = ? AND desconectada_em IS NULL
            RETURNING id
            """,
            (conexao_id, usuario_id),
        ).fetchone()
        if row is None:
            conn.rollback()
            raise ValueError("Conexao bancaria nao encontrada.")
        conn.commit()
        return int(row[0])
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def finalizar_evento_com_falha(
    evento_id: int,
    usuario_id: int,
    codigo_erro: str,
    mensagem_erro: str,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE eventos_sincronizacao
            SET status = 'erro', finalizada_em = CURRENT_TIMESTAMP,
                codigo_erro = ?, mensagem_erro = ?
            WHERE id = ? AND conexao_id IN (
                SELECT id FROM conexoes_bancarias WHERE usuario_id = ?
            )
            """,
            (codigo_erro[:80], mensagem_erro[:500], evento_id, usuario_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _delete_missing(
    conn,
    table: str,
    owner_column: str,
    owner_id: int,
    external_column: str,
    external_ids: list[str],
) -> int:
    if external_ids:
        placeholders = ", ".join("?" for _ in external_ids)
        result = conn.execute(
            f"""
            DELETE FROM {table}
            WHERE {owner_column} = ?
              AND {external_column} NOT IN ({placeholders})
            """,
            (owner_id, *external_ids),
        )
    else:
        result = conn.execute(
            f"DELETE FROM {table} WHERE {owner_column} = ?",
            (owner_id,),
        )
    return result.rowcount


def _mark_missing_transactions_removed(
    conn,
    external_account_id: int,
    current_external_ids: list[str],
) -> int:
    filters = ["conta_bancaria_externa_id = ?", "removida_em IS NULL"]
    params: list[object] = [external_account_id]
    if current_external_ids:
        placeholders = ", ".join("?" for _ in current_external_ids)
        filters.append(f"external_transaction_id NOT IN ({placeholders})")
        params.extend(current_external_ids)
    rows = conn.execute(
        f"SELECT id FROM transacoes_bancarias WHERE {' AND '.join(filters)}",
        params,
    ).fetchall()
    bank_ids = [int(row[0]) for row in rows]
    if not bank_ids:
        return 0
    placeholders = ", ".join("?" for _ in bank_ids)
    reabrir_correspondencias(conn, bank_ids)
    conn.execute(
        f"""
        UPDATE transacoes_bancarias
        SET removida_em = CURRENT_TIMESTAMP, status_conciliacao = 'reaberta',
            transacao_nivra_id = NULL, atualizada_em = CURRENT_TIMESTAMP
        WHERE id IN ({placeholders})
        """,
        bank_ids,
    )
    return len(bank_ids)


def persistir_snapshot_sincronizacao(
    conexao_id: int,
    usuario_id: int,
    evento_id: int,
    instituicao_nome: str,
    status_conexao: str,
    contas: list[dict],
) -> dict[str, int]:
    conn = get_connection()
    try:
        conn.lock_row("conexoes_bancarias", "id", conexao_id)
        ownership = conn.execute(
            """
            SELECT id FROM conexoes_bancarias
            WHERE id = ? AND usuario_id = ? AND desconectada_em IS NULL
            """,
            (conexao_id, usuario_id),
        ).fetchone()
        if ownership is None:
            raise ValueError("Conexao bancaria nao encontrada.")

        existing_accounts = {
            str(row[0]): int(row[1])
            for row in conn.execute(
                """
                SELECT external_account_id, id
                FROM contas_bancarias_externas
                WHERE conexao_id = ?
                """,
                (conexao_id,),
            ).fetchall()
        }
        created_accounts = 0
        updated_accounts = 0
        created_transactions = 0
        updated_transactions = 0
        deleted_transactions = 0
        current_account_ids: list[str] = []
        metadata_placeholder = "CAST(? AS JSONB)" if conn.dialect_name == "postgresql" else "?"

        for account in contas:
            external_account_id = str(account["external_account_id"])
            current_account_ids.append(external_account_id)
            account_row = conn.execute(
                """
                INSERT INTO contas_bancarias_externas (
                    conexao_id, external_account_id, nome, tipo, subtipo, moeda, saldo
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (conexao_id, external_account_id) DO UPDATE SET
                    nome = excluded.nome,
                    tipo = excluded.tipo,
                    subtipo = excluded.subtipo,
                    moeda = excluded.moeda,
                    saldo = excluded.saldo,
                    atualizada_em = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (
                    conexao_id,
                    external_account_id,
                    account["nome"],
                    account["tipo"],
                    account["subtipo"],
                    account["moeda"],
                    str(account["saldo"]) if account["saldo"] is not None else None,
                ),
            ).fetchone()
            if account_row is None:
                raise RuntimeError("Nao foi possivel persistir a conta externa.")
            external_account_pk = int(account_row[0])
            if external_account_id in existing_accounts:
                updated_accounts += 1
            else:
                created_accounts += 1

            existing_transactions = {
                str(row[0]): row[1:]
                for row in conn.execute(
                    """
                    SELECT external_transaction_id, id, valor, data, direcao, removida_em
                    FROM transacoes_bancarias
                    WHERE conta_bancaria_externa_id = ?
                    """,
                    (external_account_pk,),
                ).fetchall()
            }
            current_transaction_ids: list[str] = []
            for transaction in account["transacoes"]:
                external_transaction_id = str(transaction["external_transaction_id"])
                current_transaction_ids.append(external_transaction_id)
                previous = existing_transactions.get(external_transaction_id)
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
                        external_account_pk,
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
                if external_transaction_id in existing_transactions:
                    updated_transactions += 1
                else:
                    created_transactions += 1

            deleted_transactions += _mark_missing_transactions_removed(
                conn, external_account_pk, current_transaction_ids
            )

        if current_account_ids:
            placeholders = ", ".join("?" for _ in current_account_ids)
            cascaded_transactions = conn.execute(
                f"""
                SELECT COUNT(tb.id)
                FROM transacoes_bancarias tb
                JOIN contas_bancarias_externas ce
                  ON ce.id = tb.conta_bancaria_externa_id
                WHERE ce.conexao_id = ?
                  AND ce.external_account_id NOT IN ({placeholders})
                """,
                (conexao_id, *current_account_ids),
            ).fetchone()[0]
        else:
            cascaded_transactions = conn.execute(
                """
                SELECT COUNT(tb.id)
                FROM transacoes_bancarias tb
                JOIN contas_bancarias_externas ce
                  ON ce.id = tb.conta_bancaria_externa_id
                WHERE ce.conexao_id = ?
                """,
                (conexao_id,),
            ).fetchone()[0]
        deleted_transactions += int(cascaded_transactions)
        deleted_accounts = _delete_missing(
            conn,
            "contas_bancarias_externas",
            "conexao_id",
            conexao_id,
            "external_account_id",
            current_account_ids,
        )
        processed = sum(len(account["transacoes"]) for account in contas)
        conn.execute(
            """
            UPDATE conexoes_bancarias
            SET instituicao_nome = ?, status = ?,
                ultima_sincronizacao_em = CURRENT_TIMESTAMP,
                atualizada_em = CURRENT_TIMESTAMP
            WHERE id = ? AND usuario_id = ?
            """,
            (instituicao_nome, status_conexao, conexao_id, usuario_id),
        )
        event_updated = conn.execute(
            """
            UPDATE eventos_sincronizacao
            SET status = 'sucesso', finalizada_em = CURRENT_TIMESTAMP,
                quantidade_processada = ?, codigo_erro = NULL, mensagem_erro = NULL
            WHERE id = ? AND conexao_id = ?
            """,
            (processed, evento_id, conexao_id),
        )
        if event_updated.rowcount != 1:
            raise RuntimeError("Evento de sincronizacao nao encontrado.")
        conn.commit()
        return {
            "contas_criadas": created_accounts,
            "contas_atualizadas": updated_accounts,
            "contas_removidas": deleted_accounts,
            "transacoes_criadas": created_transactions,
            "transacoes_atualizadas": updated_transactions,
            "transacoes_removidas": deleted_transactions,
            "transacoes_processadas": processed,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def listar_contas_externas(conexao_id: int, usuario_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT ce.id, ce.nome, ce.tipo, ce.subtipo, ce.moeda, ce.saldo,
                   COUNT(tb.id) AS quantidade_transacoes,
                   ce.conta_nivra_id, c.nome AS conta_nivra_nome
            FROM contas_bancarias_externas ce
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            LEFT JOIN contas c ON c.id = ce.conta_nivra_id
            LEFT JOIN transacoes_bancarias tb
                   ON tb.conta_bancaria_externa_id = ce.id AND tb.removida_em IS NULL
            WHERE ce.conexao_id = ? AND cb.usuario_id = ?
            GROUP BY ce.id, ce.nome, ce.tipo, ce.subtipo, ce.moeda, ce.saldo,
                     ce.conta_nivra_id, c.nome
            ORDER BY LOWER(ce.nome), ce.id
            """,
            (conexao_id, usuario_id),
        ).fetchall()
    finally:
        conn.close()
