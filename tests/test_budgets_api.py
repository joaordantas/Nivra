import unittest

from fastapi.testclient import TestClient

from tests.auth_support import authenticate_existing_user
from tests.db_support import remove_test_database, reset_test_database

from backend.main import app
from database.connection import get_connection
from services.categoria_service import criar_categoria_service


class BudgetApiTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        conn = get_connection()
        conn.execute("INSERT INTO usuarios (id,usuario,email,senha) VALUES (1,'A','a@example.com','x')")
        conn.execute("INSERT INTO usuarios (id,usuario,email,senha) VALUES (2,'B','b@example.com','x')")
        conn.commit()
        conn.close()
        self.category = criar_categoria_service("Alimentação", 1)
        self.other_category = criar_categoria_service("Alimentação", 2)
        self.client = TestClient(app)
        self.headers = authenticate_existing_user(self.client, 1)

    def tearDown(self):
        self.client.close()
        remove_test_database()

    def test_crud_contract_and_extra_payload_rejected(self):
        created = self.client.post("/api/budgets", headers=self.headers, json={"category_id": self.category["id"], "period": "2026-10", "limit": "800.25"})
        self.assertEqual(created.status_code, 201, created.text)
        body = created.json()
        self.assertEqual(body["limit"], "800.25")
        self.assertEqual(self.client.get("/api/budgets?period=2026-10").json()[0]["id"], body["id"])
        self.assertEqual(self.client.get(f"/api/budgets/{body['id']}").status_code, 200)
        updated = self.client.patch(f"/api/budgets/{body['id']}", headers=self.headers, json={"limit": "900.00"})
        self.assertEqual(updated.json()["limit"], "900.00")
        invalid = self.client.post("/api/budgets", headers=self.headers, json={"category_id": self.category["id"], "period": "2026-11", "limit": "10", "user_id": 2})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(self.client.delete(f"/api/budgets/{body['id']}", headers=self.headers).status_code, 204)

    def test_csrf_duplicate_invalid_period_and_foreign_category(self):
        payload = {"category_id": self.category["id"], "period": "2026-10", "limit": "100"}
        self.assertEqual(self.client.post("/api/budgets", json=payload).status_code, 403)
        self.assertEqual(self.client.post("/api/budgets", headers=self.headers, json=payload).status_code, 201)
        self.assertEqual(self.client.post("/api/budgets", headers=self.headers, json=payload).status_code, 409)
        foreign = {**payload, "category_id": self.other_category["id"], "period": "2026-11"}
        self.assertEqual(self.client.post("/api/budgets", headers=self.headers, json=foreign).status_code, 400)
        self.assertEqual(self.client.get("/api/budgets?period=outubro").status_code, 422)

    def test_idor_returns_not_found(self):
        other = TestClient(app)
        other_headers = authenticate_existing_user(other, 2)
        response = other.post("/api/budgets", headers=other_headers, json={"category_id": self.other_category["id"], "period": "2026-10", "limit": "300"})
        budget_id = response.json()["id"]
        self.assertEqual(self.client.get(f"/api/budgets/{budget_id}").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/budgets/{budget_id}", headers=self.headers, json={"limit": "1"}).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/budgets/{budget_id}", headers=self.headers).status_code, 404)
        other.close()


if __name__ == "__main__":
    unittest.main()
