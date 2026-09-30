import unittest
from unittest.mock import patch

from scripts.lumi_postgres_gate_guard import test_url_from_env as guarded_test_url_from_env


class LumiPostgresGateGuardTests(unittest.TestCase):
    def test_rejects_missing_test_url(self):
        with patch("scripts.lumi_postgres_gate_guard.dotenv_values", return_value={}), patch.dict(
            "os.environ", {"DATABASE_URL": "postgresql://u:p@prod.example/nivra"}, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "P65_TEST_DATABASE_URL"):
                guarded_test_url_from_env()

    def test_rejects_production_endpoint_even_with_different_database(self):
        with patch("scripts.lumi_postgres_gate_guard.dotenv_values", return_value={}), patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://u:p@ep-prod-pooler.neon.tech/nivra",
                "P65_TEST_DATABASE_URL": "postgresql://u:p@ep-prod.neon.tech/nivra_p65_gate",
            }, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "endpoint"):
                guarded_test_url_from_env()

    def test_rejects_database_without_test_marker(self):
        with patch("scripts.lumi_postgres_gate_guard.dotenv_values", return_value={}), patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://u:p@ep-prod.neon.tech/nivra",
                "P65_TEST_DATABASE_URL": "postgresql://u:p@ep-other.neon.tech/nivra",
            }, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "descartável"):
                guarded_test_url_from_env()

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
                guarded_test_url_from_env()

    def test_accepts_separate_test_endpoint(self):
        candidate = "postgresql://u:p@ep-test.neon.tech/nivra_p65_gate"
        with patch("scripts.lumi_postgres_gate_guard.dotenv_values", return_value={}), patch.dict(
            "os.environ",
            {"DATABASE_URL": "postgresql://u:p@ep-prod.neon.tech/nivra", "P65_TEST_DATABASE_URL": candidate},
            clear=True
        ):
            self.assertEqual(guarded_test_url_from_env(), candidate)

    def test_accepts_separate_database_on_known_preview_branch_for_p69(self):
        preview = "postgresql://u:p@ep-preview.neon.tech/neondb"
        candidate = "postgresql://u:p@ep-preview.neon.tech/nivra_lumi_p69_gate"
        with patch("scripts.lumi_postgres_gate_guard.dotenv_values", return_value={}), patch.dict(
            "os.environ",
            {"P65_PREVIEW_BRANCH_DATABASE_URL": preview, "P69_TEST_DATABASE_URL": candidate},
            clear=True,
        ):
            self.assertEqual(guarded_test_url_from_env(), candidate)

    def test_derives_p69_database_without_exposing_a_second_url(self):
        preview = "postgresql://u:p@ep-preview.neon.tech/neondb?sslmode=require"
        with patch(
            "scripts.lumi_postgres_gate_guard.dotenv_values",
            return_value={"P65_PREVIEW_BRANCH_DATABASE_URL": preview},
        ), patch.dict("os.environ", {}, clear=True):
            derived = guarded_test_url_from_env()
        self.assertEqual(derived, "postgresql+pg8000://u:p@ep-preview.neon.tech/nivra_lumi_p69_gate")

    def test_rejects_p69_when_it_is_the_preview_database_itself(self):
        preview = "postgresql://u:p@ep-preview.neon.tech/neondb"
        with patch("scripts.lumi_postgres_gate_guard.dotenv_values", return_value={}), patch.dict(
            "os.environ",
            {"P65_PREVIEW_BRANCH_DATABASE_URL": preview, "P69_TEST_DATABASE_URL": preview},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "outro database"):
                guarded_test_url_from_env()


if __name__ == "__main__":
    unittest.main()
