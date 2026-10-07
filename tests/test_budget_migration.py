import unittest
from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, text

from database.migrations import get_alembic_config


class BudgetMigrationTests(unittest.TestCase):
    def setUp(self):
        self.database = Path(__file__).resolve().parents[1] / "storage" / "test_budget_migration.db"
        self.database.unlink(missing_ok=True)
        self.engine = create_engine(f"sqlite+pysqlite:///{self.database.as_posix()}", future=True)

    def tearDown(self):
        self.engine.dispose()
        self.database.unlink(missing_ok=True)

    def config(self, connection):
        config = get_alembic_config()
        config.attributes["connection"] = connection
        return config

    def test_valid_legacy_data_is_preserved_with_id_and_precision(self):
        with self.engine.connect() as connection:
            config = self.config(connection)
            command.upgrade(config, "b1c2d3e4f5a6")
            connection.execute(text("INSERT INTO usuarios (id,usuario,email,senha) VALUES (7,'Legado','legacy@example.com','x')"))
            connection.execute(text("INSERT INTO categorias (id,nome,usuario_id) VALUES (9,'Alimentação',7)"))
            connection.execute(text("INSERT INTO limites (id,categoria_id,valor,mes,usuario_id) VALUES (11,9,800.25,'2026-10',7)"))
            connection.commit()
            command.upgrade(config, "head")
            row = connection.execute(text("SELECT id,usuario_id,categoria_id,periodo,limite FROM budgets")).one()
            self.assertEqual((row.id, row.usuario_id, row.categoria_id), (11, 7, 9))
            self.assertEqual(str(row.periodo), "2026-10-01")
            self.assertEqual(str(row.limite), "800.25")
            self.assertIsNone(connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='limites'")).first())

    def test_invalid_period_and_cross_user_category_abort_migration(self):
        for month, owner in (("outubro", 1), ("2026-10", 2)):
            with self.subTest(month=month, owner=owner):
                self.engine.dispose()
                self.database.unlink(missing_ok=True)
                self.engine = create_engine(f"sqlite+pysqlite:///{self.database.as_posix()}", future=True)
                with self.engine.connect() as connection:
                    config = self.config(connection)
                    command.upgrade(config, "b1c2d3e4f5a6")
                    connection.execute(text("INSERT INTO usuarios (id,usuario,email,senha) VALUES (1,'A','a@example.com','x')"))
                    connection.execute(text("INSERT INTO usuarios (id,usuario,email,senha) VALUES (2,'B','b@example.com','x')"))
                    connection.execute(text("INSERT INTO categorias (id,nome,usuario_id) VALUES (3,'Cat',:owner)"), {"owner": owner})
                    connection.execute(text("INSERT INTO limites (id,categoria_id,valor,mes,usuario_id) VALUES (4,3,10,:month,1)"), {"month": month})
                    connection.commit()
                    with self.assertRaisesRegex(RuntimeError, "inválido"):
                        command.upgrade(config, "head")

    def test_downgrade_and_reupgrade_preserve_budget(self):
        with self.engine.connect() as connection:
            config = self.config(connection)
            command.upgrade(config, "head")
            connection.execute(text("INSERT INTO usuarios (id,usuario,email,senha) VALUES (1,'A','a@example.com','x')"))
            connection.execute(text("INSERT INTO categorias (id,nome,usuario_id) VALUES (2,'Cat',1)"))
            connection.execute(text("INSERT INTO budgets (id,usuario_id,categoria_id,periodo,limite) VALUES (3,1,2,'2026-10-01',12.34)"))
            connection.commit()
            command.downgrade(config, "b1c2d3e4f5a6")
            legacy = connection.execute(text("SELECT id,mes,valor FROM limites")).one()
            self.assertEqual((legacy.id, legacy.mes, str(legacy.valor)), (3, "2026-10", "12.34"))
            command.upgrade(config, "head")
            self.assertEqual(connection.execute(text("SELECT COUNT(*) FROM budgets")).scalar_one(), 1)


if __name__ == "__main__":
    unittest.main()
