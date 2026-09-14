from datetime import date
from decimal import Decimal

from database.connection import get_connection


PLAN_SELECT = """
    SELECT p.id, p.descricao, p.valor_total, p.quantidade_parcelas,
           p.data_inicial, p.criado_em, p.atualizado_em,
           COUNT(t.id) AS parcelas_persistidas,
           COALESCE(SUM(t.valor), 0) AS valor_persistido,
           MIN(t.data) AS primeira_parcela_data,
           MAX(t.data) AS ultima_parcela_data,
           COALESCE(SUM(CASE WHEN t.data <= CURRENT_DATE THEN 1 ELSE 0 END), 0)
               AS parcelas_com_data_atingida,
           MIN(CASE WHEN t.data > CURRENT_DATE THEN t.data END)
               AS proxima_parcela_data
    FROM parcelamentos p
    LEFT JOIN transacoes t
      ON t.parcelamento_id = p.id AND t.usuario_id = p.usuario_id
"""


def criar_parcelamento_atomico(
    usuario_id: int,
    descricao: str,
    valor_total: Decimal,
    quantidade_parcelas: int,
    data_inicial: date,
    tipo: str,
    categoria_id: int | None,
    conta_id: int | None,
    parcelas: list[tuple[int, Decimal, date]],
) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO parcelamentos (
                usuario_id, descricao, valor_total, quantidade_parcelas, data_inicial
            ) VALUES (?, ?, ?, ?, ?) RETURNING id
            """,
            (usuario_id, descricao, valor_total, quantidade_parcelas, data_inicial),
        )
        parcelamento_id = int(cursor.fetchone()[0])
        for numero, valor, data_parcela in parcelas:
            conn.execute(
                """
                INSERT INTO transacoes (
                    valor, tipo, categoria_id, comentario, data, usuario_id,
                    conta_id, parcelamento_id, numero_parcela
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    valor,
                    tipo,
                    categoria_id,
                    descricao,
                    data_parcela,
                    usuario_id,
                    conta_id,
                    parcelamento_id,
                    numero,
                ),
            )
        conn.commit()
        return parcelamento_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def buscar_parcelamento(parcelamento_id: int, usuario_id: int) -> tuple | None:
    conn = get_connection()
    try:
        return conn.execute(
            f"""
            {PLAN_SELECT}
            WHERE p.id = ? AND p.usuario_id = ?
            GROUP BY p.id
            """,
            (parcelamento_id, usuario_id),
        ).fetchone()
    finally:
        conn.close()


def listar_parcelamentos(usuario_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute(
            f"""
            {PLAN_SELECT}
            WHERE p.usuario_id = ?
            GROUP BY p.id
            ORDER BY p.data_inicial DESC, p.id DESC
            """,
            (usuario_id,),
        ).fetchall()
    finally:
        conn.close()


def listar_parcelas(parcelamento_id: int, usuario_id: int) -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT t.id, t.numero_parcela, t.valor, t.data, t.tipo,
                   t.categoria_id, COALESCE(cat.nome, 'Sem categoria'),
                   t.conta_id, COALESCE(c.nome, 'Sem conta'), t.comentario
            FROM transacoes t
            LEFT JOIN categorias cat ON cat.id = t.categoria_id
            LEFT JOIN contas c ON c.id = t.conta_id
            WHERE t.parcelamento_id = ? AND t.usuario_id = ?
            ORDER BY t.numero_parcela
            """,
            (parcelamento_id, usuario_id),
        ).fetchall()
    finally:
        conn.close()


def atualizar_parcelamento_atomico(
    parcelamento_id: int,
    usuario_id: int,
    descricao: str,
    categoria_id: int | None,
    conta_id: int | None,
) -> bool:
    conn = get_connection()
    try:
        conn.lock_row("parcelamentos", "id", parcelamento_id)
        plano = conn.execute(
            "SELECT id FROM parcelamentos WHERE id = ? AND usuario_id = ?",
            (parcelamento_id, usuario_id),
        ).fetchone()
        if plano is None:
            conn.rollback()
            return False
        conn.execute(
            """
            UPDATE correspondencias_conciliacao
            SET status = 'reaberta', atualizada_em = CURRENT_TIMESTAMP
            WHERE transacao_nivra_id IN (
                SELECT id FROM transacoes
                WHERE parcelamento_id = ? AND usuario_id = ?
            ) AND status IN ('sugerida', 'confirmada')
            """,
            (parcelamento_id, usuario_id),
        )
        conn.execute(
            """
            UPDATE transacoes_bancarias
            SET status_conciliacao = 'pendente',
                transacao_nivra_id = NULL,
                atualizada_em = CURRENT_TIMESTAMP
            WHERE transacao_nivra_id IN (
                SELECT id FROM transacoes
                WHERE parcelamento_id = ? AND usuario_id = ?
            )
            """,
            (parcelamento_id, usuario_id),
        )
        conn.execute(
            """
            UPDATE parcelamentos
            SET descricao = ?, atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ? AND usuario_id = ?
            """,
            (descricao, parcelamento_id, usuario_id),
        )
        cursor = conn.execute(
            """
            UPDATE transacoes
            SET comentario = ?, categoria_id = ?, conta_id = ?
            WHERE parcelamento_id = ? AND usuario_id = ?
            """,
            (descricao, categoria_id, conta_id, parcelamento_id, usuario_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def excluir_parcelamento_atomico(parcelamento_id: int, usuario_id: int) -> bool:
    conn = get_connection()
    try:
        conn.lock_row("parcelamentos", "id", parcelamento_id)
        plano = conn.execute(
            "SELECT id FROM parcelamentos WHERE id = ? AND usuario_id = ?",
            (parcelamento_id, usuario_id),
        ).fetchone()
        if plano is None:
            conn.rollback()
            return False
        conn.execute(
            """
            UPDATE transacoes_bancarias
            SET status_conciliacao = 'pendente',
                transacao_nivra_id = NULL,
                atualizada_em = CURRENT_TIMESTAMP
            WHERE transacao_nivra_id IN (
                SELECT id FROM transacoes
                WHERE parcelamento_id = ? AND usuario_id = ?
            )
            """,
            (parcelamento_id, usuario_id),
        )
        conn.execute(
            "DELETE FROM transacoes WHERE parcelamento_id = ? AND usuario_id = ?",
            (parcelamento_id, usuario_id),
        )
        cursor = conn.execute(
            "DELETE FROM parcelamentos WHERE id = ? AND usuario_id = ?",
            (parcelamento_id, usuario_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
