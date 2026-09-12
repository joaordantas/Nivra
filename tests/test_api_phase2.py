import unittest

from fastapi.testclient import TestClient

from backend.main import app
from tests.auth_support import csrf_headers, issue_csrf, register_client
from tests.db_support import remove_test_database, reset_test_database


class Phase2ApiTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        self.client_a = TestClient(app)
        self.client_b = TestClient(app)

    def tearDown(self):
        self.client_a.close()
        self.client_b.close()
        remove_test_database()

    def test_fluxo_financeiro_e_isolamento_entre_sessoes(self):
        user_a = register_client(self.client_a, "Usuario A", "a@example.com")
        user_b = register_client(self.client_b, "Usuario B", "b@example.com")
        headers_a = csrf_headers(self.client_a)
        headers_b = csrf_headers(self.client_b)

        login_client = TestClient(app)
        login_csrf = issue_csrf(login_client)
        login = login_client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": login_csrf},
            json={"email": "A@example.com", "senha": "senha-segura-123"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()["id"], user_a["id"])
        login_client.close()

        category_a = self.client_a.post(
            "/api/categories", headers=headers_a, json={"nome": "Alimentacao"}
        ).json()
        self.client_b.post(
            "/api/categories", headers=headers_b, json={"nome": "Privada B"}
        )
        account_a_1 = self.client_a.post(
            "/api/accounts",
            headers=headers_a,
            json={"nome": "Conta A", "tipo": "digital", "saldo_inicial": 1000},
        ).json()
        account_a_2 = self.client_a.post(
            "/api/accounts",
            headers=headers_a,
            json={"nome": "Reserva A", "tipo": "poupanca", "saldo_inicial": 100},
        ).json()
        account_b = self.client_b.post(
            "/api/accounts",
            headers=headers_b,
            json={"nome": "Conta B", "tipo": "digital", "saldo_inicial": 500},
        ).json()

        expense = self.client_a.post(
            "/api/transactions",
            headers=headers_a,
            json={
                "valor": 80,
                "tipo": "saida",
                "categoria_id": category_a["id"],
                "comentario": "Mercado",
                "data": "2026-09-11",
                "conta_id": account_a_1["id"],
            },
        )
        self.assertEqual(expense.status_code, 201, expense.text)
        expense_id = expense.json()["id"]

        income_b = self.client_b.post(
            "/api/transactions",
            headers=headers_b,
            json={"valor": 200, "tipo": "entrada", "data": "2026-09-11", "conta_id": account_b["id"]},
        )
        self.assertEqual(income_b.status_code, 201, income_b.text)

        forbidden = self.client_b.post(
            "/api/transactions",
            headers=headers_b,
            json={"valor": 10, "tipo": "saida", "data": "2026-09-11", "conta_id": account_a_1["id"]},
        )
        self.assertEqual(forbidden.status_code, 400)

        spoofed = self.client_b.post(
            "/api/accounts",
            headers=headers_b,
            json={"nome": "Forjada", "tipo": "digital", "saldo_inicial": 0, "usuario_id": user_a["id"]},
        )
        self.assertEqual(spoofed.status_code, 422)

        transfer = self.client_a.post(
            "/api/transfers",
            headers=headers_a,
            json={
                "conta_origem_id": account_a_1["id"],
                "conta_destino_id": account_a_2["id"],
                "valor": 100,
                "descricao": "Reserva",
                "data": "2026-09-11",
            },
        )
        self.assertEqual(transfer.status_code, 201, transfer.text)

        transactions_a = self.client_a.get("/api/transactions").json()
        transactions_b = self.client_b.get("/api/transactions").json()
        self.assertEqual([item["id"] for item in transactions_a], [expense_id])
        self.assertEqual(len(transactions_b), 1)
        self.assertEqual(self.client_a.get("/api/categories").json(), [category_a])

        updated = self.client_a.put(
            f"/api/transactions/{expense_id}",
            headers=headers_a,
            json={
                "valor": 90,
                "tipo": "saida",
                "categoria_id": category_a["id"],
                "comentario": "Mercado atualizado",
                "data": "2026-09-11",
                "conta_id": account_a_1["id"],
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["valor"], 90)
        self.assertEqual(
            self.client_a.get("/api/transactions/summary").json(),
            {"entradas": 0.0, "saidas": 90.0, "saldo": -90.0},
        )

        self.assertEqual(
            self.client_a.delete(f"/api/transfers/{transfer.json()['id']}", headers=headers_a).status_code,
            204,
        )
        self.assertEqual(
            self.client_a.delete(f"/api/transactions/{expense_id}", headers=headers_a).status_code,
            204,
        )
        self.assertEqual(self.client_a.get("/api/transactions").json(), [])
        self.assertEqual(self.client_b.get("/api/accounts").json()[0]["id"], account_b["id"])
        self.assertNotEqual(user_a["id"], user_b["id"])


if __name__ == "__main__":
    unittest.main()
