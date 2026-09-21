import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from database.connection import get_connection
from services.cartao_service import (
    alterar_status_cartao_service,
    criar_cartao_service,
    criar_compra_service,
    pagar_fatura_service,
)
from services.categoria_service import criar_categoria_service
from services.conta_service import criar_conta_service
from services.insight_service import _card_commitment, obter_insights_financeiros_service
from services.parcelamento_service import criar_parcelamento_service
from services.transacao_service import criar_transacao_service
from services.transferencia_service import criar_transferencia_service
from tests.auth_support import authenticate_existing_user
from tests.db_support import remove_test_database, reset_test_database


class InsightProjectionTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        conn = get_connection()
        conn.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES (1, 'Ana', 'ana-p52@example.com', 'hash')"
        )
        conn.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES (2, 'Beto', 'beto-p52@example.com', 'hash')"
        )
        conn.commit()
        conn.close()
        self.account_a = criar_conta_service("Conta A", "digital", 2000, 1)
        self.account_b = criar_conta_service("Conta B", "digital", 1000, 1)
        self.category = criar_categoria_service("Planejamento", 1)
        self.client = TestClient(app)
        authenticate_existing_user(self.client, 1)

    def tearDown(self):
        self.client.close()
        remove_test_database()

    def insight(self, start="2024-09-01", end="2024-09-30", today=date(2024, 9, 15)):
        return obter_insights_financeiros_service(1, start, end, hoje=today)

    def test_empty_month_and_income_or_expense_only(self):
        empty = self.insight()
        self.assertEqual(empty["monthly_projection"]["realized"]["savings"], 0)
        self.assertEqual(empty["monthly_projection"]["known_future_entries"], 0)
        self.assertEqual(empty["card_commitment"]["active_cards"], 0)

        criar_transacao_service(500, "entrada", self.category["id"], "Receita", "2024-09-10", 1, self.account_a["id"])
        income = self.insight()
        self.assertEqual(income["monthly_projection"]["realized"], {"income": 500.0, "expenses": 0.0, "savings": 500.0})

        conn = get_connection()
        conn.execute("DELETE FROM transacoes WHERE usuario_id = ?", (1,))
        conn.commit()
        conn.close()
        criar_transacao_service(120, "saida", self.category["id"], "Despesa", "2024-09-10", 1, self.account_a["id"])
        expense = self.insight()
        self.assertEqual(expense["monthly_projection"]["realized"], {"income": 0.0, "expenses": 120.0, "savings": -120.0})

    def test_known_future_projection_includes_installment_and_excludes_transfer_and_next_month(self):
        criar_transacao_service(1000, "entrada", self.category["id"], "Receita", "2024-09-01", 1, self.account_a["id"])
        criar_transacao_service(100, "saida", self.category["id"], "Despesa", "2024-09-02", 1, self.account_a["id"])
        criar_transacao_service(200, "entrada", self.category["id"], "Receita futura", "2024-09-20", 1, self.account_a["id"])
        criar_transacao_service(300, "saida", self.category["id"], "Despesa futura", "2024-09-25", 1, self.account_a["id"])
        criar_transacao_service(999, "saida", self.category["id"], "Fora do mês", "2024-10-01", 1, self.account_a["id"])
        criar_parcelamento_service(
            1, "Curso", "200.00", 2, date(2024, 9, 20), "saida", self.category["id"], self.account_a["id"]
        )
        criar_transferencia_service(
            self.account_a["id"], self.account_b["id"], 400, "Transferência", "2024-09-22", 1
        )
        card = criar_cartao_service(1, "Cartão futuro", 1000, 13, 20)
        criar_compra_service(card["id"], 1, 25, "Compra realizada", self.category["id"], "2024-09-12")
        criar_compra_service(card["id"], 1, 50, "Compra futura", self.category["id"], "2024-09-18")

        projection = self.insight()["monthly_projection"]

        self.assertEqual(projection["realized"], {"income": 1000.0, "expenses": 125.0, "savings": 875.0})
        self.assertEqual(projection["known_future"], {"income": 200.0, "expenses": 450.0, "savings": -250.0})
        self.assertEqual(projection["projected"], {"income": 1200.0, "expenses": 575.0, "savings": 625.0})
        self.assertEqual(projection["known_future_entries"], 4)

    def test_projection_handles_leap_february_and_year_end(self):
        criar_transacao_service(100, "saida", self.category["id"], "29 de fevereiro", "2024-02-29", 1, self.account_a["id"])
        leap = self.insight("2024-02-01", "2024-02-29", date(2024, 2, 28))
        self.assertEqual(leap["monthly_projection"]["known_future"]["expenses"], 100.0)

        criar_transacao_service(250, "entrada", self.category["id"], "Virada", "2024-12-31", 1, self.account_a["id"])
        year_end = self.insight("2024-12-01", "2024-12-31", date(2024, 12, 30))
        self.assertEqual(year_end["monthly_projection"]["known_future"]["income"], 250.0)
        self.assertEqual(year_end["period"]["previous_start"], "2024-11-01")

    def test_known_future_commitments_can_make_projection_negative(self):
        criar_transacao_service(300, "entrada", self.category["id"], "Receita", "2024-09-10", 1, self.account_a["id"])
        criar_transacao_service(450, "saida", self.category["id"], "Compromisso", "2024-09-25", 1, self.account_a["id"])

        result = self.insight()

        self.assertEqual(result["monthly_projection"]["realized"]["savings"], 300.0)
        self.assertEqual(result["monthly_projection"]["projected"]["savings"], -150.0)
        self.assertIn(
            "known_commitments_negative_projection",
            {item["code"] for item in result["attention"]},
        )

    def test_unused_card_has_open_current_invoice_and_full_available_limit(self):
        criar_cartao_service(1, "Sem uso", 750, 13, 20)

        cards = self.insight(today=date(2024, 9, 10))["card_commitment"]

        self.assertEqual(cards["total_committed"], 0.0)
        self.assertEqual(cards["total_available"], 750.0)
        self.assertEqual(cards["cards"][0]["current_invoice_amount"], 0.0)
        self.assertEqual(cards["cards"][0]["invoice_status"], "aberta")

    def test_card_commitment_aggregates_active_cards_and_generates_alerts(self):
        first = criar_cartao_service(1, "Primeiro", 1000, 13, 20)
        second = criar_cartao_service(1, "Segundo", 500, 13, 20)
        inactive = criar_cartao_service(1, "Inativo", 1000, 13, 20)
        criar_compra_service(first["id"], 1, 800, "Compra 1", self.category["id"], "2024-09-10")
        criar_compra_service(second["id"], 1, 500, "Compra 2", self.category["id"], "2024-09-10")
        criar_compra_service(inactive["id"], 1, 900, "Compra inativa", self.category["id"], "2024-09-10")
        alterar_status_cartao_service(inactive["id"], 1, False)

        result = self.insight(today=date(2024, 9, 18))
        cards = result["card_commitment"]

        self.assertEqual(cards["active_cards"], 2)
        self.assertEqual(cards["total_limit"], 1500.0)
        self.assertEqual(cards["total_committed"], 1300.0)
        self.assertEqual(cards["total_available"], 200.0)
        self.assertAlmostEqual(cards["committed_percent"], 86.67)
        self.assertEqual({item["name"] for item in cards["cards"]}, {"Primeiro", "Segundo"})
        codes = {item["code"] for item in result["attention"]}
        self.assertIn("card_limit_critical", codes)
        self.assertIn("card_invoice_due_soon", codes)

    def test_paid_invoice_releases_limit_without_removing_economic_expense(self):
        card = criar_cartao_service(1, "Pago", 1000, 13, 20)
        purchase = criar_compra_service(card["id"], 1, 300, "Compra", self.category["id"], "2024-09-10")
        pagar_fatura_service(purchase["fatura_id"], self.account_a["id"], 1, "2024-09-14")

        result = self.insight(today=date(2024, 9, 15))

        self.assertEqual(result["monthly_projection"]["realized"]["expenses"], 300.0)
        self.assertEqual(result["card_commitment"]["total_committed"], 0.0)
        self.assertEqual(result["card_commitment"]["cards"][0]["next_due_invoice_amount"], 0.0)

    def test_zero_and_negative_card_values_are_safe(self):
        malformed_cards = [{
            "id": 1,
            "nome": "Legado",
            "limite_total": 0,
            "limite_utilizado": -10,
            "fatura_atual": None,
        }]
        with (
            patch("services.insight_service.listar_cartoes_formatados", return_value=malformed_cards),
            patch("services.insight_service.listar_faturas_service", return_value=[]),
        ):
            result = _card_commitment(1, date(2024, 9, 15))

        self.assertEqual(result["total_limit"], 0.0)
        self.assertEqual(result["total_committed"], 0.0)
        self.assertIsNone(result["committed_percent"])
        self.assertIsNone(result["cards"][0]["committed_percent"])

    def test_endpoint_does_not_accept_spoofed_user_and_excludes_other_cards(self):
        own = criar_cartao_service(1, "Meu cartão", 1000, 13, 20)
        other_category = criar_categoria_service("Privada", 2)
        other = criar_cartao_service(2, "Cartão privado", 9000, 13, 20)
        criar_compra_service(own["id"], 1, 100, "Minha compra", self.category["id"], "2024-09-10")
        criar_compra_service(other["id"], 2, 8000, "Compra privada", other_category["id"], "2024-09-10")

        response = self.client.get(
            "/api/insights",
            params={"data_inicio": "2024-09-01", "data_fim": "2024-09-30", "usuario_id": 2},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["card_commitment"]["total_limit"], 1000.0)
        self.assertEqual(response.json()["card_commitment"]["cards"][0]["name"], "Meu cartão")


if __name__ == "__main__":
    unittest.main()
