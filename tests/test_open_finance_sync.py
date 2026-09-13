import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from database.connection import get_connection
from services.open_finance_provider import (
    OpenFinanceAccount,
    OpenFinanceItem,
    OpenFinanceProviderError,
    OpenFinanceTransaction,
)
from services.transacao_service import listar_transacoes_formatadas, obter_resumo_financeiro
from tests.auth_support import csrf_headers, register_client
from tests.db_support import remove_test_database, reset_test_database


ITEM_A = "a8597d75-9f4e-4b3e-baa0-fb3c60653a70"


class FakeSyncProvider:
    def __init__(self, user_id: int) -> None:
        self.item = OpenFinanceItem(
            id=ITEM_A,
            client_user_id=f"nivra-user-{user_id}",
            connector_id=2,
            institution_name="Sandbox PF",
            status="UPDATED",
            execution_status="SUCCESS",
        )
        self.accounts = [
            OpenFinanceAccount(
                id="external-account-1",
                name="Conta Sandbox",
                type="BANK",
                subtype="CHECKING_ACCOUNT",
                currency_code="BRL",
                balance=Decimal("1250.50"),
            )
        ]
        self.transactions = {
            "external-account-1": [
                OpenFinanceTransaction(
                    id="external-transaction-1",
                    description="Salario",
                    amount=Decimal("2500.00"),
                    date=date(2026, 9, 1),
                    direction="entrada",
                    status="POSTED",
                    category_id="01000000",
                    category_name="Salary",
                ),
                OpenFinanceTransaction(
                    id="external-transaction-2",
                    description="Mercado",
                    amount=Decimal("149.90"),
                    date=date(2026, 9, 2),
                    direction="saida",
                    status="POSTED",
                    category_id="08000000",
                    category_name="Groceries",
                ),
            ]
        }
        self.fail_accounts = False

    def create_connect_token(self, client_user_id: str) -> str:
        return "unused"

    def get_item(self, item_id: str) -> OpenFinanceItem:
        if item_id != self.item.id:
            raise OpenFinanceProviderError("Item nao encontrado.")
        return self.item

    def list_accounts(self, item_id: str) -> list[OpenFinanceAccount]:
        if self.fail_accounts:
            raise OpenFinanceProviderError("A Pluggy esta temporariamente indisponivel.")
        return list(self.accounts)

    def list_transactions(
        self,
        account_id: str,
        account_type: str,
    ) -> list[OpenFinanceTransaction]:
        return list(self.transactions.get(account_id, []))


class OpenFinanceSyncApiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_test_database()
        self.a = TestClient(app)
        self.b = TestClient(app)
        self.user_a = register_client(self.a, "Sync A", "sync-a@example.com")
        register_client(self.b, "Sync B", "sync-b@example.com")
        self.provider = FakeSyncProvider(self.user_a["id"])
        self.provider_patch = patch(
            "services.open_finance_service.get_open_finance_provider",
            return_value=self.provider,
        )
        self.provider_patch.start()
        completed = self.a.post(
            "/api/open-finance/connections/complete",
            headers=csrf_headers(self.a),
            json={"item_id": ITEM_A},
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        self.connection_id = completed.json()["id"]

    def tearDown(self) -> None:
        self.provider_patch.stop()
        self.a.close()
        self.b.close()
        remove_test_database()

    def sync(self):
        return self.a.post(
            f"/api/open-finance/connections/{self.connection_id}/sync",
            headers=csrf_headers(self.a),
        )

    def test_sync_imports_snapshot_without_changing_manual_finances(self) -> None:
        conn = get_connection()
        try:
            category_id = int(
                conn.execute(
                    "SELECT id FROM categorias WHERE usuario_id = ? AND chave_sistema = 'food'",
                    (self.user_a["id"],),
                ).fetchone()[0]
            )
        finally:
            conn.close()
        account = self.a.post(
            "/api/accounts",
            headers=csrf_headers(self.a),
            json={"nome": "Conta manual", "tipo": "digital", "saldo_inicial": 100},
        )
        self.assertEqual(account.status_code, 201, account.text)
        transaction = self.a.post(
            "/api/transactions",
            headers=csrf_headers(self.a),
            json={
                "valor": 25,
                "tipo": "saida",
                "categoria_id": category_id,
                "comentario": "Compra manual",
                "data": "2026-09-03",
                "conta_id": account.json()["id"],
            },
        )
        self.assertEqual(transaction.status_code, 201, transaction.text)
        before_summary = obter_resumo_financeiro(self.user_a["id"])
        before_transactions = listar_transacoes_formatadas(self.user_a["id"])

        response = self.sync()

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["contas_criadas"], 1)
        self.assertEqual(response.json()["transacoes_criadas"], 2)
        self.assertEqual(response.json()["transacoes_processadas"], 2)
        self.assertEqual(obter_resumo_financeiro(self.user_a["id"]), before_summary)
        self.assertEqual(listar_transacoes_formatadas(self.user_a["id"]), before_transactions)

        accounts = self.a.get(
            f"/api/open-finance/connections/{self.connection_id}/accounts"
        )
        self.assertEqual(accounts.status_code, 200, accounts.text)
        self.assertEqual(accounts.json()[0]["saldo"], 1250.5)
        self.assertEqual(accounts.json()[0]["quantidade_transacoes"], 2)

    def test_resync_updates_and_deletes_without_duplication(self) -> None:
        first = self.sync()
        self.assertEqual(first.status_code, 200, first.text)
        self.provider.accounts[0] = replace(
            self.provider.accounts[0],
            name="Conta Sandbox atualizada",
            balance=Decimal("1300.00"),
        )
        updated = replace(
            self.provider.transactions["external-account-1"][0],
            description="Salario atualizado",
            amount=Decimal("2600.00"),
        )
        created = replace(
            self.provider.transactions["external-account-1"][1],
            id="external-transaction-3",
            description="Farmacia",
            amount=Decimal("80.00"),
            category_name="Health",
        )
        self.provider.transactions["external-account-1"] = [updated, created]

        second = self.sync()
        third = self.sync()

        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["transacoes_criadas"], 1)
        self.assertEqual(second.json()["transacoes_atualizadas"], 1)
        self.assertEqual(second.json()["transacoes_removidas"], 1)
        self.assertEqual(third.status_code, 200, third.text)
        self.assertEqual(third.json()["transacoes_criadas"], 0)
        self.assertEqual(third.json()["transacoes_removidas"], 0)

        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT tb.external_transaction_id, tb.descricao, tb.valor
                FROM transacoes_bancarias tb
                JOIN contas_bancarias_externas ce
                  ON ce.id = tb.conta_bancaria_externa_id
                WHERE ce.conexao_id = ?
                ORDER BY tb.external_transaction_id
                """,
                (self.connection_id,),
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], ("external-transaction-1", "Salario atualizado", 2600.0))
        self.assertEqual(rows[1][0], "external-transaction-3")

    def test_complete_empty_snapshot_removes_external_accounts_and_transactions(self) -> None:
        self.assertEqual(self.sync().status_code, 200)
        self.provider.accounts = []
        self.provider.transactions = {}

        response = self.sync()

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["contas_removidas"], 1)
        self.assertEqual(
            self.a.get(
                f"/api/open-finance/connections/{self.connection_id}/accounts"
            ).json(),
            [],
        )

    def test_provider_failure_keeps_previous_snapshot_and_records_error(self) -> None:
        self.assertEqual(self.sync().status_code, 200)
        self.provider.fail_accounts = True

        failed = self.sync()

        self.assertEqual(failed.status_code, 502, failed.text)
        accounts = self.a.get(
            f"/api/open-finance/connections/{self.connection_id}/accounts"
        ).json()
        self.assertEqual(accounts[0]["quantidade_transacoes"], 2)
        connection = self.a.get("/api/open-finance/connections").json()[0]
        self.assertEqual(connection["ultimo_evento_status"], "erro")
        self.assertIn("temporariamente indisponivel", connection["ultimo_erro"])

    def test_other_user_cannot_sync_or_list_external_accounts(self) -> None:
        sync = self.b.post(
            f"/api/open-finance/connections/{self.connection_id}/sync",
            headers=csrf_headers(self.b),
        )
        accounts = self.b.get(
            f"/api/open-finance/connections/{self.connection_id}/accounts"
        )

        self.assertEqual(sync.status_code, 404, sync.text)
        self.assertEqual(accounts.status_code, 404, accounts.text)


if __name__ == "__main__":
    unittest.main()
