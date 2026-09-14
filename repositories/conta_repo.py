from datetime import date, timedelta

from database.connection import get_connection


SALDO_ATUAL_SQL = """
    c.saldo_inicial
    + COALESCE((
        SELECT SUM(CASE WHEN t.tipo = 'entrada' THEN t.valor ELSE -t.valor END)
        FROM transacoes t
        WHERE t.conta_id = c.id AND t.usuario_id = c.usuario_id
          AND t.data <= CURRENT_DATE
    ), 0)
    + COALESCE((
        SELECT SUM(tr.valor)
        FROM transferencias tr
        WHERE tr.conta_destino_id = c.id AND tr.usuario_id = c.usuario_id
    ), 0)
    - COALESCE((
        SELECT SUM(tr.valor)
        FROM transferencias tr
        WHERE tr.conta_origem_id = c.id AND tr.usuario_id = c.usuario_id
    ), 0)
    - COALESCE((
        SELECT SUM(pf.valor)
        FROM pagamentos_fatura pf
        WHERE pf.conta_id = c.id AND pf.usuario_id = c.usuario_id
    ), 0)
"""


SALDO_EXIBIDO_SQL = f"""
    CASE
        WHEN ce.id IS NOT NULL AND ce.saldo IS NOT NULL THEN ce.saldo
        ELSE {SALDO_ATUAL_SQL}
    END
"""


def criar_conta(nome: str, tipo: str, saldo_inicial: float, usuario_id: int) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO contas (nome, tipo, saldo_inicial, usuario_id)
            VALUES (?, ?, ?, ?) RETURNING id
            """,
            (nome, tipo, saldo_inicial, usuario_id),
        )
        conta_id = int(cursor.fetchone()[0])
        conn.commit()
        return conta_id
    finally:
        conn.close()


def listar_contas_com_saldo(usuario_id: int, incluir_inativas: bool = False) -> list[tuple]:
    conn = get_connection()
    try:
        filtro_ativo = "" if incluir_inativas else "AND c.ativo = TRUE"
        return conn.execute(
            f"""
            SELECT c.id, c.nome, c.tipo, c.saldo_inicial, c.ativo, c.principal,
                   {SALDO_EXIBIDO_SQL} AS saldo_atual,
                   ce.id AS conta_externa_id, cb.instituicao_nome,
                   cb.ultima_sincronizacao_em
            FROM contas c
            LEFT JOIN contas_bancarias_externas ce ON ce.conta_nivra_id = c.id
            LEFT JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            WHERE c.usuario_id = ? {filtro_ativo}
            ORDER BY c.ativo DESC, c.principal DESC, LOWER(c.nome)
            """,
            (usuario_id,),
        ).fetchall()
    finally:
        conn.close()


def buscar_conta_por_id(
    conta_id: int, usuario_id: int, somente_ativa: bool = True
) -> tuple | None:
    conn = get_connection()
    try:
        filtro_ativo = "AND c.ativo = TRUE" if somente_ativa else ""
        return conn.execute(
            f"""
            SELECT c.id, c.nome, c.tipo, c.saldo_inicial, c.ativo, c.principal,
                   {SALDO_EXIBIDO_SQL} AS saldo_atual,
                   ce.id AS conta_externa_id, cb.instituicao_nome,
                   cb.ultima_sincronizacao_em
            FROM contas c
            LEFT JOIN contas_bancarias_externas ce ON ce.conta_nivra_id = c.id
            LEFT JOIN conexoes_bancarias cb ON cb.id = ce.conexao_id
            WHERE c.id = ? AND c.usuario_id = ? {filtro_ativo}
            """,
            (conta_id, usuario_id),
        ).fetchone()
    finally:
        conn.close()


def atualizar_conta(
    conta_id: int,
    nome: str,
    tipo: str,
    saldo_inicial: float,
    usuario_id: int,
) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE contas
            SET nome = ?, tipo = ?, saldo_inicial = ?
            WHERE id = ? AND usuario_id = ?
            """,
            (nome, tipo, saldo_inicial, conta_id, usuario_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def alterar_status_conta(conta_id: int, ativo: bool, usuario_id: int) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE contas
            SET ativo = ?, principal = CASE WHEN ? = FALSE THEN FALSE ELSE principal END
            WHERE id = ? AND usuario_id = ?
            """,
            (ativo, ativo, conta_id, usuario_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def definir_conta_principal(conta_id: int, usuario_id: int) -> bool:
    conn = get_connection()
    try:
        conn.lock_row("usuarios", "id", usuario_id)
        conta = conn.execute(
            "SELECT id FROM contas WHERE id = ? AND usuario_id = ? AND ativo = TRUE",
            (conta_id, usuario_id),
        ).fetchone()
        if conta is None:
            conn.rollback()
            return False
        conn.execute(
            "UPDATE contas SET principal = FALSE WHERE usuario_id = ? AND principal = TRUE",
            (usuario_id,),
        )
        conn.execute(
            "UPDATE contas SET principal = TRUE WHERE id = ? AND usuario_id = ?",
            (conta_id, usuario_id),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obter_uso_contas(usuario_id: int) -> dict[int, int]:
    conn = get_connection()
    try:
        inicio_periodo = date.today() - timedelta(days=90)
        linhas = conn.execute(
            """
            WITH usos AS (
                SELECT conta_id AS conta_id, COUNT(*) AS quantidade
                FROM transacoes
                WHERE usuario_id = ? AND conta_id IS NOT NULL
                  AND data >= ?
                GROUP BY conta_id
                UNION ALL
                SELECT conta_origem_id, COUNT(*)
                FROM transferencias
                WHERE usuario_id = ? AND data >= ?
                GROUP BY conta_origem_id
                UNION ALL
                SELECT conta_destino_id, COUNT(*)
                FROM transferencias
                WHERE usuario_id = ? AND data >= ?
                GROUP BY conta_destino_id
                UNION ALL
                SELECT conta_id, COUNT(*)
                FROM pagamentos_fatura
                WHERE usuario_id = ? AND data >= ?
                GROUP BY conta_id
            )
            SELECT conta_id, SUM(quantidade)
            FROM usos
            GROUP BY conta_id
            """,
            (
                usuario_id, inicio_periodo,
                usuario_id, inicio_periodo,
                usuario_id, inicio_periodo,
                usuario_id, inicio_periodo,
            ),
        ).fetchall()
        return {int(conta_id): int(quantidade) for conta_id, quantidade in linhas}
    finally:
        conn.close()
