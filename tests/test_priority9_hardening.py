import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.middleware.operations import _normalized_path
from services.rate_limit_service import RateLimitExceeded
from tests.auth_support import csrf_headers, register_client
from tests.db_support import remove_test_database, reset_test_database


class Priority9MovementPaginationTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        self.a = TestClient(app)
        self.b = TestClient(app)
        register_client(self.a, "P9 A", "p9-a@example.com")
        register_client(self.b, "P9 B", "p9-b@example.com")

    def tearDown(self):
        self.a.close()
        self.b.close()
        remove_test_database()

    @staticmethod
    def _create_account(client: TestClient, name: str) -> int:
        response = client.post(
            "/api/accounts",
            headers=csrf_headers(client),
            json={"nome": name, "tipo": "digital", "saldo_inicial": 1000},
        )
        if response.status_code != 201:
            raise AssertionError(response.text)
        return int(response.json()["id"])

    def _category(self, client: TestClient) -> int:
        response = client.get("/api/categories")
        self.assertEqual(response.status_code, 200, response.text)
        return int(next(item["id"] for item in response.json() if item.get("system_key") == "food"))

    def _transaction(self, client: TestClient, account_id: int, category_id: int, description: str, value: float, kind: str) -> None:
        response = client.post(
            "/api/transactions",
            headers=csrf_headers(client),
            json={
                "valor": value,
                "tipo": kind,
                "categoria_id": category_id,
                "comentario": description,
                "data": "2026-10-10",
                "conta_id": account_id,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)

    def test_unified_history_filters_paginates_and_isolates_tenants(self):
        account_a1 = self._create_account(self.a, "Conta A1")
        account_a2 = self._create_account(self.a, "Conta A2")
        category_a = self._category(self.a)
        self._transaction(self.a, account_a1, category_a, "Mercado P9", 50, "saida")
        self._transaction(self.a, account_a1, category_a, "Receita P9", 200, "entrada")
        transfer = self.a.post(
            "/api/transfers",
            headers=csrf_headers(self.a),
            json={
                "conta_origem_id": account_a1,
                "conta_destino_id": account_a2,
                "valor": 25,
                "descricao": "Reserva P9",
                "data": "2026-10-10",
            },
        )
        self.assertEqual(transfer.status_code, 201, transfer.text)

        account_b = self._create_account(self.b, "Conta B")
        category_b = self._category(self.b)
        self._transaction(self.b, account_b, category_b, "Segredo B", 999, "saida")

        first = self.a.get("/api/transactions/page", params={"limit": 2})
        self.assertEqual(first.status_code, 200, first.text)
        body = first.json()
        self.assertEqual(body["total"], 3)
        self.assertEqual(len(body["items"]), 2)
        self.assertTrue(body["has_more"])
        self.assertEqual(body["summary"], {"entradas": 200.0, "saidas": 50.0, "saldo": 150.0})
        self.assertNotIn("Segredo B", first.text)

        second = self.a.get("/api/transactions/page", params={"limit": 2, "offset": 2})
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(len(second.json()["items"]), 1)
        self.assertFalse(second.json()["has_more"])

        search = self.a.get("/api/transactions/page", params={"q": "mercado"})
        self.assertEqual(search.json()["total"], 1)
        self.assertEqual(search.json()["items"][0]["transaction"]["comentario"], "Mercado P9")

        transfers = self.a.get("/api/transactions/page", params={"movement_type": "transferencia"})
        self.assertEqual(transfers.json()["total"], 1)
        self.assertEqual(transfers.json()["items"][0]["kind"], "transfer")

        forged_account = self.a.get("/api/transactions/page", params={"account_id": account_b})
        self.assertEqual(forged_account.status_code, 200, forged_account.text)
        self.assertEqual(forged_account.json()["total"], 0)

        invalid_dates = self.a.get(
            "/api/transactions/page",
            params={"start_date": "2026-10-11", "end_date": "2026-10-10"},
        )
        self.assertEqual(invalid_dates.status_code, 400, invalid_dates.text)


class Priority9HttpHardeningTests(unittest.TestCase):
    def test_api_responses_receive_security_and_correlation_headers(self):
        with TestClient(app) as client:
            response = client.get("/api/health", headers={"X-Request-ID": "p9-request-1234"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["x-request-id"], "p9-request-1234")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertIn("camera=()", response.headers["permissions-policy"])

    def test_general_rate_limit_returns_retry_after_without_exposing_subject(self):
        with patch.dict(os.environ, {"API_RATE_LIMIT_ENABLED": "true"}), patch(
            "backend.middleware.operations.consumir_limite",
            side_effect=RateLimitExceeded(17),
        ):
            with TestClient(app) as client:
                response = client.get("/api/accounts")
        self.assertEqual(response.status_code, 429, response.text)
        self.assertEqual(response.headers["retry-after"], "17")
        self.assertEqual(response.json(), {"detail": "Muitas solicitações. Tente novamente em instantes."})

    def test_structured_path_replaces_identifiers(self):
        self.assertEqual(_normalized_path("/api/goals/123/movements/456"), "/api/goals/{id}/movements/{id}")


if __name__ == "__main__":
    unittest.main()
