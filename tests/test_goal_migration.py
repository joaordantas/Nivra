import unittest
from pathlib import Path
from alembic import command
from sqlalchemy import create_engine, inspect, text
from database.migrations import get_alembic_config


class GoalMigrationTests(unittest.TestCase):
    def setUp(self): self.path=Path(__file__).resolve().parents[1]/"storage"/"test_goal_migration.db"; self.path.unlink(missing_ok=True); self.engine=create_engine(f"sqlite+pysqlite:///{self.path.as_posix()}",future=True)
    def tearDown(self): self.engine.dispose(); self.path.unlink(missing_ok=True)
    def test_upgrade_constraints_indexes_downgrade_reupgrade_preserve_budgets(self):
        with self.engine.connect() as connection:
            config=get_alembic_config(); config.attributes["connection"]=connection; command.upgrade(config,"c2d3e4f5a6b7")
            connection.execute(text("INSERT INTO usuarios (id,usuario,email,senha) VALUES (1,'A','a@example.com','x')")); connection.execute(text("INSERT INTO categorias (id,nome,usuario_id) VALUES (2,'Cat',1)")); connection.execute(text("INSERT INTO budgets (id,usuario_id,categoria_id,periodo,limite) VALUES (3,1,2,'2026-10-01',10)")); connection.commit()
            command.upgrade(config,"head"); command.check(config); inspector=inspect(connection); self.assertIn("goals",inspector.get_table_names()); self.assertIn("goal_movements",inspector.get_table_names()); self.assertTrue(any(i["name"]=="ix_goal_movements_goal_effective" for i in inspector.get_indexes("goal_movements")))
            command.downgrade(config,"c2d3e4f5a6b7"); self.assertEqual(connection.execute(text("SELECT COUNT(*) FROM budgets")).scalar_one(),1); command.upgrade(config,"head"); self.assertEqual(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one(),"d3e4f5a6b7c8")


if __name__=="__main__": unittest.main()
