import unittest
from unittest.mock import patch

from tests.integration.financial_threshold_postgres_gate import test_url_from_env


class FinancialThresholdPostgresGateGuardTests(unittest.TestCase):
    def test_only_named_disposable_postgresql_database_is_accepted(self):
        with patch(
            "tests.integration.financial_threshold_postgres_gate.dotenv_values",
            return_value={},
        ), patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "obrigatória"):
                test_url_from_env()
        with patch(
            "tests.integration.financial_threshold_postgres_gate.dotenv_values",
            return_value={},
        ), patch.dict(
            "os.environ",
            {"P77_TEST_DATABASE_URL": "postgresql://u:p@h/production"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "nivra_p77_gate"):
                test_url_from_env()
        raw = "postgresql://u:p@h/nivra_p77_gate"
        with patch(
            "tests.integration.financial_threshold_postgres_gate.dotenv_values",
            return_value={},
        ), patch.dict("os.environ", {"P77_TEST_DATABASE_URL": raw}, clear=True):
            self.assertEqual(test_url_from_env(), raw)


if __name__ == "__main__":
    unittest.main()
