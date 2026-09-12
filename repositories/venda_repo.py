from database.connection import get_connection

def adicionar_venda(cliente: str, tipo: str, valor_total: float,
                    comentario: str | None, data: str, usuario_id: int) -> int:
    conn = get_connection()
    cursor = conn.execute("""
        INSERT INTO vendas (cliente, tipo, valor_total, comentario, data, usuario_id)
        VALUES (?, ?, ?, ?, ?, ?) RETURNING id
    """, (cliente, tipo, valor_total, comentario, data, usuario_id))
    venda_id = int(cursor.fetchone()[0])
    conn.commit()
    conn.close()
    return venda_id

def listar_vendas(usuario_id: int) -> list:
    conn = get_connection()
    cursor = conn.execute("""
        SELECT id, cliente, tipo, valor_total, comentario, data
        FROM vendas
        WHERE usuario_id = ?
        ORDER BY data DESC
    """, (usuario_id,))
    vendas = cursor.fetchall()
    conn.close()
    return vendas

def listar_clientes(usuario_id: int) -> list[str]:
    """Retorna lista de nomes únicos de clientes do usuário."""
    conn = get_connection()
    cursor = conn.execute("""
        SELECT DISTINCT cliente FROM vendas
        WHERE usuario_id = ?
        ORDER BY cliente
    """, (usuario_id,))
    clientes = [row[0] for row in cursor.fetchall()]
    conn.close()
    return clientes

def buscar_venda_por_id(venda_id: int, usuario_id: int):
    conn = get_connection()
    cursor = conn.execute("""
        SELECT id, cliente, tipo, valor_total, comentario, data
        FROM vendas
        WHERE id = ? AND usuario_id = ?
    """, (venda_id, usuario_id))
    venda = cursor.fetchone()
    conn.close()
    return venda
