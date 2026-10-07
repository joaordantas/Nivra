import unittest
from fastapi.testclient import TestClient
from tests.auth_support import authenticate_existing_user
from tests.db_support import remove_test_database, reset_test_database
from backend.main import app
from database.connection import get_connection


class GoalApiTests(unittest.TestCase):
    def setUp(self):
        reset_test_database(); conn=get_connection(); conn.execute("INSERT INTO usuarios (id,usuario,email,senha) VALUES (1,'A','a@example.com','x')"); conn.execute("INSERT INTO usuarios (id,usuario,email,senha) VALUES (2,'B','b@example.com','x')"); conn.commit(); conn.close()
        self.client=TestClient(app); self.headers=authenticate_existing_user(self.client,1)
    def tearDown(self): self.client.close(); remove_test_database()
    def test_crud_movements_csrf_extra_and_exact_decimals(self):
        payload={"name":"Viagem","description":None,"target_amount":"1000.25","deadline":None}
        self.assertEqual(self.client.post("/api/goals",json=payload).status_code,403)
        created=self.client.post("/api/goals",headers=self.headers,json=payload); self.assertEqual(created.status_code,201,created.text); goal=created.json(); self.assertEqual(goal["target_amount"],"1000.25")
        extra=self.client.post("/api/goals",headers=self.headers,json={**payload,"user_id":2}); self.assertEqual(extra.status_code,422)
        movement=self.client.post(f"/api/goals/{goal['id']}/movements",headers=self.headers,json={"type":"contribution","amount":"100.10","effective_date":"2026-10-07","description":None,"idempotency_key":"api-test-key-1"}); self.assertEqual(movement.status_code,201,movement.text)
        self.assertEqual(len(self.client.get(f"/api/goals/{goal['id']}/movements").json()),1)
        self.assertEqual(self.client.patch(f"/api/goals/{goal['id']}",headers=self.headers,json={"target_amount":"90.00"}).status_code,200)
        self.assertEqual(self.client.delete(f"/api/goals/{goal['id']}",headers=self.headers).json()["outcome"],"archived")
    def test_idor_is_not_found(self):
        other=TestClient(app); headers=authenticate_existing_user(other,2); goal=other.post("/api/goals",headers=headers,json={"name":"B","target_amount":"10"}).json(); goal_id=goal["id"]
        self.assertEqual(self.client.get(f"/api/goals/{goal_id}").status_code,404); self.assertEqual(self.client.get(f"/api/goals/{goal_id}/movements").status_code,404)
        self.assertEqual(self.client.patch(f"/api/goals/{goal_id}",headers=self.headers,json={"name":"X"}).status_code,404); self.assertEqual(self.client.delete(f"/api/goals/{goal_id}",headers=self.headers).status_code,404)
        self.assertEqual(self.client.post(f"/api/goals/{goal_id}/movements",headers=self.headers,json={"type":"contribution","amount":"1","effective_date":"2026-10-07","idempotency_key":"foreign-key-1"}).status_code,404); other.close()


if __name__=="__main__": unittest.main()
