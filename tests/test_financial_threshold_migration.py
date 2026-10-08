import unittest
from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, inspect, text

from database.migrations import get_alembic_config


class FinancialThresholdMigrationTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).resolve().parents[1] / "storage" / "test_p77_migration.db"
        self.path.unlink(missing_ok=True)
        self.engine = create_engine(
            f"sqlite+pysqlite:///{self.path.as_posix()}", future=True
        )

    def tearDown(self):
        self.engine.dispose()
        self.path.unlink(missing_ok=True)

    def test_upgrade_downgrade_reupgrade_preserve_existing_notifications(self):
        with self.engine.connect() as connection:
            config = get_alembic_config()
            config.attributes["connection"] = connection
            command.upgrade(config, "d3e4f5a6b7c8")
            connection.execute(text(
                "INSERT INTO usuarios (id,usuario,email,senha) VALUES (1,'A','a@example.com','x')"
            ))
            connection.execute(text(
                "INSERT INTO notification_preferences (usuario_id,preference_key,enabled) "
                "VALUES (1,'card_limit',0)"
            ))
            connection.commit()

            command.upgrade(config, "head")
            command.check(config)
            inspector = inspect(connection)
            self.assertIn("financial_alert_states", inspector.get_table_names())
            self.assertTrue(any(
                item["name"] == "ix_financial_alert_states_user_kind_period"
                for item in inspector.get_indexes("financial_alert_states")
            ))
            connection.execute(text(
                "INSERT INTO notification_preferences (usuario_id,preference_key,enabled) "
                "VALUES (1,'budget_threshold',1),(1,'goal_progress',1)"
            ))
            connection.execute(text(
                "INSERT INTO financial_alert_states "
                "(usuario_id,source_kind,source_id,period_key,highest_milestone) "
                "VALUES (1,'budget',7,'2026-10',100)"
            ))
            connection.commit()

            command.downgrade(config, "d3e4f5a6b7c8")
            self.assertNotIn("financial_alert_states", inspect(connection).get_table_names())
            self.assertEqual(connection.execute(text(
                "SELECT enabled FROM notification_preferences "
                "WHERE usuario_id=1 AND preference_key='card_limit'"
            )).scalar_one(), 0)
            command.upgrade(config, "head")
            self.assertEqual(
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one(),
                "e4f5a6b7c8d9",
            )


if __name__ == "__main__":
    unittest.main()
