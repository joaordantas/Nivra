import unittest
from unittest.mock import patch

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from backend.main import app
from database.connection import dispose_engine, get_connection, get_engine
from database.migrations import get_alembic_config, upgrade_database
from services.open_finance_provider import (
    OpenFinanceItem,
    OpenFinanceItemNotFoundError,
    OpenFinanceProviderError,
)
from tests.auth_support import csrf_headers, issue_csrf, register_client
from tests.db_support import remove_test_database, reset_test_database


ITEM_A = "34318da6-77e0-4ed8-a289-c1f826f2b7da"
ITEM_B = "63431173-b9f1-4c20-b155-62995ce2fb30"
ITEM_MISSING = "7af3b221-3cb3-4dcb-a917-092314559166"
ITEM_UNAVAILABLE = "91ff8f1b-b156-4372-a1ec-f99d558257b1"
ITEM_PENDING = "e6f630fc-d065-4723-851f-ef2601c35b64"


class FakeItemProvider:
    def __init__(self, items: dict[str, OpenFinanceItem]) -> None:
        self.items = items
        self.requested_item_ids: list[str] = []

    def create_connect_token(self, client_user_id: str) -> str:
        return "unused"

    def get_item(self, item_id: str) -> OpenFinanceItem:
        self.requested_item_ids.append(item_id)
        if item_id == ITEM_UNAVAILABLE:
            raise OpenFinanceProviderError("A Pluggy esta temporariamente indisponivel.")
        try:
            return self.items[item_id]
        except KeyError as exc:
            raise OpenFinanceItemNotFoundError("Item nao encontrado.") from exc


def item(item_id: str, user_id: int, *, execution_status: str = "SUCCESS") -> OpenFinanceItem:
    return OpenFinanceItem(
        id=item_id,
        client_user_id=f"nivra-user-{user_id}",
        connector_id=2,
        institution_name="Sandbox PF",
        status="UPDATED",
        execution_status=execution_status,
    )


class OpenFinancePersistenceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_test_database()
        self.a = TestClient(app)
        self.b = TestClient(app)
        self.user_a = register_client(self.a, "Open A", "open-a@example.com")
        self.user_b = register_client(self.b, "Open B", "open-b@example.com")
        self.provider = FakeItemProvider(
            {
                ITEM_A: item(ITEM_A, self.user_a["id"]),
                ITEM_B: item(ITEM_B, self.user_b["id"]),
                ITEM_PENDING: item(
                    ITEM_PENDING,
                    self.user_a["id"],
                    execution_status="WAITING_USER_INPUT",
                ),
            }
        )
        self.provider_patch = patch(
            "services.open_finance_service.get_open_finance_provider",
            return_value=self.provider,
        )
        self.provider_patch.start()

    def tearDown(self) -> None:
        self.provider_patch.stop()
        self.a.close()
        self.b.close()
        remove_test_database()

    def complete(self, client: TestClient, item_id: str, headers: dict[str, str] | None = None):
        return client.post(
            "/api/open-finance/connections/complete",
            headers=headers if headers is not None else csrf_headers(client),
            json={"item_id": item_id},
        )

    def test_valid_connection_is_idempotent_and_survives_login_refresh(self) -> None:
        first = self.complete(self.a, ITEM_A)
        repeated = self.complete(self.a, ITEM_A)

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(first.json()["id"], repeated.json()["id"])
        self.assertEqual(first.json()["instituicao_nome"], "Sandbox PF")
        self.assertNotIn("external_item_id", first.json())

        conn = get_connection()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM conexoes_bancarias WHERE external_item_id = ?",
                (ITEM_A,),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 1)

        refresh = self.a.get("/api/open-finance/connections")
        self.assertEqual(refresh.status_code, 200, refresh.text)
        self.assertEqual(len(refresh.json()), 1)

        logout = self.a.post("/api/auth/logout", headers=csrf_headers(self.a))
        self.assertEqual(logout.status_code, 204, logout.text)
        login_csrf = issue_csrf(self.a)
        login = self.a.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": login_csrf},
            json={"email": "open-a@example.com", "senha": "senha-segura-123"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        restored = self.a.get("/api/open-finance/connections")
        self.assertEqual(restored.json(), refresh.json())

    def test_item_claim_by_another_user_is_denied_without_private_data(self) -> None:
        owner_response = self.complete(self.a, ITEM_A)
        attacker_response = self.complete(self.b, ITEM_A)

        self.assertEqual(owner_response.status_code, 200, owner_response.text)
        self.assertEqual(attacker_response.status_code, 403, attacker_response.text)
        self.assertNotIn(ITEM_A, attacker_response.text)
        self.assertNotIn("Sandbox PF", attacker_response.text)
        self.assertEqual(self.b.get("/api/open-finance/connections").json(), [])

    def test_connections_are_listed_only_for_the_authenticated_owner(self) -> None:
        self.assertEqual(self.complete(self.a, ITEM_A).status_code, 200)
        self.assertEqual(self.complete(self.b, ITEM_B).status_code, 200)

        listed_a = self.a.get("/api/open-finance/connections").json()
        listed_b = self.b.get("/api/open-finance/connections").json()

        self.assertEqual(len(listed_a), 1)
        self.assertEqual(len(listed_b), 1)
        self.assertNotEqual(listed_a[0]["id"], listed_b[0]["id"])

    def test_missing_pending_and_unavailable_items_fail_safely(self) -> None:
        missing = self.complete(self.a, ITEM_MISSING)
        pending = self.complete(self.a, ITEM_PENDING)
        unavailable = self.complete(self.a, ITEM_UNAVAILABLE)

        self.assertEqual(missing.status_code, 404, missing.text)
        self.assertEqual(pending.status_code, 409, pending.text)
        self.assertEqual(unavailable.status_code, 502, unavailable.text)
        self.assertEqual(self.a.get("/api/open-finance/connections").json(), [])

    def test_complete_requires_session_and_valid_csrf(self) -> None:
        anonymous = TestClient(app)
        try:
            unauthenticated = self.complete(anonymous, ITEM_A, headers={})
        finally:
            anonymous.close()
        missing_csrf = self.complete(self.a, ITEM_A, headers={})
        invalid_csrf = self.complete(
            self.a,
            ITEM_A,
            headers={"X-CSRF-Token": "csrf-invalido"},
        )

        self.assertEqual(unauthenticated.status_code, 401, unauthenticated.text)
        self.assertEqual(missing_csrf.status_code, 403, missing_csrf.text)
        self.assertEqual(invalid_csrf.status_code, 403, invalid_csrf.text)
        self.assertEqual(self.provider.requested_item_ids, [])


class OpenFinanceMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_test_database()

    def tearDown(self) -> None:
        remove_test_database()

    def test_upgrade_constraints_foreign_keys_indexes_and_downgrade(self) -> None:
        inspector = inspect(get_engine())
        expected_tables = {
            "conexoes_bancarias",
            "contas_bancarias_externas",
            "transacoes_bancarias",
            "eventos_sincronizacao",
            "eventos_webhook_open_finance",
        }
        self.assertTrue(expected_tables.issubset(set(inspector.get_table_names())))

        uniques = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("conexoes_bancarias")
        }
        self.assertIn("uq_conexoes_provider_item", uniques)
        transaction_uniques = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("transacoes_bancarias")
        }
        self.assertIn("uq_transacoes_bancarias_conta_transacao", transaction_uniques)
        self.assertIn("uq_transacoes_bancarias_transacao_nivra", transaction_uniques)
        external_account_uniques = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("contas_bancarias_externas")
        }
        self.assertIn("uq_contas_externas_conta_nivra", external_account_uniques)

        connection_fks = inspector.get_foreign_keys("conexoes_bancarias")
        self.assertTrue(any(fk["referred_table"] == "usuarios" for fk in connection_fks))
        external_account_fks = inspector.get_foreign_keys("contas_bancarias_externas")
        self.assertTrue(any(fk["referred_table"] == "conexoes_bancarias" for fk in external_account_fks))

        indexes = {index["name"] for index in inspector.get_indexes("conexoes_bancarias")}
        self.assertIn("ix_conexoes_usuario_status", indexes)
        webhook_uniques = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints(
                "eventos_webhook_open_finance"
            )
        }
        self.assertIn("uq_eventos_webhook_provider_evento", webhook_uniques)

        dispose_engine()
        command.downgrade(get_alembic_config(), "b92d8f3a6c10")
        downgraded_tables = set(inspect(get_engine()).get_table_names())
        self.assertTrue(expected_tables.isdisjoint(downgraded_tables))

        dispose_engine()
        upgrade_database()
        self.assertTrue(expected_tables.issubset(set(inspect(get_engine()).get_table_names())))


if __name__ == "__main__":
    unittest.main()
