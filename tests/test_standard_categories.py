import unittest

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.main import app
from database.connection import dispose_engine, get_connection
from database.migrations import get_alembic_config, upgrade_database
from services.categoria_service import criar_categoria_service, renomear_categoria_service
from tests.auth_support import csrf_headers, register_client
from tests.db_support import remove_test_database, reset_test_database
from utils.categorias_padrao import (
    DEFAULT_CATEGORIES,
    is_provider_neutral_movement,
    map_provider_category,
)


class StandardCategoryTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_test_database()
        self.client_a = TestClient(app)
        self.client_b = TestClient(app)

    def tearDown(self) -> None:
        self.client_a.close()
        self.client_b.close()
        remove_test_database()

    def test_new_users_receive_their_own_standard_categories(self) -> None:
        user_a = register_client(self.client_a, "Categorias A", "categorias-a@example.com")
        user_b = register_client(self.client_b, "Categorias B", "categorias-b@example.com")

        categories_a = self.client_a.get("/api/categories").json()
        categories_b = self.client_b.get("/api/categories").json()

        self.assertEqual(len(categories_a), len(DEFAULT_CATEGORIES))
        self.assertEqual(len(categories_b), len(DEFAULT_CATEGORIES))
        self.assertTrue(all(category["padrao"] for category in categories_a))
        self.assertTrue(all(category["padrao"] for category in categories_b))
        self.assertNotEqual({category["id"] for category in categories_a}, {category["id"] for category in categories_b})

        conn = get_connection()
        try:
            keys_a = conn.execute(
                "SELECT chave_sistema FROM categorias WHERE usuario_id = ? ORDER BY chave_sistema",
                (user_a["id"],),
            ).fetchall()
            keys_b = conn.execute(
                "SELECT chave_sistema FROM categorias WHERE usuario_id = ? ORDER BY chave_sistema",
                (user_b["id"],),
            ).fetchall()
        finally:
            conn.close()
        expected_keys = sorted(key for key, _ in DEFAULT_CATEGORIES)
        self.assertEqual([row[0] for row in keys_a], expected_keys)
        self.assertEqual([row[0] for row in keys_b], expected_keys)

    def test_custom_categories_remain_deletable_and_standard_categories_do_not(self) -> None:
        register_client(self.client_a, "Categorias", "categorias@example.com")
        headers = csrf_headers(self.client_a)
        custom = self.client_a.post("/api/categories", headers=headers, json={"nome": "Projeto pessoal"})
        self.assertEqual(custom.status_code, 201, custom.text)
        self.assertFalse(custom.json()["padrao"])
        self.assertEqual(
            self.client_a.delete(f"/api/categories/{custom.json()['id']}", headers=headers).status_code,
            204,
        )

        standard = next(category for category in self.client_a.get("/api/categories").json() if category["nome"] == "Alimentação")
        blocked = self.client_a.delete(f"/api/categories/{standard['id']}", headers=headers)
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertIn("padrão", blocked.json()["detail"])

    def test_renaming_standard_category_preserves_system_key_and_key_is_unique_per_user(self) -> None:
        user = register_client(self.client_a, "Renomear", "renomear@example.com")
        categories = self.client_a.get("/api/categories").json()
        food = next(category for category in categories if category["nome"] == "Alimentação")

        renamed = renomear_categoria_service(food["id"], "Refeições", user["id"])
        self.assertTrue(renamed["padrao"])

        conn = get_connection()
        try:
            system_key = conn.execute(
                "SELECT chave_sistema FROM categorias WHERE id = ? AND usuario_id = ?",
                (food["id"], user["id"]),
            ).fetchone()
            with self.assertRaises(IntegrityError):
                conn.execute(
                    "INSERT INTO categorias (nome, usuario_id, chave_sistema) VALUES (?, ?, ?)",
                    ("Duplicada", user["id"], "food"),
                )
            conn.rollback()
        finally:
            conn.close()

        self.assertEqual(system_key[0], "food")

    def test_mapper_uses_provider_data_and_unknown_category_falls_back_to_other(self) -> None:
        self.assertEqual(map_provider_category("pluggy", 123, "Groceries"), "groceries")
        self.assertEqual(map_provider_category("pluggy", 123, "Food delivery"), "food")
        self.assertEqual(map_provider_category("pluggy", 123, "Transfer - PIX"), "transfers")
        self.assertEqual(map_provider_category("pluggy", 456, "Categoria desconhecida"), "other")
        self.assertEqual(map_provider_category("outro-provider", None, "Groceries"), "other")
        self.assertTrue(
            is_provider_neutral_movement(
                "pluggy", "05000000", "Same person transfer - PIX"
            )
        )
        self.assertTrue(
            is_provider_neutral_movement(
                "pluggy", None, "Credit card payment"
            )
        )
        self.assertFalse(
            is_provider_neutral_movement("pluggy", None, "Transfer - PIX")
        )


class StandardCategoryMigrationTests(unittest.TestCase):
    def tearDown(self) -> None:
        remove_test_database()

    def test_upgrade_seeds_existing_users_without_duplication(self) -> None:
        reset_test_database()
        dispose_engine()
        command.downgrade(get_alembic_config(), "e81f72c4a93b")

        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO usuarios (id, usuario, email, senha) VALUES (?, ?, ?, ?)",
                (101, "Usuario legado", "legado@example.com", "hash"),
            )
            conn.execute(
                "INSERT INTO categorias (nome, usuario_id) VALUES (?, ?)",
                ("Moradia", 101),
            )
            conn.commit()
        finally:
            conn.close()

        dispose_engine()
        upgrade_database()
        upgrade_database()

        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT nome, chave_sistema FROM categorias WHERE usuario_id = ? ORDER BY chave_sistema",
                (101,),
            ).fetchall()
        finally:
            conn.close()

        system_keys = [row[1] for row in rows if row[1] is not None]
        self.assertEqual(len(system_keys), len(DEFAULT_CATEGORIES))
        self.assertEqual(system_keys, sorted(key for key, _ in DEFAULT_CATEGORIES))
        self.assertIn(("Moradia", None), rows)


if __name__ == "__main__":
    unittest.main()
