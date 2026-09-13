from database.connection import get_connection


def buscar_conta_externa_para_vinculo(conta_externa_id: int, usuario_id: int) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT ce.id, ce.nome, ce.tipo, ce.subtipo, ce.moeda, ce.saldo,
                   ce.conta_nivra_id, cb.instituicao_nome
            FROM contas_bancarias_externas ce
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            WHERE ce.id = ? AND cb.usuario_id = ? AND cb.desconectada_em IS NULL
            """,
            (conta_externa_id, usuario_id),
        ).fetchone()
    finally:
        conn.close()


def buscar_conta_nivra_disponivel(conta_nivra_id: int, usuario_id: int) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT c.id, c.nome, c.ativo, ce.id AS conta_externa_id
            FROM contas c
            LEFT JOIN contas_bancarias_externas ce ON ce.conta_nivra_id = c.id
            WHERE c.id = ? AND c.usuario_id = ?
            """,
            (conta_nivra_id, usuario_id),
        ).fetchone()
    finally:
        conn.close()


def vincular_conta_externa(
    conta_externa_id: int,
    conta_nivra_id: int,
    usuario_id: int,
) -> bool:
    conn = get_connection()
    try:
        conn.lock_row("contas_bancarias_externas", "id", conta_externa_id)
        current_link = conn.execute(
            """
            SELECT ce.conta_nivra_id
            FROM contas_bancarias_externas ce
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            WHERE ce.id = ? AND cb.usuario_id = ? AND cb.desconectada_em IS NULL
            """,
            (conta_externa_id, usuario_id),
        ).fetchone()
        if current_link is None:
            conn.rollback()
            return False
        if current_link[0] is not None and int(current_link[0]) != conta_nivra_id:
            conn.execute(
                """
                UPDATE transacoes_bancarias
                SET status_conciliacao = 'pendente',
                    transacao_nivra_id = NULL,
                    atualizada_em = CURRENT_TIMESTAMP
                WHERE conta_bancaria_externa_id = ?
                  AND status_conciliacao IN (
                      'possivel_correspondencia', 'conciliada'
                  )
                """,
                (conta_externa_id,),
            )
        result = conn.execute(
            """
            UPDATE contas_bancarias_externas
            SET conta_nivra_id = ?, atualizada_em = CURRENT_TIMESTAMP
            WHERE id = ?
              AND conexao_id IN (
                  SELECT id FROM conexoes_bancarias
                  WHERE usuario_id = ? AND desconectada_em IS NULL
              )
              AND EXISTS (
                  SELECT 1 FROM contas
                  WHERE id = ? AND usuario_id = ? AND ativo = TRUE
              )
            """,
            (
                conta_nivra_id,
                conta_externa_id,
                usuario_id,
                conta_nivra_id,
                usuario_id,
            ),
        )
        if result.rowcount != 1:
            conn.rollback()
            return False
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def criar_conta_nivra_e_vincular(
    conta_externa_id: int,
    usuario_id: int,
    nome: str,
    tipo: str,
) -> int:
    conn = get_connection()
    try:
        conn.lock_row("contas_bancarias_externas", "id", conta_externa_id)
        ownership = conn.execute(
            """
            SELECT ce.id, ce.conta_nivra_id
            FROM contas_bancarias_externas ce
            JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            WHERE ce.id = ? AND cb.usuario_id = ? AND cb.desconectada_em IS NULL
            """,
            (conta_externa_id, usuario_id),
        ).fetchone()
        if ownership is None:
            raise ValueError("Conta externa nao encontrada.")
        if ownership[1] is not None:
            raise ValueError("Esta conta externa ja esta vinculada a Nivra.")

        account = conn.execute(
            """
            INSERT INTO contas (nome, tipo, saldo_inicial, usuario_id)
            VALUES (?, ?, 0, ?) RETURNING id
            """,
            (nome, tipo, usuario_id),
        ).fetchone()
        if account is None:
            raise RuntimeError("Nao foi possivel criar a conta Nivra.")
        conta_nivra_id = int(account[0])
        linked = conn.execute(
            """
            UPDATE contas_bancarias_externas
            SET conta_nivra_id = ?, atualizada_em = CURRENT_TIMESTAMP
            WHERE id = ? AND conta_nivra_id IS NULL
            """,
            (conta_nivra_id, conta_externa_id),
        )
        if linked.rowcount != 1:
            raise RuntimeError("Nao foi possivel vincular a conta criada.")
        conn.commit()
        return conta_nivra_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
