import unittest

from fastapi.testclient import TestClient

from backend.main import app
from services.notification_service import NotificationNotFoundError, notification_service
from services.notification_types import NotificationSeverity, NotificationType
from tests.auth_support import register_client
from tests.db_support import remove_test_database, reset_test_database


class NotificationServiceTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        self.client_a = TestClient(app)
        self.client_b = TestClient(app)
        self.user_a = register_client(
            self.client_a, "Notificacao A", "notification-a@example.com"
        )
        self.user_b = register_client(
            self.client_b, "Notificacao B", "notification-b@example.com"
        )

    def tearDown(self):
        self.client_a.close()
        self.client_b.close()
        remove_test_database()

    def _notify(self, user_id: int, suffix: str, **overrides):
        parameters = {
            "notification_type": NotificationType.SYSTEM,
            "title": f"Titulo {suffix}",
            "message": f"Mensagem {suffix}",
            "severity": NotificationSeverity.INFO,
            "metadata": {"route": "/dashboard", "source_type": "test", "source_id": suffix},
        }
        parameters.update(overrides)
        return notification_service.notify(user_id, **parameters)

    def test_create_list_filter_and_paginate_newest_first(self):
        first = self._notify(self.user_a["id"], "1")
        second = self._notify(
            self.user_a["id"],
            "2",
            notification_type=NotificationType.CARD_ALERT,
            severity=NotificationSeverity.WARNING,
        )
        third = self._notify(self.user_a["id"], "3")
        self._notify(self.user_b["id"], "privada")

        page = notification_service.list(self.user_a["id"], limit=2)
        filtered = notification_service.list(
            self.user_a["id"], notification_type=NotificationType.CARD_ALERT
        )

        self.assertEqual([item["id"] for item in page], [third["id"], second["id"]])
        self.assertEqual([item["id"] for item in filtered], [second["id"]])
        self.assertEqual(
            notification_service.list(self.user_a["id"], limit=2, offset=2)[0]["id"],
            first["id"],
        )
        self.assertEqual(notification_service.unread_count(self.user_a["id"]), 3)

    def test_dedupe_is_scoped_per_user_and_preserves_original_payload(self):
        first = self._notify(
            self.user_a["id"], "original", dedupe_key="statement:2026-10"
        )
        replay = self._notify(
            self.user_a["id"], "alterado", dedupe_key="statement:2026-10"
        )
        other_user = self._notify(
            self.user_b["id"], "outro", dedupe_key="statement:2026-10"
        )

        self.assertEqual(replay["id"], first["id"])
        self.assertEqual(replay["titulo"], first["titulo"])
        self.assertNotEqual(other_user["id"], first["id"])
        self.assertEqual(notification_service.unread_count(self.user_a["id"]), 1)

    def test_read_read_all_and_delete_are_idempotent_and_owned(self):
        first = self._notify(self.user_a["id"], "1")
        second = self._notify(self.user_a["id"], "2")
        private_b = self._notify(self.user_b["id"], "b")

        read_once = notification_service.mark_read(self.user_a["id"], first["id"])
        read_twice = notification_service.mark_read(self.user_a["id"], first["id"])
        self.assertTrue(read_once["lida"])
        self.assertEqual(read_twice["lida_em"], read_once["lida_em"])
        self.assertEqual(notification_service.mark_all_read(self.user_a["id"]), 1)
        self.assertEqual(notification_service.mark_all_read(self.user_a["id"]), 0)
        self.assertEqual(notification_service.unread_count(self.user_a["id"]), 0)
        self.assertEqual(notification_service.unread_count(self.user_b["id"]), 1)

        with self.assertRaises(NotificationNotFoundError):
            notification_service.mark_read(self.user_a["id"], private_b["id"])
        self.assertFalse(notification_service.delete(self.user_a["id"], private_b["id"]))
        self.assertTrue(notification_service.delete(self.user_a["id"], second["id"]))
        self.assertFalse(notification_service.delete(self.user_a["id"], second["id"]))

    def test_closed_contract_and_controlled_metadata_are_validated(self):
        valid = self._notify(self.user_a["id"], "valida")
        self.assertEqual(valid["metadados"]["route"], "/dashboard")

        invalid_calls = (
            lambda: self._notify(self.user_a["id"], "x", notification_type="arbitrary"),
            lambda: self._notify(self.user_a["id"], "x", severity="urgent"),
            lambda: self._notify(self.user_a["id"], "x", title="   "),
            lambda: self._notify(self.user_a["id"], "x", message="m" * 601),
            lambda: self._notify(self.user_a["id"], "x", dedupe_key="d" * 161),
            lambda: self._notify(self.user_a["id"], "x", metadata={"secret": "no"}),
            lambda: self._notify(self.user_a["id"], "x", metadata={"route": "https://example.com"}),
            lambda: self._notify(self.user_a["id"], "x", metadata={"source_id": [1]}),
        )
        for invalid_call in invalid_calls:
            with self.subTest(call=invalid_call):
                with self.assertRaises(ValueError):
                    invalid_call()

        with self.assertRaises(ValueError):
            notification_service.list(self.user_a["id"], limit=101)
        with self.assertRaises(ValueError):
            notification_service.list(self.user_a["id"], offset=10_001)


if __name__ == "__main__":
    unittest.main()
