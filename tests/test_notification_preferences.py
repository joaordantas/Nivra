import unittest
from datetime import date

from fastapi.testclient import TestClient

from backend.main import app
from database.connection import get_connection
from services.financial_notification_service import financial_notification_service
from services.notification_preference_service import notification_preference_service
from services.notification_service import notification_service
from tests.auth_support import csrf_headers, register_client
from tests.db_support import remove_test_database, reset_test_database


DEFAULTS = {
    "invoice_due_soon": True,
    "invoice_overdue": True,
    "card_limit": True,
    "unusual_expense": True,
    "weekly_summary": True,
    "monthly_summary": True,
    "budget_threshold": True,
    "goal_progress": True,
}

FINANCIAL_ALERT_DEFAULTS = (
    "invoice_due_soon",
    "invoice_overdue",
    "card_limit",
    "unusual_expense",
)


def card_fact(
    event_id: int,
    *,
    percentage: float = 20,
    amount: float = 0,
    due_date: str | None = None,
    status: str | None = None,
) -> dict:
    return {
        "card_id": event_id,
        "name": f"Cartao ficticio {event_id}",
        "total_limit": 1000.0,
        "committed": percentage * 10,
        "available": max(1000 - percentage * 10, 0),
        "committed_percent": percentage,
        "current_invoice_amount": amount,
        "closing_date": None,
        "due_date": due_date,
        "invoice_status": status,
        "next_due_invoice_amount": amount,
        "next_due_date": due_date,
        "next_due_status": status,
    }


def commitment(*cards: dict) -> dict:
    return {
        "total_limit": sum(card["total_limit"] for card in cards),
        "total_committed": sum(card["committed"] for card in cards),
        "total_available": sum(card["available"] for card in cards),
        "committed_percent": None,
        "active_cards": len(cards),
        "cards": list(cards),
    }


def unusual_fact(event_id: int) -> dict:
    return {
        "id": event_id,
        "description": "Evento ficticio",
        "amount": 500.0,
        "date": "2026-10-06",
        "category": "Categoria ficticia",
        "account": "Conta ficticia",
        "source": "manual",
        "baseline": 50.0,
        "times_baseline": 10.0,
        "context": "both",
        "sample_size": 8,
        "global_baseline": 50.0,
        "category_baseline": 50.0,
        "median_absolute_deviation": 0.0,
        "robust_z_score": None,
        "reason": "Deteccao deterministica ficticia.",
        "data_nature": "deterministic_inference",
    }


class NotificationPreferenceApiTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        self.a = TestClient(app)
        self.b = TestClient(app)
        self.user_a = register_client(self.a, "Preferencias A", "p74-a@example.com")
        self.user_b = register_client(self.b, "Preferencias B", "p74-b@example.com")
        self.headers_a = csrf_headers(self.a)
        self.headers_b = csrf_headers(self.b)

    def tearDown(self):
        self.a.close()
        self.b.close()
        remove_test_database()

    def test_missing_configuration_returns_all_preferences_enabled(self):
        response = self.a.get("/api/notifications/preferences")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), DEFAULTS)

        connection = get_connection()
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM notification_preferences WHERE usuario_id = ?",
                (self.user_a["id"],),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 0)

    def test_update_is_validated_idempotent_and_scoped_to_session_user(self):
        without_csrf = self.a.patch(
            "/api/notifications/preferences",
            json={"unusual_expense": False},
        )
        self.assertEqual(without_csrf.status_code, 403)

        for payload in (
            {},
            {"arbitrary": False},
            {"card_limit": "false"},
            {"card_limit": None},
            {"usuario_id": self.user_b["id"], "card_limit": False},
        ):
            with self.subTest(payload=payload):
                response = self.a.patch(
                    "/api/notifications/preferences",
                    headers=self.headers_a,
                    json=payload,
                )
                self.assertEqual(response.status_code, 422, response.text)

        for _ in range(2):
            updated = self.a.patch(
                "/api/notifications/preferences",
                headers=self.headers_a,
                json={"unusual_expense": False, "card_limit": False},
            )
            self.assertEqual(updated.status_code, 200, updated.text)
            self.assertFalse(updated.json()["unusual_expense"])
            self.assertFalse(updated.json()["card_limit"])

        self.assertEqual(self.b.get("/api/notifications/preferences").json(), DEFAULTS)

    def test_update_preserves_old_notifications_and_financial_tables(self):
        old = notification_service.notify(
            self.user_a["id"],
            "financial_alert",
            "Notificacao existente",
            "Registro anterior deve permanecer.",
            dedupe_key="p74:existing",
        )
        connection = get_connection()
        try:
            financial_before = connection.execute(
                "SELECT COUNT(*) FROM transacoes"
            ).fetchone()[0]
        finally:
            connection.close()

        response = self.a.patch(
            "/api/notifications/preferences",
            headers=self.headers_a,
            json={"unusual_expense": False},
        )
        self.assertEqual(response.status_code, 200, response.text)

        connection = get_connection()
        try:
            financial_after = connection.execute(
                "SELECT COUNT(*) FROM transacoes"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(financial_after, financial_before)
        self.assertEqual([item["id"] for item in notification_service.list(self.user_a["id"])], [old["id"]])


class NotificationPreferenceProducerTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        connection = get_connection()
        connection.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES "
            "(1, 'P74 A', 'p74-producer-a@example.com', 'hash')"
        )
        connection.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES "
            "(2, 'P74 B', 'p74-producer-b@example.com', 'hash')"
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        remove_test_database()

    def _publish(self, user_id: int, key: str, event_id: int):
        if key == "invoice_due_soon":
            cards = commitment(card_fact(event_id, amount=200, due_date="2026-10-09", status="fechada"))
            unusual = []
        elif key == "invoice_overdue":
            cards = commitment(card_fact(event_id, amount=200, due_date="2026-10-05", status="vencida"))
            unusual = []
        elif key == "card_limit":
            cards = commitment(card_fact(event_id, percentage=92))
            unusual = []
        else:
            cards = commitment()
            unusual = [unusual_fact(event_id)]
        return financial_notification_service.publish_from_insights(
            user_id,
            card_commitment=cards,
            unusual_expenses=unusual,
            reference=date(2026, 10, 6),
        )

    def test_each_producer_respects_disabled_and_enabled_preference(self):
        for event_id, key in enumerate(FINANCIAL_ALERT_DEFAULTS, start=740):
            with self.subTest(preference=key):
                notification_preference_service.update(1, {key: False})
                suppressed = self._publish(1, key, event_id)
                self.assertEqual(suppressed.suppressed, 1)
                self.assertEqual(notification_service.list(1), [])

                notification_preference_service.update(1, {key: True})
                replay = self._publish(1, key, event_id)
                self.assertEqual(replay.suppressed, 1)
                self.assertEqual(notification_service.list(1), [])

                delivered = self._publish(1, key, event_id + 100)
                self.assertEqual(delivered.delivered_or_deduplicated, 1)
                created = notification_service.list(1)
                self.assertEqual(len(created), 1)
                notification_service.delete(1, created[0]["id"])

    def test_replay_dedupe_and_different_users_remain_isolated(self):
        notification_preference_service.update(1, {"card_limit": False})
        self._publish(1, "card_limit", 750)
        self._publish(2, "card_limit", 750)
        self._publish(2, "card_limit", 750)

        self.assertEqual(notification_service.list(1), [])
        self.assertEqual(len(notification_service.list(2)), 1)


if __name__ == "__main__":
    unittest.main()
