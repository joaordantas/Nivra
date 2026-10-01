import unittest
from datetime import date

from database.connection import get_connection
from services.categoria_service import criar_categoria_service
from services.conta_service import criar_conta_service
from services.insight_service import obter_contexto_financeiro_lumi_service
from services.transacao_service import criar_transacao_service
from services.transferencia_service import criar_transferencia_service
from tests.db_support import remove_test_database, reset_test_database


PERIOD_START = "2026-09-01"
PERIOD_END = "2026-09-30"
REFERENCE_DATE = date(2026, 9, 30)


class LumiBalanceContextTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_test_database()
        conn = get_connection()
        conn.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES (1, 'Ana', 'ana-balance@example.com', 'hash')"
        )
        conn.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES (2, 'Beto', 'beto-balance@example.com', 'hash')"
        )
        conn.commit()
        conn.close()
        self.category = criar_categoria_service("Teste", 1)

    def tearDown(self) -> None:
        remove_test_database()

    def context(self, user_id: int = 1) -> dict:
        return obter_contexto_financeiro_lumi_service(
            user_id,
            PERIOD_START,
            PERIOD_END,
            hoje=REFERENCE_DATE,
        )

    def test_real_gate_regression_uses_dashboard_balance_source(self) -> None:
        account = criar_conta_service("Nubank", "digital", 7.22, 1)
        criar_transacao_service(
            2.34, "entrada", self.category["id"], "Receita fictícia",
            "2026-09-10", 1, account["id"],
        )
        criar_transacao_service(
            1.11, "saida", self.category["id"], "Despesa fictícia",
            "2026-09-11", 1, account["id"],
        )

        context = self.context()

        self.assertEqual(context["financial_position"]["total_current_balance"], 8.45)
        self.assertEqual(context["period_summary"], {
            "income": 2.34,
            "expenses": 1.11,
            "savings": 1.23,
        })
        self.assertEqual(context["financial_position"]["accounts"], [{
            "name": "Nubank",
            "type": "digital",
            "current_balance": 8.45,
            "balance_source": "manual",
        }])
        self.assertTrue(context["data_status"]["has_movements_in_period"])
        self.assertEqual(context["data_status"]["transaction_count"], 2)

    def test_legitimate_zero_balance_does_not_mean_no_movements(self) -> None:
        account = criar_conta_service("Conta zero", "digital", 0, 1)
        criar_transacao_service(
            10, "entrada", self.category["id"], "Entrada",
            "2026-09-10", 1, account["id"],
        )
        criar_transacao_service(
            10, "saida", self.category["id"], "Saída",
            "2026-09-11", 1, account["id"],
        )

        context = self.context()

        self.assertEqual(context["financial_position"]["total_current_balance"], 0.0)
        self.assertTrue(context["data_status"]["has_accounts"])
        self.assertTrue(context["data_status"]["has_transactions_in_period"])
        self.assertTrue(context["data_status"]["has_movements_in_period"])

    def test_multiple_accounts_and_internal_transfer_preserve_consolidated_balance(self) -> None:
        checking = criar_conta_service("Corrente", "corrente", 100, 1)
        reserve = criar_conta_service("Reserva", "poupanca", 50, 1)
        criar_transferencia_service(
            checking["id"], reserve["id"], 30, "Reserva fictícia", "2026-09-12", 1
        )

        context = self.context()
        balances = {
            account["name"]: account["current_balance"]
            for account in context["financial_position"]["accounts"]
        }

        self.assertEqual(context["financial_position"]["total_current_balance"], 150.0)
        self.assertEqual(balances, {"Corrente": 70.0, "Reserva": 80.0})
        self.assertEqual(context["data_status"]["transfer_count"], 1)
        self.assertTrue(context["data_status"]["has_movements_in_period"])

    def test_open_finance_account_uses_provider_balance(self) -> None:
        account = criar_conta_service("Banco conectado", "corrente", 100, 1)
        conn = get_connection()
        connection_id = conn.execute(
            """
            INSERT INTO conexoes_bancarias (
                usuario_id, provider, external_item_id, client_user_ref,
                instituicao_nome, status, ambiente
            ) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id
            """,
            (1, "fake", "item-balance", "user-balance", "Banco Teste", "ativo", "sandbox"),
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO contas_bancarias_externas (
                conexao_id, external_account_id, conta_nivra_id,
                nome, tipo, subtipo, moeda, saldo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                connection_id, "external-balance", account["id"], "Conta externa",
                "BANK", "CHECKING_ACCOUNT", "BRL", 999.99,
            ),
        )
        conn.commit()
        conn.close()

        context = self.context()

        self.assertEqual(context["financial_position"]["total_current_balance"], 999.99)
        self.assertEqual(
            context["financial_position"]["accounts"][0]["balance_source"],
            "open_finance",
        )

    def test_context_is_user_scoped_and_does_not_expose_internal_ids(self) -> None:
        criar_conta_service("Somente Ana", "digital", 25, 1)
        criar_conta_service("Somente Beto", "digital", 9000, 2)

        context = self.context(1)
        accounts = context["financial_position"]["accounts"]

        self.assertEqual(context["financial_position"]["total_current_balance"], 25.0)
        self.assertEqual([account["name"] for account in accounts], ["Somente Ana"])
        self.assertNotIn("id", accounts[0])

    def test_absence_of_accounts_and_movements_is_explicit(self) -> None:
        context = self.context(2)

        self.assertEqual(context["financial_position"]["total_current_balance"], 0.0)
        self.assertFalse(context["data_status"]["has_accounts"])
        self.assertFalse(context["data_status"]["has_movements_in_period"])


if __name__ == "__main__":
    unittest.main()
