import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from tests.db_support import remove_test_database, reset_test_database


SECRET = "s" * 40
URL = "/api/internal/jobs/periodic-summaries"


class PeriodicSummaryTriggerTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        remove_test_database()

    def test_missing_configuration_fails_closed(self):
        with patch.dict(
            os.environ,
            {"CRON_SECRET": "", "PERIODIC_SUMMARY_JOBS_ENABLED": ""},
        ):
            response = self.client.get(URL)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text.casefold())

    def test_wrong_secret_is_rejected(self):
        with patch.dict(os.environ, {"CRON_SECRET": SECRET}):
            response = self.client.get(URL, headers={"Authorization": "Bearer wrong"})
        self.assertEqual(response.status_code, 401)

    def test_feature_flag_off_or_invalid_is_closed(self):
        for value in (None, "false", "invalid"):
            environment = {
                "CRON_SECRET": SECRET,
                "PERIODIC_SUMMARY_JOBS_ENABLED": value or "",
            }
            with self.subTest(value=value), patch.dict(os.environ, environment):
                response = self.client.get(URL, headers={"Authorization": f"Bearer {SECRET}"})
            self.assertEqual(response.status_code, 503)

    def test_authenticated_trigger_runs_without_user_session(self):
        environment = {
            "CRON_SECRET": SECRET,
            "PERIODIC_SUMMARY_JOBS_ENABLED": "true",
            "PERIODIC_SUMMARY_TIMEZONE": "America/Sao_Paulo",
        }
        with patch.dict(os.environ, environment):
            response = self.client.get(URL, headers={"Authorization": f"Bearer {SECRET}"})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual({item["job_type"] for item in body["results"]}, {"weekly", "monthly"})
        self.assertNotIn(SECRET, response.text)
        self.assertNotIn("R$", response.text)

    def test_wrong_method_query_and_payload_are_rejected(self):
        environment = {"CRON_SECRET": SECRET, "PERIODIC_SUMMARY_JOBS_ENABLED": "true"}
        headers = {"Authorization": f"Bearer {SECRET}"}
        with patch.dict(os.environ, environment):
            self.assertEqual(self.client.post(URL, headers=headers).status_code, 405)
            self.assertEqual(self.client.get(URL + "?user_id=1", headers=headers).status_code, 400)
            self.assertEqual(
                self.client.request("GET", URL, headers=headers, content=b'{}').status_code,
                400,
            )


if __name__ == "__main__":
    unittest.main()
