from datetime import date

from database.connection import get_connection
from repositories.parcela_repo import buscar_valor_parcela, marcar_parcela_paga
from repositories.transacao_repo import adicionar_transacao

# categoria_id = None significa "sem categoria" — aceitável para entradas automáticas
# Em breve podemos criar uma categoria padrão "Recebimentos" e usar o ID dela aqui.

def registrar_pagamento_parcela(parcela_id: int, usuario_id: int) -> bool:
    sucesso = marcar_parcela_paga(parcela_id, usuario_id)
    if sucesso:
        valor = buscar_valor_parcela(parcela_id, usuario_id)
        adicionar_transacao(
            valor=valor,
            tipo='entrada',
            categoria_id=None,
            comentario=f'Parcela #{parcela_id} recebida',
            data=str(date.today()),
            usuario_id=usuario_id,
        )
    return sucesso


def registrar_pagamento_parcela_atomic(parcela_id: int, usuario_id: int) -> bool:
    conn = get_connection()
    try:
        update_result = conn.execute("""
            UPDATE parcelas
            SET status = 'pago'
            WHERE id = ? AND usuario_id = ? AND status = 'pendente'
        """, (parcela_id, usuario_id))

        if update_result.rowcount == 0:
            conn.rollback()
            return False

        value_result = conn.execute("""
            SELECT valor
            FROM parcelas
            WHERE id = ? AND usuario_id = ?
        """, (parcela_id, usuario_id))
        resultado = value_result.fetchone()
        valor = resultado[0] if resultado else 0.0

        conn.execute("""
            INSERT INTO transacoes (valor, tipo, categoria_id, comentario, data, usuario_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            valor,
            "entrada",
            None,
            f"Parcela #{parcela_id} recebida",
            str(date.today()),
            usuario_id,
        ))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
