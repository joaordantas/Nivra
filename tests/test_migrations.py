import unittest
from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, text

from database.migrations import get_alembic_config


class MigrationConnectionTests(unittest.TestCase):
    def setUp(self):
        self.database = Path(__file__).resolve().parents[1] / "storage" / "test_injected_migration.db"
        self.database.unlink(missing_ok=True)

    def tearDown(self):
        self.database.unlink(missing_ok=True)

    def test_upgrade_accepts_prevalidated_connection(self):
        engine = create_engine(f"sqlite+pysqlite:///{self.database.as_posix()}", future=True)
        try:
            with engine.connect() as connection:
                config = get_alembic_config()
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                self.assertEqual(revision, "d7e8f9a012b3")
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
