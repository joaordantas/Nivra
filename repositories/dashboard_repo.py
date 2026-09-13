from database.connection import get_connection


def total_a_receber(usuario_id: int) -> float:
    conn = get_connection()
    try:
        resultado = conn.execute("""
            SELECT SUM(valor)
            FROM parcelas
            WHERE usuario_id = ? AND status = 'pendente'
        """, (usuario_id,)).fetchone()
        return float(resultado[0] if resultado and resultado[0] is not None else 0)
    finally:
        conn.close()


def a_receber_por_cliente(usuario_id: int) -> list:
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT vendas.cliente, SUM(parcelas.valor) AS pendente
            FROM parcelas
            JOIN vendas ON parcelas.venda_id = vendas.id
            WHERE parcelas.usuario_id = ? AND parcelas.status = 'pendente'
            GROUP BY vendas.cliente
            ORDER BY pendente DESC
        """, (usuario_id,)).fetchall()
    finally:
        conn.close()
