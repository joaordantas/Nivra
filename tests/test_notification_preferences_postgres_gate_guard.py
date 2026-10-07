import unittest
from unittest.mock import patch

from sqlalchemy.engine import make_url

from tests.integration.notification_preferences_postgres_gate import (
    test_url_from_env as guarded_url,
)


class NotificationPreferencesPostgresGateGuardTests(unittest.TestCase):
    def test_requires_explicit_p74_url(self):
        with patch(
            "tests.integration.notification_preferences_postgres_gate.dotenv_values",
            return_value={},
        ), patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "P74_TEST_DATABASE_URL"):
                guarded_url()

    def test_rejects_database_without_p74_marker(self):
        with patch(
            "tests.integration.notification_preferences_postgres_gate.dotenv_values",
            return_value={},
        ), patch.dict(
            "os.environ",
            {"P74_TEST_DATABASE_URL": "postgresql://u:p@test.example/neondb"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "p74"):
                guarded_url()

    def test_rejects_configured_application_target(self):
        candidate = "postgresql://u:p@test.example/nivra_p74_gate"
        with patch(
            "tests.integration.notification_preferences_postgres_gate.dotenv_values",
            return_value={},
        ), patch.dict(
            "os.environ",
            {"P74_TEST_DATABASE_URL": candidate, "DATABASE_URL": candidate},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
                guarded_url()

    def test_accepts_distinct_marked_postgresql_database(self):
        candidate = "postgresql://u:p@test.example/nivra_p74_gate"
        with patch(
            "tests.integration.notification_preferences_postgres_gate.dotenv_values",
            return_value={},
        ), patch.dict("os.environ", {"P74_TEST_DATABASE_URL": candidate}, clear=True):
            self.assertEqual(guarded_url(), candidate)

    def test_derives_isolated_database_from_known_preview_endpoint(self):
        preview = "postgresql://u:p@ep-preview.neon.tech/nivra_preview"
        with patch(
            "tests.integration.notification_preferences_postgres_gate.dotenv_values",
            return_value={"P65_PREVIEW_BRANCH_DATABASE_URL": preview},
        ), patch.dict("os.environ", {}, clear=True):
            derived = guarded_url()
        self.assertEqual(make_url(derived).database, "nivra_p74_gate")


if __name__ == "__main__":
    unittest.main()
