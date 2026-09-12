from database.connection import get_connection

def adicionar_parcelas(venda_id: int, quantidade: int, valor: float,
                       status: str, data: str, usuario_id: int):
    conn = get_connection()
    for _ in range(quantidade):
        conn.execute("""
            INSERT INTO parcelas (venda_id, valor, status, data, usuario_id)
            VALUES (?, ?, ?, ?, ?)
        """, (venda_id, valor, status, data, usuario_id))
    conn.commit()
    conn.close()

def listar_parcelas_por_cliente(cliente: str, usuario_id: int) -> list:
    conn = get_connection()
    cursor = conn.execute("""
        SELECT parcelas.id, parcelas.venda_id, parcelas.valor, parcelas.status, parcelas.data
        FROM parcelas
        JOIN vendas ON parcelas.venda_id = vendas.id
        WHERE vendas.cliente = ? AND vendas.usuario_id = ?
        ORDER BY parcelas.data
    """, (cliente, usuario_id))
    parcelas = cursor.fetchall()
    conn.close()
    return parcelas

def marcar_parcela_paga(parcela_id: int, usuario_id: int) -> bool:
    """Retorna True se a parcela foi marcada com sucesso, False se não encontrou."""
    conn = get_connection()
    cursor = conn.execute("""
        UPDATE parcelas SET status = 'pago'
        WHERE id = ? AND usuario_id = ? AND status = 'pendente'
    """, (parcela_id, usuario_id))
    sucesso = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return sucesso

def buscar_valor_parcela(parcela_id: int, usuario_id: int) -> float:
    conn = get_connection()
    cursor = conn.execute("""
        SELECT valor FROM parcelas WHERE id = ? AND usuario_id = ?
    """, (parcela_id, usuario_id))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else 0.0

def calcular_total_pago(cliente: str, usuario_id: int) -> float:
    conn = get_connection()
    cursor = conn.execute("""
        SELECT SUM(parcelas.valor)
        FROM parcelas
        JOIN vendas ON parcelas.venda_id = vendas.id
        WHERE vendas.cliente = ? AND parcelas.status = 'pago' AND vendas.usuario_id = ?
    """, (cliente, usuario_id))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] or 0.0

def buscar_valor_total_vendas(cliente: str, usuario_id: int) -> float:
    conn = get_connection()
    cursor = conn.execute("""
        SELECT SUM(valor_total) FROM vendas
        WHERE cliente = ? AND usuario_id = ?
    """, (cliente, usuario_id))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] or 0.0

def somar_valor_parcelas_da_venda(venda_id: int, usuario_id: int) -> float:
    conn = get_connection()
    cursor = conn.execute("""
        SELECT SUM(valor) FROM parcelas
        WHERE venda_id = ? AND usuario_id = ?
    """, (venda_id, usuario_id))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] or 0.0
