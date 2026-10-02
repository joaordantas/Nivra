import unittest
from unittest.mock import patch

from tests.integration.notification_postgres_gate import test_url_from_env as guarded_url


class NotificationPostgresGateGuardTests(unittest.TestCase):
    def test_requires_explicit_p71_url(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "P71_TEST_DATABASE_URL"):
                guarded_url()

    def test_rejects_database_without_p71_marker(self):
        with patch.dict(
            "os.environ",
            {"P71_TEST_DATABASE_URL": "postgresql://u:p@test.example/neondb"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "p71"):
                guarded_url()

    def test_rejects_configured_application_target(self):
        candidate = "postgresql://u:p@test.example/nivra_p71_gate"
        with patch.dict(
            "os.environ",
            {"P71_TEST_DATABASE_URL": candidate, "DATABASE_URL": candidate},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
                guarded_url()

    def test_accepts_distinct_marked_postgresql_database(self):
        candidate = "postgresql://u:p@test.example/nivra_p71_gate"
        with patch.dict("os.environ", {"P71_TEST_DATABASE_URL": candidate}, clear=True):
            self.assertEqual(guarded_url(), candidate)


if __name__ == "__main__":
    unittest.main()
