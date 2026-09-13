import unittest

from fastapi.testclient import TestClient

from backend.main import app
from database.connection import get_connection
from tests.auth_support import csrf_headers, register_client
from tests.db_support import remove_test_database, reset_test_database


class CrossAccountAuthorizationTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        self.a = TestClient(app)
        self.b = TestClient(app)
        self.user_a = register_client(self.a, "Usuario A", "bola-a@example.com")
        register_client(self.b, "Usuario B", "bola-b@example.com")
        self.ha = csrf_headers(self.a)
        self.hb = csrf_headers(self.b)

    def tearDown(self):
        self.a.close(); self.b.close(); remove_test_database()

    def test_ids_from_another_account_cannot_be_read_changed_or_deleted(self):
        category = self.a.post("/api/categories", headers=self.ha, json={"nome": "Privada"}).json()
        account_1 = self.a.post("/api/accounts", headers=self.ha, json={"nome": "A1", "tipo": "digital", "saldo_inicial": 1000}).json()
        account_2 = self.a.post("/api/accounts", headers=self.ha, json={"nome": "A2", "tipo": "digital", "saldo_inicial": 200}).json()
        transaction = self.a.post("/api/transactions", headers=self.ha, json={"valor": 50, "tipo": "saida", "categoria_id": category["id"], "conta_id": account_1["id"], "data": "2026-09-11"}).json()
        transfer = self.a.post("/api/transfers", headers=self.ha, json={"conta_origem_id": account_1["id"], "conta_destino_id": account_2["id"], "valor": 25, "data": "2026-09-11"}).json()
        card = self.a.post("/api/cards", headers=self.ha, json={"nome": "Cartão A", "limite_total": 1000, "dia_fechamento": 13, "dia_vencimento": 20}).json()
        purchase = self.a.post("/api/card-purchases", headers=self.ha, json={"cartao_id": card["id"], "valor": 100, "descricao": "Privada", "categoria_id": category["id"], "data": "2026-09-11"}).json()
        conn = get_connection()
        try:
            sale_id = conn.execute(
                "INSERT INTO vendas (cliente, tipo, valor_total, data, usuario_id) VALUES (?, ?, ?, ?, ?) RETURNING id",
                ("Cliente privado", "servico", 100, "2026-09-11", self.user_a["id"]),
            ).fetchone()[0]
            installment_id = conn.execute(
                "INSERT INTO parcelas (venda_id, valor, status, data, usuario_id) VALUES (?, ?, ?, ?, ?) RETURNING id",
                (sale_id, 100, "pendente", "2026-09-11", self.user_a["id"]),
            ).fetchone()[0]
            conn.commit()
        finally:
            conn.close()

        attempts = [
            self.b.put(f"/api/categories/{category['id']}", headers=self.hb, json={"nome": "Invadida"}),
            self.b.delete(f"/api/categories/{category['id']}", headers=self.hb),
            self.b.put(f"/api/accounts/{account_1['id']}", headers=self.hb, json={"nome": "Invadida", "tipo": "digital", "saldo_inicial": 0}),
            self.b.patch(f"/api/accounts/{account_1['id']}/primary", headers=self.hb),
            self.b.put(f"/api/transactions/{transaction['id']}", headers=self.hb, json={"valor": 1, "tipo": "saida", "conta_id": account_1["id"], "data": "2026-09-11"}),
            self.b.delete(f"/api/transactions/{transaction['id']}", headers=self.hb),
            self.b.put(f"/api/transfers/{transfer['id']}", headers=self.hb, json={"conta_origem_id": account_1["id"], "conta_destino_id": account_2["id"], "valor": 1, "data": "2026-09-11"}),
            self.b.delete(f"/api/transfers/{transfer['id']}", headers=self.hb),
            self.b.put(f"/api/cards/{card['id']}", headers=self.hb, json={"nome": "Invadido", "limite_total": 900, "dia_fechamento": 10, "dia_vencimento": 18}),
            self.b.get(f"/api/cards/{card['id']}/invoices"),
            self.b.get(f"/api/invoices/{purchase['fatura_id']}"),
            self.b.put(f"/api/card-purchases/{purchase['id']}", headers=self.hb, json={"cartao_id": card["id"], "valor": 1, "descricao": "Invadida", "categoria_id": category["id"], "data": "2026-09-11"}),
            self.b.delete(f"/api/card-purchases/{purchase['id']}", headers=self.hb),
            self.b.post("/api/installments", headers=self.hb, json={"venda_id": sale_id, "quantidade": 1, "valor": 100, "status": "pendente", "data": "2026-09-11"}),
            self.b.post(f"/api/installments/{installment_id}/pay", headers=self.hb),
        ]

        self.assertTrue(all(response.status_code in {400, 404, 409} for response in attempts), [(r.status_code, r.text) for r in attempts])
        categorias_a = self.a.get("/api/categories").json()
        self.assertTrue(any(categoria["nome"] == "Privada" for categoria in categorias_a))
        self.assertEqual(self.a.get("/api/transactions").json()[0]["valor"], 50)
        self.assertEqual(self.a.get(f"/api/invoices/{purchase['fatura_id']}").json()["valor_total"], 100)
        self.assertEqual(self.b.get("/api/accounts").json(), [])
        self.assertEqual(self.b.get("/api/cards").json(), [])
        self.assertEqual(self.b.get("/api/sales").json(), [])
        self.assertEqual(self.b.get("/api/installments/by-client", params={"cliente": "Cliente privado"}).json()["parcelas"], [])


if __name__ == "__main__":
    unittest.main()
