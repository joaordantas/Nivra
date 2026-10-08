import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from sqlalchemy import create_engine, inspect, text

from database.migrations import get_alembic_config


class NotificationOperationsMigrationTests(unittest.TestCase):
    def test_upgrade_backfills_ledger_and_downgrade_preserves_notifications(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "migration.db"
            engine = create_engine(f"sqlite+pysqlite:///{database.as_posix()}", future=True)
            try:
                with engine.connect() as connection:
                    config = get_alembic_config()
                    config.attributes["connection"] = connection
                    command.upgrade(config, "e4f5a6b7c8d9")
                    connection.execute(text(
                        "INSERT INTO usuarios (id,usuario,email,senha) VALUES (1,'A','a@example.com','x')"
                    ))
                    connection.execute(text(
                        "INSERT INTO notifications "
                        "(usuario_id,tipo,severidade,titulo,mensagem,chave_dedupe) "
                        "VALUES (1,'system','info','Title','Message','stable:key')"
                    ))
                    connection.commit()
                    command.upgrade(config, "head")
                    self.assertIn("notification_dedupe_ledger", inspect(connection).get_table_names())
                    self.assertEqual(connection.execute(text(
                        "SELECT dedupe_key FROM notification_dedupe_ledger WHERE usuario_id=1"
                    )).scalar_one(), "stable:key")
                    columns = {column["name"] for column in inspect(connection).get_columns("periodic_summary_job_runs")}
                    self.assertTrue({"generated_count", "deduplicated_count", "duration_ms"}.issubset(columns))
                    command.downgrade(config, "e4f5a6b7c8d9")
                    self.assertNotIn("notification_dedupe_ledger", inspect(connection).get_table_names())
                    self.assertEqual(connection.execute(text(
                        "SELECT chave_dedupe FROM notifications WHERE usuario_id=1"
                    )).scalar_one(), "stable:key")
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
