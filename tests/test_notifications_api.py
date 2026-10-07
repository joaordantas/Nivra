import unittest

from fastapi.testclient import TestClient

from backend.main import app
from services.notification_service import notification_service
from services.notification_types import NotificationType
from tests.auth_support import csrf_headers, register_client
from tests.db_support import remove_test_database, reset_test_database


class NotificationApiTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        self.a = TestClient(app)
        self.b = TestClient(app)
        self.user_a = register_client(self.a, "API A", "notification-api-a@example.com")
        self.user_b = register_client(self.b, "API B", "notification-api-b@example.com")
        self.headers_a = csrf_headers(self.a)
        self.headers_b = csrf_headers(self.b)

    def tearDown(self):
        self.a.close()
        self.b.close()
        remove_test_database()

    def _notify(self, user_id: int, label: str, notification_type=NotificationType.SYSTEM):
        return notification_service.notify(
            user_id,
            notification_type,
            f"Titulo {label}",
            f"Mensagem {label}",
            dedupe_key=f"api:{label}",
            metadata={"route": "/dashboard", "source_type": "test", "source_id": label},
        )

    def test_queries_require_authentication_and_isolate_accounts(self):
        own = self._notify(self.user_a["id"], "a")
        self._notify(self.user_b["id"], "b")

        with TestClient(app) as anonymous:
            self.assertEqual(anonymous.get("/api/notifications").status_code, 401)
            self.assertEqual(anonymous.get("/api/notifications/unread-count").status_code, 401)

        response = self.a.get("/api/notifications")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("chave_dedupe", response.json()[0])
        self.assertEqual([item["id"] for item in response.json()], [own["id"]])
        self.assertEqual(self.a.get("/api/notifications/unread-count").json(), {"unread_count": 1})

    def test_mutations_require_csrf_and_do_not_accept_cross_account_access(self):
        own = self._notify(self.user_a["id"], "a")
        private_b = self._notify(self.user_b["id"], "b")

        self.assertEqual(self.a.post(f"/api/notifications/{own['id']}/read").status_code, 403)
        self.assertEqual(
            self.a.post(
                f"/api/notifications/{private_b['id']}/read", headers=self.headers_a
            ).status_code,
            404,
        )
        hidden_delete = self.a.delete(
            f"/api/notifications/{private_b['id']}", headers=self.headers_a
        )
        self.assertEqual(hidden_delete.status_code, 204, hidden_delete.text)
        self.assertEqual(self.b.get("/api/notifications/unread-count").json()["unread_count"], 1)

        read = self.a.post(f"/api/notifications/{own['id']}/read", headers=self.headers_a)
        self.assertEqual(read.status_code, 200, read.text)
        self.assertTrue(read.json()["lida"])
        self.assertEqual(
            self.a.delete(f"/api/notifications/{own['id']}", headers=self.headers_a).status_code,
            204,
        )
        self.assertEqual(
            self.a.delete(f"/api/notifications/{own['id']}", headers=self.headers_a).status_code,
            204,
        )

    def test_read_all_filter_and_pagination_contract(self):
        self._notify(self.user_a["id"], "system-1")
        card = self._notify(self.user_a["id"], "card", NotificationType.CARD_ALERT)
        self._notify(self.user_a["id"], "system-2")
        self._notify(self.user_b["id"], "private")

        page = self.a.get("/api/notifications", params={"limit": 1, "offset": 1})
        filtered = self.a.get("/api/notifications", params={"tipo": "card_alert"})
        self.assertEqual(page.status_code, 200, page.text)
        self.assertEqual(page.json()[0]["id"], card["id"])
        self.assertEqual([item["id"] for item in filtered.json()], [card["id"]])
        self.assertEqual(self.a.get("/api/notifications", params={"limit": 101}).status_code, 422)
        self.assertEqual(self.a.get("/api/notifications", params={"tipo": "arbitrary"}).status_code, 422)

        without_csrf = self.a.post("/api/notifications/read-all")
        read_all = self.a.post("/api/notifications/read-all", headers=self.headers_a)
        self.assertEqual(without_csrf.status_code, 403)
        self.assertEqual(read_all.status_code, 200, read_all.text)
        self.assertEqual(read_all.json(), {"updated_count": 3})
        self.assertEqual(self.a.get("/api/notifications", params={"unread_only": True}).json(), [])
        self.assertEqual(self.b.get("/api/notifications/unread-count").json()["unread_count"], 1)

    def test_no_arbitrary_public_creation_endpoint_exists(self):
        response = self.a.post(
            "/api/notifications",
            headers=self.headers_a,
            json={"tipo": "system", "titulo": "Nao", "mensagem": "Nao"},
        )
        self.assertEqual(response.status_code, 405, response.text)


if __name__ == "__main__":
    unittest.main()
