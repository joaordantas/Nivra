import unittest
from unittest.mock import patch

from scripts.lumi_postgres_gate_guard import test_url_from_env


class LumiPostgresGateGuardTests(unittest.TestCase):
    def test_rejects_missing_test_url(self):
        with patch("scripts.lumi_postgres_gate_guard.dotenv_values", return_value={}), patch.dict(
            "os.environ", {"DATABASE_URL": "postgresql://u:p@prod.example/nivra"}, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "P65_TEST_DATABASE_URL"):
                test_url_from_env()

    def test_rejects_production_endpoint_even_with_different_database(self):
        with patch("scripts.lumi_postgres_gate_guard.dotenv_values", return_value={}), patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://u:p@ep-prod-pooler.neon.tech/nivra",
                "P65_TEST_DATABASE_URL": "postgresql://u:p@ep-prod.neon.tech/nivra_p65_gate",
            }, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "endpoint"):
                test_url_from_env()

    def test_rejects_database_without_test_marker(self):
        with patch("scripts.lumi_postgres_gate_guard.dotenv_values", return_value={}), patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://u:p@ep-prod.neon.tech/nivra",
                "P65_TEST_DATABASE_URL": "postgresql://u:p@ep-other.neon.tech/nivra",
            }, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "descartável"):
                test_url_from_env()

    def test_rejects_unpooled_production_endpoint(self):
        with patch("scripts.lumi_postgres_gate_guard.dotenv_values", return_value={}), patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://u:p@ep-prod-pooler.neon.tech/nivra",
                "DATABASE_URL_UNPOOLED": "postgresql://u:p@ep-prod.neon.tech/nivra",
                "P65_TEST_DATABASE_URL": "postgresql://u:p@ep-prod.neon.tech/nivra_p65_gate",
            }, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "endpoint"):
                test_url_from_env()

    def test_accepts_separate_test_endpoint(self):
        candidate = "postgresql://u:p@ep-test.neon.tech/nivra_p65_gate"
        with patch("scripts.lumi_postgres_gate_guard.dotenv_values", return_value={}), patch.dict(
            "os.environ",
            {"DATABASE_URL": "postgresql://u:p@ep-prod.neon.tech/nivra", "P65_TEST_DATABASE_URL": candidate},
            clear=True
        ):
            self.assertEqual(test_url_from_env(), candidate)


if __name__ == "__main__":
    unittest.main()
