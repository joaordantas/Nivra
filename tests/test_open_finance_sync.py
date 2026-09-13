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

    def external_accounts(self) -> list[dict]:
        response = self.a.get(
            f"/api/open-finance/connections/{self.connection_id}/accounts"
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

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

    def test_existing_account_can_be_linked_and_uses_provider_balance(self) -> None:
        account = self.a.post(
            "/api/accounts",
            headers=csrf_headers(self.a),
            json={"nome": "Minha conta", "tipo": "digital", "saldo_inicial": 100},
        )
        self.assertEqual(account.status_code, 201, account.text)
        self.assertEqual(self.sync().status_code, 200)
        external = self.external_accounts()[0]

        linked = self.a.patch(
            f"/api/open-finance/external-accounts/{external['id']}/link",
            headers=csrf_headers(self.a),
            json={"conta_nivra_id": account.json()["id"]},
        )

        self.assertEqual(linked.status_code, 200, linked.text)
        refreshed_external = self.external_accounts()[0]
        self.assertEqual(refreshed_external["conta_nivra_id"], account.json()["id"])
        self.assertEqual(refreshed_external["conta_nivra_nome"], "Minha conta")
        listed = self.a.get("/api/accounts").json()[0]
        self.assertEqual(listed["saldo_inicial"], 100)
        self.assertEqual(listed["saldo_atual"], 1250.5)
        self.assertEqual(listed["origem"], "open_finance")
        self.assertEqual(listed["conta_externa_id"], external["id"])

        self.provider.accounts[0] = replace(
            self.provider.accounts[0], balance=Decimal("1300.75")
        )
        self.assertEqual(self.sync().status_code, 200)
        updated = self.a.get("/api/accounts").json()[0]
        self.assertEqual(updated["saldo_atual"], 1300.75)
        self.assertEqual(updated["conta_externa_id"], external["id"])

    def test_nivra_account_can_be_created_atomically_from_external_account(self) -> None:
        self.assertEqual(self.sync().status_code, 200)
        external = self.external_accounts()[0]

        created = self.a.post(
            f"/api/open-finance/external-accounts/{external['id']}/nivra-account",
            headers=csrf_headers(self.a),
        )

        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["conta_nivra_nome"], "Sandbox PF - Conta Sandbox")
        listed = self.a.get("/api/accounts").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["tipo"], "corrente")
        self.assertEqual(listed[0]["saldo_inicial"], 0)
        self.assertEqual(listed[0]["saldo_atual"], 1250.5)
        self.assertEqual(listed[0]["origem"], "open_finance")
        self.assertEqual(self.external_accounts()[0]["conta_nivra_id"], listed[0]["id"])

    def test_link_can_be_changed_without_leaving_two_accounts_linked(self) -> None:
        first = self.a.post(
            "/api/accounts",
            headers=csrf_headers(self.a),
            json={"nome": "Primeira", "tipo": "digital", "saldo_inicial": 10},
        ).json()
        second = self.a.post(
            "/api/accounts",
            headers=csrf_headers(self.a),
            json={"nome": "Segunda", "tipo": "digital", "saldo_inicial": 20},
        ).json()
        self.assertEqual(self.sync().status_code, 200)
        external_id = self.external_accounts()[0]["id"]
        for account_id in (first["id"], second["id"]):
            response = self.a.patch(
                f"/api/open-finance/external-accounts/{external_id}/link",
                headers=csrf_headers(self.a),
                json={"conta_nivra_id": account_id},
            )
            self.assertEqual(response.status_code, 200, response.text)

        accounts = {account["id"]: account for account in self.a.get("/api/accounts").json()}
        self.assertEqual(accounts[first["id"]]["origem"], "manual")
        self.assertEqual(accounts[first["id"]]["saldo_atual"], 10)
        self.assertEqual(accounts[second["id"]]["origem"], "open_finance")
        self.assertEqual(accounts[second["id"]]["saldo_atual"], 1250.5)

    def test_link_rejects_other_user_account_duplicate_target_and_credit_card(self) -> None:
        second_external = replace(
            self.provider.accounts[0], id="external-account-2", name="Outra conta"
        )
        credit = replace(
            self.provider.accounts[0],
            id="external-credit-1",
            name="Cartao Sandbox",
            type="CREDIT",
            subtype="CREDIT_CARD",
            balance=Decimal("-500.00"),
        )
        self.provider.accounts.extend([second_external, credit])
        self.provider.transactions[second_external.id] = []
        self.provider.transactions[credit.id] = []
        self.assertEqual(self.sync().status_code, 200)
        external_by_name = {item["nome"]: item for item in self.external_accounts()}
        target = self.a.post(
            "/api/accounts",
            headers=csrf_headers(self.a),
            json={"nome": "Alvo", "tipo": "digital", "saldo_inicial": 0},
        ).json()
        other_user_account = self.b.post(
            "/api/accounts",
            headers=csrf_headers(self.b),
            json={"nome": "Privada B", "tipo": "digital", "saldo_inicial": 0},
        ).json()

        first_link = self.a.patch(
            f"/api/open-finance/external-accounts/{external_by_name['Conta Sandbox']['id']}/link",
            headers=csrf_headers(self.a),
            json={"conta_nivra_id": target["id"]},
        )
        duplicate = self.a.patch(
            f"/api/open-finance/external-accounts/{external_by_name['Outra conta']['id']}/link",
            headers=csrf_headers(self.a),
            json={"conta_nivra_id": target["id"]},
        )
        foreign_target = self.a.patch(
            f"/api/open-finance/external-accounts/{external_by_name['Outra conta']['id']}/link",
            headers=csrf_headers(self.a),
            json={"conta_nivra_id": other_user_account["id"]},
        )
        foreign_external = self.b.patch(
            f"/api/open-finance/external-accounts/{external_by_name['Outra conta']['id']}/link",
            headers=csrf_headers(self.b),
            json={"conta_nivra_id": other_user_account["id"]},
        )
        credit_link = self.a.patch(
            f"/api/open-finance/external-accounts/{external_by_name['Cartao Sandbox']['id']}/link",
            headers=csrf_headers(self.a),
            json={"conta_nivra_id": target["id"]},
        )
        missing_csrf = self.a.patch(
            f"/api/open-finance/external-accounts/{external_by_name['Outra conta']['id']}/link",
            json={"conta_nivra_id": target["id"]},
        )

        self.assertEqual(first_link.status_code, 200, first_link.text)
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        self.assertEqual(foreign_target.status_code, 404, foreign_target.text)
        self.assertEqual(foreign_external.status_code, 404, foreign_external.text)
        self.assertEqual(credit_link.status_code, 422, credit_link.text)
        self.assertEqual(missing_csrf.status_code, 403, missing_csrf.text)


if __name__ == "__main__":
    unittest.main()
