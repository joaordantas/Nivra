import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from services.open_finance_provider import (
    OpenFinanceConfigurationError,
    OpenFinanceItem,
    PluggyOpenFinanceProvider,
    get_open_finance_provider,
    reset_open_finance_provider,
)
from services.open_finance_service import criar_connect_token_service
from tests.auth_support import csrf_headers, register_client
from tests.db_support import remove_test_database, reset_test_database


class FakeProvider:
    def __init__(self, token: str = "connect-token-sandbox") -> None:
        self.token = token
        self.client_user_ids: list[str] = []

    def create_connect_token(self, client_user_id: str) -> str:
        self.client_user_ids.append(client_user_id)
        return self.token

    def get_item(self, item_id: str) -> OpenFinanceItem:
        raise AssertionError("get_item nao deveria ser chamado neste teste")


class PluggyProviderTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_open_finance_provider()

    def test_provider_authenticates_on_backend_and_reuses_api_key(self) -> None:
        calls: list[tuple[str, str, dict[str, str], dict]] = []

        def requester(method: str, url: str, headers: dict[str, str], payload: dict | None) -> dict:
            calls.append((method, url, headers, payload))
            if url.endswith("/auth"):
                return {"apiKey": "server-api-key"}
            return {"accessToken": f"connect-token-{len(calls)}"}

        provider = PluggyOpenFinanceProvider(
            "client-id",
            "client-secret",
            requester=requester,
        )

        first = provider.create_connect_token("nivra-user-7")
        second = provider.create_connect_token("nivra-user-7")

        self.assertEqual(first, "connect-token-2")
        self.assertEqual(second, "connect-token-3")
        self.assertEqual(sum(url.endswith("/auth") for _, url, _, _ in calls), 1)
        self.assertEqual(calls[0][3], {"clientId": "client-id", "clientSecret": "client-secret"})
        self.assertEqual(calls[1][2], {"X-API-KEY": "server-api-key"})
        self.assertEqual(
            calls[1][3],
            {"options": {"clientUserId": "nivra-user-7", "avoidDuplicates": True}},
        )

    def test_provider_retrieves_and_normalizes_item_server_side(self) -> None:
        item_id = "e2b360bd-0df4-4f73-ae93-66de4d689b86"
        calls: list[tuple[str, str, dict[str, str], dict | None]] = []

        def requester(method: str, url: str, headers: dict[str, str], payload: dict | None) -> dict:
            calls.append((method, url, headers, payload))
            if url.endswith("/auth"):
                return {"apiKey": "server-api-key"}
            return {
                "id": item_id,
                "clientUserId": "nivra-user-9",
                "status": "UPDATED",
                "executionStatus": "SUCCESS",
                "connector": {"id": 2, "name": "Sandbox PF"},
            }

        provider = PluggyOpenFinanceProvider("client-id", "client-secret", requester=requester)
        item = provider.get_item(item_id)

        self.assertEqual(item.client_user_id, "nivra-user-9")
        self.assertEqual(item.institution_name, "Sandbox PF")
        self.assertEqual(item.connector_id, 2)
        self.assertEqual(calls[1][0], "GET")
        self.assertEqual(calls[1][2], {"X-API-KEY": "server-api-key"})
        self.assertIsNone(calls[1][3])

    def test_provider_lists_accounts_and_cursor_paginated_transactions(self) -> None:
        calls: list[tuple[str, str, dict[str, str], dict | None]] = []

        def requester(method: str, url: str, headers: dict[str, str], payload: dict | None) -> dict:
            calls.append((method, url, headers, payload))
            if url.endswith("/auth"):
                return {"apiKey": "server-api-key"}
            if "/accounts?" in url:
                return {
                    "results": [{
                        "id": "account-1",
                        "name": "Conta Sandbox",
                        "type": "BANK",
                        "subtype": "CHECKING_ACCOUNT",
                        "currencyCode": "BRL",
                        "balance": 900.45,
                    }]
                }
            if "after=" not in url:
                return {
                    "results": [{
                        "id": "transaction-1",
                        "description": "Mercado",
                        "amount": -42.9,
                        "date": "2026-09-12T02:00:00.000Z",
                        "type": "DEBIT",
                        "status": "POSTED",
                        "category": "Groceries",
                        "categoryId": "08000000",
                    }],
                    "next": "?accountId=account-1&after=next-cursor",
                }
            return {
                "results": [{
                    "id": "transaction-2",
                    "description": "Salario",
                    "amount": 2500,
                    "date": "2026-09-12T12:00:00.000Z",
                    "type": "CREDIT",
                    "status": "POSTED",
                }]
            }

        provider = PluggyOpenFinanceProvider("client-id", "client-secret", requester=requester)
        accounts = provider.list_accounts("item-1")
        transactions = provider.list_transactions(accounts[0].id, accounts[0].type)

        self.assertEqual(accounts[0].balance, Decimal("900.45"))
        self.assertEqual(len(transactions), 2)
        self.assertEqual(transactions[0].amount, Decimal("42.9"))
        self.assertEqual(transactions[0].direction, "saida")
        self.assertEqual(transactions[0].date.isoformat(), "2026-09-11")
        self.assertEqual(transactions[1].direction, "entrada")
        self.assertTrue(any("after=next-cursor" in call[1] for call in calls))

    def test_missing_backend_credentials_fails_clearly(self) -> None:
        with patch.dict(os.environ, {"PLUGGY_CLIENT_ID": "", "PLUGGY_CLIENT_SECRET": ""}):
            reset_open_finance_provider()
            with self.assertRaises(OpenFinanceConfigurationError):
                get_open_finance_provider()

    def test_service_uses_internal_user_reference(self) -> None:
        provider = FakeProvider()

        response = criar_connect_token_service(42, provider)

        self.assertEqual(provider.client_user_ids, ["nivra-user-42"])
        self.assertEqual(response["connect_token"], "connect-token-sandbox")
        self.assertNotIn("client_secret", response)


class OpenFinanceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_test_database()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        remove_test_database()

    def test_connect_token_requires_session_and_csrf(self) -> None:
        unauthenticated = self.client.post("/api/open-finance/connect-token")
        register_client(self.client, "Open Finance", "open-finance@example.com")
        without_csrf = self.client.post("/api/open-finance/connect-token")

        self.assertEqual(unauthenticated.status_code, 401, unauthenticated.text)
        self.assertEqual(without_csrf.status_code, 403, without_csrf.text)

    def test_missing_pluggy_credentials_do_not_block_application_or_auth(self) -> None:
        with patch.dict(
            os.environ,
            {"PLUGGY_CLIENT_ID": "", "PLUGGY_CLIENT_SECRET": ""},
        ):
            reset_open_finance_provider()

            self.assertEqual(self.client.get("/api/health").status_code, 200)
            self.assertEqual(self.client.get("/openapi.json").status_code, 200)

            csrf = self.client.get("/api/auth/csrf")
            self.assertEqual(csrf.status_code, 200, csrf.text)

            register_client(
                self.client,
                "Sem Pluggy",
                "sem-pluggy@example.com",
            )
            logout = self.client.post(
                "/api/auth/logout",
                headers=csrf_headers(self.client),
            )
            self.assertEqual(logout.status_code, 204, logout.text)

            login_csrf = self.client.get("/api/auth/csrf")
            login = self.client.post(
                "/api/auth/login",
                headers={"X-CSRF-Token": login_csrf.json()["csrf_token"]},
                json={
                    "email": "sem-pluggy@example.com",
                    "senha": "senha-segura-123",
                },
            )
            self.assertEqual(login.status_code, 200, login.text)

            restored_session = self.client.get("/api/auth/me")
            self.assertEqual(restored_session.status_code, 200, restored_session.text)

            connect_token = self.client.post(
                "/api/open-finance/connect-token",
                headers=csrf_headers(self.client),
            )
            self.assertEqual(connect_token.status_code, 503, connect_token.text)
            self.assertEqual(
                connect_token.json()["detail"],
                "Open Finance ainda nao foi configurado neste ambiente.",
            )

            final_logout = self.client.post(
                "/api/auth/logout",
                headers=csrf_headers(self.client),
            )
            self.assertEqual(final_logout.status_code, 204, final_logout.text)
            self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_endpoint_returns_only_scoped_connect_token(self) -> None:
        register_client(self.client, "Sandbox", "sandbox@example.com")
        fake_response = {
            "connect_token": "temporary-connect-token",
            "provider": "pluggy",
            "environment": "sandbox",
        }

        with patch(
            "backend.routers.open_finance.criar_connect_token_service",
            return_value=fake_response,
        ):
            response = self.client.post(
                "/api/open-finance/connect-token",
                headers=csrf_headers(self.client),
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), fake_response)
        self.assertNotIn("client", response.text.lower())
        self.assertNotIn("api_key", response.text.lower())


if __name__ == "__main__":
    unittest.main()
