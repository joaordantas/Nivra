import os
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
from tests.auth_support import csrf_headers, register_client
from tests.db_support import remove_test_database, reset_test_database


ITEM_ID = "51d5b16f-a4a8-41bc-a16e-311a5b8e59c9"
ACCOUNT_ID = "52d12e23-1e05-48ee-bd65-1eae3bd7b8d0"
WEBHOOK_SECRET = "nivra-webhook-test-secret-with-32-chars"


class FakeWebhookProvider:
    def __init__(self, user_id: int) -> None:
        self.item = OpenFinanceItem(
            id=ITEM_ID,
            client_user_id=f"nivra-user-{user_id}",
            connector_id=2,
            institution_name="Pluggy Sandbox",
            status="UPDATED",
            execution_status="SUCCESS",
        )
        self.accounts = [
            OpenFinanceAccount(
                id=ACCOUNT_ID,
                name="Conta Sandbox",
                type="BANK",
                subtype="CHECKING_ACCOUNT",
                currency_code="BRL",
                balance=Decimal("900.00"),
            )
        ]
        self.transactions = [
            OpenFinanceTransaction(
                id="transaction-1",
                description="Mercado",
                amount=Decimal("80.00"),
                date=date(2026, 9, 10),
                direction="saida",
                status="POSTED",
                category_id="08000000",
                category_name="Groceries",
            )
        ]
        self.created_ids: set[str] = set()
        self.fail_transactions = False
        self.transaction_calls = 0

    def create_connect_token(self, client_user_id: str) -> str:
        return "unused"

    def get_item(self, item_id: str) -> OpenFinanceItem:
        if item_id != ITEM_ID:
            raise OpenFinanceProviderError("Item nao encontrado.")
        return self.item

    def list_accounts(self, item_id: str) -> list[OpenFinanceAccount]:
        return list(self.accounts)

    def list_transactions(
        self,
        account_id: str,
        account_type: str,
        *,
        transaction_ids: list[str] | None = None,
        created_at_from: str | None = None,
    ) -> list[OpenFinanceTransaction]:
        self.transaction_calls += 1
        if self.fail_transactions:
            raise OpenFinanceProviderError("Provider temporariamente indisponivel.")
        result = list(self.transactions)
        if transaction_ids:
            wanted = set(transaction_ids)
            result = [transaction for transaction in result if transaction.id in wanted]
        elif created_at_from:
            result = [
                transaction
                for transaction in result
                if transaction.id in self.created_ids
            ]
        return result


class OpenFinanceWebhookApiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_test_database()
        self.client = TestClient(app)
        self.user = register_client(
            self.client,
            "Webhook User",
            "webhook-user@example.com",
        )
        self.provider = FakeWebhookProvider(self.user["id"])
        self.service_provider_patch = patch(
            "services.open_finance_service.get_open_finance_provider",
            return_value=self.provider,
        )
        self.webhook_provider_patch = patch(
            "services.open_finance_webhook_service.get_open_finance_provider",
            return_value=self.provider,
        )
        self.service_provider_patch.start()
        self.webhook_provider_patch.start()
        self.environment_patch = patch.dict(
            os.environ,
            {"PLUGGY_WEBHOOK_SECRET": WEBHOOK_SECRET},
        )
        self.environment_patch.start()
        completed = self.client.post(
            "/api/open-finance/connections/complete",
            headers=csrf_headers(self.client),
            json={"item_id": ITEM_ID},
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        self.connection_id = completed.json()["id"]

    def tearDown(self) -> None:
        self.environment_patch.stop()
        self.webhook_provider_patch.stop()
        self.service_provider_patch.stop()
        self.client.close()
        remove_test_database()

    def send(self, payload: dict, secret: str | None = WEBHOOK_SECRET):
        headers = {"X-Nivra-Webhook-Secret": secret} if secret is not None else {}
        return self.client.post(
            "/api/open-finance/webhooks/pluggy",
            headers=headers,
            json=payload,
        )

    def seed_from_item_event(self, event_id: str = "event-item-updated"):
        response = self.send(
            {"event": "item/updated", "eventId": event_id, "itemId": ITEM_ID}
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def webhook_row(self, event_id: str) -> tuple:
        conn = get_connection()
        try:
            row = conn.execute(
                """
                SELECT status, tentativas, quantidade_processada,
                       codigo_erro, conexao_id
                FROM eventos_webhook_open_finance
                WHERE provider_event_id = ?
                """,
                (event_id,),
            ).fetchone()
            assert row is not None
            return row
        finally:
            conn.close()

    def test_secret_is_required_and_compared_before_persisting(self) -> None:
        payload = {"event": "item/updated", "eventId": "event-auth", "itemId": ITEM_ID}
        missing = self.send(payload, None)
        invalid = self.send(payload, "wrong-secret")

        self.assertEqual(missing.status_code, 401, missing.text)
        self.assertEqual(invalid.status_code, 401, invalid.text)
        conn = get_connection()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM eventos_webhook_open_finance"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 0)

    def test_missing_server_configuration_returns_retryable_error(self) -> None:
        with patch.dict(os.environ, {"PLUGGY_WEBHOOK_SECRET": ""}):
            response = self.send(
                {
                    "event": "item/updated",
                    "eventId": "event-missing-config",
                    "itemId": ITEM_ID,
                }
            )
        self.assertEqual(response.status_code, 503, response.text)

    def test_item_updated_syncs_once_and_duplicate_is_acknowledged(self) -> None:
        first = self.seed_from_item_event()
        calls_after_first = self.provider.transaction_calls
        duplicate = self.seed_from_item_event()

        self.assertEqual(first.json()["status"], "processed")
        self.assertEqual(first.json()["processed_count"], 1)
        self.assertEqual(duplicate.json()["status"], "duplicate")
        self.assertEqual(self.provider.transaction_calls, calls_after_first)
        self.assertEqual(self.webhook_row("event-item-updated")[:3], ("sucesso", 1, 1))

    def test_created_updated_and_deleted_transactions_are_incremental(self) -> None:
        self.seed_from_item_event()
        new_transaction = OpenFinanceTransaction(
            id="transaction-2",
            description="Salario",
            amount=Decimal("1500.00"),
            date=date(2026, 9, 12),
            direction="entrada",
            status="POSTED",
            category_id="01000000",
            category_name="Salary",
        )
        self.provider.transactions.append(new_transaction)
        self.provider.created_ids.add(new_transaction.id)

        created = self.send(
            {
                "event": "transactions/created",
                "eventId": "event-created",
                "itemId": ITEM_ID,
                "accountId": ACCOUNT_ID,
                "transactionsCreatedAtFrom": "2026-09-12T00:00:00.000Z",
            }
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["processed_count"], 1)

        self.provider.transactions[-1] = replace(
            new_transaction,
            description="Salario atualizado",
            amount=Decimal("1600.00"),
        )
        updated = self.send(
            {
                "event": "transactions/updated",
                "eventId": "event-updated",
                "itemId": ITEM_ID,
                "accountId": ACCOUNT_ID,
                "transactionIds": ["transaction-2"],
            }
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["processed_count"], 1)

        deleted = self.send(
            {
                "event": "transactions/deleted",
                "eventId": "event-deleted",
                "itemId": ITEM_ID,
                "accountId": ACCOUNT_ID,
                "transactionIds": ["transaction-2"],
            }
        )
        repeated_delete = self.send(
            {
                "event": "transactions/deleted",
                "eventId": "event-deleted",
                "itemId": ITEM_ID,
                "accountId": ACCOUNT_ID,
                "transactionIds": ["transaction-2"],
            }
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(deleted.json()["processed_count"], 1)
        self.assertEqual(repeated_delete.json()["status"], "duplicate")

        conn = get_connection()
        try:
            row = conn.execute(
                """
                SELECT descricao, valor, removida_em FROM transacoes_bancarias
                WHERE external_transaction_id = 'transaction-2'
                """
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertIsNotNone(row[2])

    def test_provider_failure_is_persisted_and_same_event_can_retry(self) -> None:
        self.seed_from_item_event()
        payload = {
            "event": "transactions/updated",
            "eventId": "event-retry",
            "itemId": ITEM_ID,
            "accountId": ACCOUNT_ID,
            "transactionIds": ["transaction-1"],
        }
        self.provider.fail_transactions = True
        failed = self.send(payload)
        self.assertEqual(failed.status_code, 503, failed.text)
        self.assertEqual(self.webhook_row("event-retry")[:2], ("erro", 1))

        self.provider.fail_transactions = False
        retried = self.send(payload)
        self.assertEqual(retried.status_code, 200, retried.text)
        self.assertEqual(retried.json()["status"], "processed")
        self.assertEqual(self.webhook_row("event-retry")[:2], ("sucesso", 2))

    def test_in_progress_duplicate_waits_and_stale_processing_can_retry(self) -> None:
        self.seed_from_item_event()
        payload = {
            "event": "transactions/updated",
            "eventId": "event-processing-lease",
            "itemId": ITEM_ID,
            "accountId": ACCOUNT_ID,
            "transactionIds": ["transaction-1"],
        }
        self.provider.fail_transactions = True
        failed = self.send(payload)
        self.assertEqual(failed.status_code, 503, failed.text)

        conn = get_connection()
        try:
            conn.execute(
                """
                UPDATE eventos_webhook_open_finance
                SET status = 'processando', ultima_tentativa_em = CURRENT_TIMESTAMP
                WHERE provider_event_id = 'event-processing-lease'
                """
            )
            conn.commit()
        finally:
            conn.close()
        self.provider.fail_transactions = False
        calls_before_duplicate = self.provider.transaction_calls
        concurrent_duplicate = self.send(payload)
        self.assertEqual(concurrent_duplicate.status_code, 503, concurrent_duplicate.text)
        self.assertEqual(self.provider.transaction_calls, calls_before_duplicate)

        conn = get_connection()
        try:
            conn.execute(
                """
                UPDATE eventos_webhook_open_finance
                SET ultima_tentativa_em = '2020-01-01 00:00:00'
                WHERE provider_event_id = 'event-processing-lease'
                """
            )
            conn.commit()
        finally:
            conn.close()
        recovered = self.send(payload)
        self.assertEqual(recovered.status_code, 200, recovered.text)
        self.assertEqual(recovered.json()["status"], "processed")
        self.assertEqual(
            self.webhook_row("event-processing-lease")[:2],
            ("sucesso", 2),
        )

    def test_financial_change_resets_old_reconciliation(self) -> None:
        self.seed_from_item_event()
        external_account = self.client.get(
            f"/api/open-finance/connections/{self.connection_id}/accounts"
        ).json()[0]
        linked = self.client.post(
            f"/api/open-finance/external-accounts/{external_account['id']}/nivra-account",
            headers=csrf_headers(self.client),
        )
        self.assertEqual(linked.status_code, 201, linked.text)
        conn = get_connection()
        try:
            category_id = int(
                conn.execute(
                    "SELECT id FROM categorias WHERE usuario_id = ? AND chave_sistema = 'groceries'",
                    (self.user["id"],),
                ).fetchone()[0]
            )
            bank_id = int(
                conn.execute(
                    "SELECT id FROM transacoes_bancarias WHERE external_transaction_id = 'transaction-1'"
                ).fetchone()[0]
            )
        finally:
            conn.close()
        manual = self.client.post(
            "/api/transactions",
            headers=csrf_headers(self.client),
            json={
                "valor": 80,
                "tipo": "saida",
                "categoria_id": category_id,
                "comentario": "Mercado manual",
                "data": "2026-09-10",
                "conta_id": linked.json()["conta_nivra_id"],
            },
        )
        self.assertEqual(manual.status_code, 201, manual.text)
        confirmed = self.client.post(
            f"/api/transactions/bank/{bank_id}/reconciliation/confirm",
            headers=csrf_headers(self.client),
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)

        self.provider.transactions[0] = replace(
            self.provider.transactions[0],
            amount=Decimal("95.00"),
        )
        updated = self.send(
            {
                "event": "transactions/updated",
                "eventId": "event-financial-change",
                "itemId": ITEM_ID,
                "accountId": ACCOUNT_ID,
                "transactionIds": ["transaction-1"],
            }
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        conn = get_connection()
        try:
            reconciliation = conn.execute(
                """
                SELECT status_conciliacao, transacao_nivra_id
                FROM transacoes_bancarias WHERE id = ?
                """,
                (bank_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(reconciliation, ("pendente", None))

    def test_event_id_payload_conflict_is_rejected(self) -> None:
        self.seed_from_item_event("event-conflict")
        conflict = self.send(
            {"event": "item/error", "eventId": "event-conflict", "itemId": ITEM_ID}
        )
        self.assertEqual(conflict.status_code, 409, conflict.text)

    def test_item_error_and_deleted_update_connection_state(self) -> None:
        error = self.send(
            {
                "event": "item/error",
                "eventId": "event-item-error",
                "itemId": ITEM_ID,
                "error": {"code": "CONNECTION_ERROR", "message": "Temporarily offline"},
            }
        )
        self.assertEqual(error.status_code, 200, error.text)
        connection = self.client.get("/api/open-finance/connections").json()[0]
        self.assertEqual(connection["status"], "error")
        self.assertEqual(connection["ultimo_evento_status"], "erro")

        deleted = self.send(
            {"event": "item/deleted", "eventId": "event-item-deleted", "itemId": ITEM_ID}
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(self.webhook_row("event-item-deleted")[0], "sucesso")

    def test_unknown_item_and_unsupported_event_are_safely_ignored(self) -> None:
        unknown_item = self.send(
            {
                "event": "item/updated",
                "eventId": "event-unknown-item",
                "itemId": "unknown-item",
            }
        )
        unsupported = self.send(
            {"event": "connector/status_updated", "eventId": "event-unsupported"}
        )
        self.assertEqual(unknown_item.status_code, 200, unknown_item.text)
        self.assertEqual(unknown_item.json()["status"], "ignored")
        self.assertEqual(unsupported.status_code, 200, unsupported.text)
        self.assertEqual(unsupported.json()["status"], "ignored")


if __name__ == "__main__":
    unittest.main()
