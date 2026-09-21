import unittest
from datetime import date

from fastapi.testclient import TestClient

from backend.main import app
from database.connection import get_connection
from services.cartao_service import criar_cartao_service, criar_compra_service
from services.categoria_service import criar_categoria_service
from services.conta_service import criar_conta_service
from services.insight_service import obter_insights_financeiros_service
from services.lumi_tool_service import executar_lumi_tool
from services.transacao_service import criar_transacao_service
from tests.auth_support import authenticate_existing_user
from tests.db_support import remove_test_database, reset_test_database


class FinancialInsightTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        conn = get_connection()
        conn.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES (1, 'Ana', 'ana@example.com', 'hash')"
        )
        conn.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES (2, 'Beto', 'beto@example.com', 'hash')"
        )
        conn.commit()
        conn.close()
        self.client = TestClient(app)
        authenticate_existing_user(self.client, 1)

    def tearDown(self):
        self.client.close()
        remove_test_database()

    def test_comparison_categories_card_expense_and_unusual_expense(self):
        account = criar_conta_service("Conta", "digital", 0, 1)
        food = criar_categoria_service("Alimentação", 1)
        income = criar_categoria_service("Renda extra", 1)

        criar_transacao_service(1000, "entrada", income["id"], "Salário", "2024-08-02", 1, account["id"])
        criar_transacao_service(200, "saida", food["id"], "Mercado", "2024-08-03", 1, account["id"])

        criar_transacao_service(1200, "entrada", income["id"], "Salário", "2024-09-02", 1, account["id"])
        criar_transacao_service(50, "saida", food["id"], "Padaria", "2024-09-03", 1, account["id"])
        criar_transacao_service(60, "saida", food["id"], "Almoço", "2024-09-04", 1, account["id"])
        criar_transacao_service(500, "saida", food["id"], "Compra grande", "2024-09-05", 1, account["id"])
        card = criar_cartao_service(1, "Nivra Card", 2000, 13, 20)
        criar_compra_service(card["id"], 1, 100, "Restaurante", food["id"], "2024-09-06")

        result = obter_insights_financeiros_service(
            1, "2024-09-01", "2024-09-30", hoje=date(2024, 9, 20)
        )

        self.assertEqual(result["period"]["end"], "2024-09-20")
        self.assertEqual(result["period"]["previous_start"], "2024-08-01")
        self.assertEqual(result["period"]["previous_end"], "2024-08-20")
        self.assertEqual(result["summary"], {"income": 1200.0, "expenses": 710.0, "savings": 490.0})
        self.assertEqual(result["previous_summary"], {"income": 1000.0, "expenses": 200.0, "savings": 800.0})
        self.assertEqual(result["comparison"]["expense_change_percent"], 255.0)
        self.assertEqual(result["top_expense_categories"][0]["total"], 710.0)
        self.assertEqual(result["unusual_expenses"][0]["description"], "Compra grande")
        self.assertIn("expenses_increased", {item["code"] for item in result["attention"]})
        self.assertIn("unusual_expense", {item["code"] for item in result["attention"]})

    def test_empty_period_and_invalid_period(self):
        result = obter_insights_financeiros_service(
            1, "2024-09-01", "2024-09-30", hoje=date(2024, 9, 20)
        )
        self.assertEqual(result["attention"][0]["code"], "no_activity")

        with self.assertRaisesRegex(ValueError, "data inicial"):
            obter_insights_financeiros_service(
                1, "2024-10-01", "2024-09-30", hoje=date(2024, 9, 20)
            )

    def test_endpoint_is_authenticated_and_isolated(self):
        own_account = criar_conta_service("Minha conta", "digital", 0, 1)
        other_account = criar_conta_service("Conta de Beto", "digital", 0, 2)
        criar_transacao_service(100, "entrada", None, "Minha renda", "2024-09-02", 1, own_account["id"])
        criar_transacao_service(9999, "entrada", None, "Renda de Beto", "2024-09-02", 2, other_account["id"])

        response = self.client.get(
            "/api/insights",
            params={"data_inicio": "2024-09-01", "data_fim": "2024-09-30"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["summary"]["income"], 100.0)

        with TestClient(app) as anonymous:
            denied = anonymous.get(
                "/api/insights",
                params={"data_inicio": "2024-09-01", "data_fim": "2024-09-30"},
            )
        self.assertEqual(denied.status_code, 401)

    def test_lumi_tool_is_allowlisted_and_injects_authenticated_user(self):
        captured = {}

        def fake_handler(user_id, start, end):
            captured.update(user_id=user_id, start=start, end=end)
            return {"ok": True}

        result = executar_lumi_tool(
            "get_financial_insights",
            {"usuario_id": 999, "data_inicio": "2024-09-01", "data_fim": "2024-09-30"},
            1,
            handlers={"get_financial_insights": fake_handler},
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured["user_id"], 1)

        with self.assertRaisesRegex(ValueError, "não permitida"):
            executar_lumi_tool("run_sql", {}, 1, handlers={"run_sql": fake_handler})


if __name__ == "__main__":
    unittest.main()
