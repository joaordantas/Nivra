import unittest
from datetime import date

from database.connection import get_connection
from services.cartao_service import criar_cartao_service, criar_compra_service
from services.categoria_service import criar_categoria_service
from services.conta_service import criar_conta_service
from services.insight_service import (
    obter_contexto_financeiro_lumi_service,
    obter_insights_financeiros_service,
)
from services.lumi_tool_service import executar_lumi_tool
from services.transacao_service import criar_transacao_service
from services.transferencia_service import criar_transferencia_service
from tests.db_support import remove_test_database, reset_test_database


class InsightTrendTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        conn = get_connection()
        conn.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES (1, 'Ana', 'ana-p53@example.com', 'hash')"
        )
        conn.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES (2, 'Beto', 'beto-p53@example.com', 'hash')"
        )
        conn.commit()
        conn.close()
        self.account = criar_conta_service("Conta", "digital", 3000, 1)
        self.reserve = criar_conta_service("Reserva", "digital", 1000, 1)
        self.category = criar_categoria_service("Gastos", 1)

    def tearDown(self):
        remove_test_database()

    def test_largest_expenses_include_cards_and_ignore_transfers_and_other_users(self):
        criar_transacao_service(500, "saida", self.category["id"], "Aluguel", "2024-09-02", 1, self.account["id"])
        criar_transacao_service(200, "saida", self.category["id"], "Mercado", "2024-09-03", 1, self.account["id"])
        criar_transferencia_service(self.account["id"], self.reserve["id"], 1000, "Reserva", "2024-09-04", 1)
        card = criar_cartao_service(1, "Cartão", 2000, 13, 20)
        criar_compra_service(card["id"], 1, 300, "Curso", self.category["id"], "2024-09-05")

        other_account = criar_conta_service("Privada", "digital", 0, 2)
        criar_transacao_service(9999, "saida", None, "Despesa privada", "2024-09-05", 2, other_account["id"])

        result = obter_insights_financeiros_service(
            1, "2024-09-01", "2024-09-30", hoje=date(2024, 9, 15)
        )

        self.assertEqual(
            [item["description"] for item in result["largest_expenses"]],
            ["Aluguel", "Curso", "Mercado"],
        )
        self.assertEqual(result["largest_expenses"][0]["percentage"], 50.0)
        self.assertEqual(result["largest_expenses"][1]["source"], "card")
        self.assertNotIn("Reserva", {item["description"] for item in result["largest_expenses"]})
        self.assertNotIn("Despesa privada", {item["description"] for item in result["largest_expenses"]})

    def test_monthly_trend_uses_six_equivalent_periods_across_year_boundary(self):
        values = [100, 110, 120, 130, 150, 180]
        months = ["2023-10", "2023-11", "2023-12", "2024-01", "2024-02", "2024-03"]
        for month, value in zip(months, values, strict=True):
            criar_transacao_service(
                value,
                "saida",
                self.category["id"],
                f"Despesa {month}",
                f"{month}-10",
                1,
                self.account["id"],
            )
            criar_transacao_service(
                999,
                "saida",
                self.category["id"],
                f"Depois do corte {month}",
                f"{month}-20",
                1,
                self.account["id"],
            )

        trend = obter_insights_financeiros_service(
            1, "2024-03-01", "2024-03-31", hoje=date(2024, 3, 15)
        )["monthly_trend"]

        self.assertEqual(trend["comparison_basis"], "same_day")
        self.assertEqual([point["month"] for point in trend["points"]], months)
        self.assertEqual(trend["points"][4]["end"], "2024-02-15")
        self.assertEqual([point["expenses"] for point in trend["points"]], [float(value) for value in values])
        self.assertEqual(trend["expense_direction"], "up")
        self.assertEqual(trend["expense_change_percent"], 80.0)
        self.assertTrue(trend["sustained_expense_growth"])

    def test_full_month_trend_and_empty_history_are_safe(self):
        result = obter_insights_financeiros_service(
            1, "2024-02-01", "2024-02-29", hoje=date(2024, 2, 29)
        )
        trend = result["monthly_trend"]

        self.assertEqual(trend["comparison_basis"], "full_month")
        self.assertEqual(trend["points"][-1]["end"], "2024-02-29")
        self.assertEqual(trend["expense_direction"], "insufficient_data")
        self.assertEqual(trend["savings_direction"], "stable")
        self.assertFalse(trend["sustained_expense_growth"])

    def test_lumi_context_is_consolidated_read_only_and_user_scoped(self):
        criar_transacao_service(800, "entrada", self.category["id"], "Receita", "2024-09-02", 1, self.account["id"])
        criar_transacao_service(250, "saida", self.category["id"], "Mercado", "2024-09-03", 1, self.account["id"])
        other_account = criar_conta_service("Beto", "digital", 0, 2)
        criar_transacao_service(9000, "saida", None, "Privada", "2024-09-03", 2, other_account["id"])

        context = obter_contexto_financeiro_lumi_service(
            1, "2024-09-01", "2024-09-30", hoje=date(2024, 9, 15)
        )

        self.assertEqual(context["financial_position"]["expenses"], 250.0)
        self.assertEqual(context["largest_expenses"][0]["description"], "Mercado")
        self.assertEqual(context["capabilities"], {
            "budgets_available": False,
            "goals_available": False,
            "recurrences_available": False,
        })
        tool_context = executar_lumi_tool(
            "get_financial_context",
            {"usuario_id": 2, "data_inicio": "2024-09-01", "data_fim": "2024-09-30"},
            1,
        )
        self.assertEqual(tool_context["financial_position"]["expenses"], 250.0)
        self.assertNotIn("Privada", {item["description"] for item in tool_context["largest_expenses"]})


if __name__ == "__main__":
    unittest.main()
