import unittest
from unittest.mock import patch

from tests.integration.budget_postgres_gate import test_url_from_env


class BudgetPostgresGateGuardTests(unittest.TestCase):
    def test_requires_postgresql_configuration(self):
        with patch("tests.integration.budget_postgres_gate.dotenv_values", return_value={}), patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "obrigatória"):
                test_url_from_env()

    def test_rejects_non_disposable_database(self):
        with patch("tests.integration.budget_postgres_gate.dotenv_values", return_value={}), patch.dict("os.environ", {"P81_TEST_DATABASE_URL": "postgresql://u:p@host/production"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "nivra_p81_gate"):
                test_url_from_env()

    def test_accepts_only_named_disposable_database(self):
        raw = "postgresql://u:p@host/nivra_p81_gate"
        with patch("tests.integration.budget_postgres_gate.dotenv_values", return_value={}), patch.dict("os.environ", {"P81_TEST_DATABASE_URL": raw}, clear=True):
            self.assertEqual(test_url_from_env(), raw)


if __name__ == "__main__":
    unittest.main()
