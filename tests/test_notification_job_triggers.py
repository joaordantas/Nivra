import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from tests.db_support import remove_test_database, reset_test_database


SECRET = "n" * 40
HEADERS = {"Authorization": f"Bearer {SECRET}"}


class NotificationJobTriggerTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        remove_test_database()

    def test_new_triggers_are_hidden_authenticated_and_disabled_by_default(self):
        for url in (
            "/api/internal/jobs/financial-alerts",
            "/api/internal/jobs/notification-maintenance",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 503)
                with patch.dict(os.environ, {"CRON_SECRET": SECRET}, clear=False):
                    self.assertEqual(self.client.get(url, headers=HEADERS).status_code, 503)
                self.assertNotIn(url, self.client.get("/openapi.json").text)

    def test_financial_alert_trigger_rejects_input_and_runs_when_explicitly_enabled(self):
        environment = {
            "CRON_SECRET": SECRET,
            "FINANCIAL_ALERTS_ENABLED": "true",
            "PERIODIC_SUMMARY_TIMEZONE": "America/Sao_Paulo",
        }
        with patch.dict(os.environ, environment, clear=False):
            self.assertEqual(self.client.get(
                "/api/internal/jobs/financial-alerts?usuario_id=1", headers=HEADERS
            ).status_code, 400)
            response = self.client.get("/api/internal/jobs/financial-alerts", headers=HEADERS)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["results"][0]["job_type"], "financial_alerts")

    def test_maintenance_requires_explicit_policy_and_can_run(self):
        base = {"CRON_SECRET": SECRET, "NOTIFICATION_MAINTENANCE_ENABLED": "true"}
        missing_policy = {
            **base,
            "NOTIFICATION_READ_RETENTION_DAYS": "",
            "NOTIFICATION_JOB_RETENTION_DAYS": "",
        }
        with patch.dict(os.environ, missing_policy, clear=False):
            self.assertEqual(self.client.get(
                "/api/internal/jobs/notification-maintenance", headers=HEADERS
            ).status_code, 503)
        environment = {
            **base,
            "NOTIFICATION_READ_RETENTION_DAYS": "30",
            "NOTIFICATION_JOB_RETENTION_DAYS": "90",
            "NOTIFICATION_MAINTENANCE_BATCH_SIZE": "10",
        }
        with patch.dict(os.environ, environment, clear=False):
            response = self.client.get("/api/internal/jobs/notification-maintenance", headers=HEADERS)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["results"][0]["job_type"], "cleanup")


if __name__ == "__main__":
    unittest.main()
