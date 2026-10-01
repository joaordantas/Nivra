import os
import unittest
from unittest.mock import patch

from database.connection import database_target_fingerprint, get_database_url


class DatabaseConfigTests(unittest.TestCase):
    def test_testes_exigem_url_separada(self):
        with patch.dict(os.environ, {"APP_ENV": "test"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "TEST_DATABASE_URL"):
                get_database_url()

    def test_testes_recusam_url_de_producao(self):
        url = "postgresql://usuario:senha@host/banco"
        with patch.dict(
            os.environ,
            {"APP_ENV": "test", "DATABASE_URL": url, "TEST_DATABASE_URL": url},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "nao pode apontar"):
                get_database_url()

    def test_execucao_normal_recusa_sqlite(self):
        with patch.dict(
            os.environ,
            {"APP_ENV": "production", "DATABASE_URL": "sqlite:///storage/banco.db"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "PostgreSQL"):
                get_database_url()

    def test_migration_prefere_url_sem_pooling(self):
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql://app:senha@ep-pooler.neon.tech/app",
                "DATABASE_URL_UNPOOLED": "postgresql://app:senha@ep.neon.tech/app",
            },
            clear=True,
        ):
            self.assertEqual(
                get_database_url(migration=True),
                "postgresql+psycopg://app:senha@ep.neon.tech/app",
            )

    def test_fingerprint_identifica_somente_host_e_database(self):
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql://user-a:secret-a@ep-preview.neon.tech/nivra?sslmode=require",
            },
            clear=True,
        ):
            first = database_target_fingerprint()
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql://user-b:secret-b@ep-preview.neon.tech/nivra?channel_binding=require",
            },
            clear=True,
        ):
            second = database_target_fingerprint()

        self.assertEqual(first, second)
        self.assertEqual(len(first), 12)
        self.assertNotIn("secret", first)


if __name__ == "__main__":
    unittest.main()
