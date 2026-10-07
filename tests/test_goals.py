import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

from tests.db_support import remove_test_database, reset_test_database
from database.connection import get_connection
from services.conta_service import criar_conta_service, listar_contas_formatadas
from services.goal_service import GoalConflictError, add_goal_movement_service, create_goal_service, delete_goal_service, get_goal_service, list_goal_movements_service, list_goals_service, update_goal_service


TODAY = date(2026, 10, 7)


class GoalDomainTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        conn=get_connection(); conn.execute("INSERT INTO usuarios (id,usuario,email,senha) VALUES (1,'A','a@example.com','x')"); conn.execute("INSERT INTO usuarios (id,usuario,email,senha) VALUES (2,'B','b@example.com','x')"); conn.commit(); conn.close()
        self.account = criar_conta_service("Conta", "digital", 1000, 1)

    def tearDown(self): remove_test_database()

    def goal(self, target="1000.00", deadline=None, user=1):
        return create_goal_service(user, "Reserva", "Reserva lógica", target, deadline, today=TODAY)

    def move(self, goal_id, kind, amount, day="2026-10-07", key=None, user=1):
        return add_goal_movement_service(user, goal_id, kind, amount, day, None, key, today=TODAY)

    def test_create_decimal_optional_deadline_and_list(self):
        goal=self.goal("1000.25", "2027-02-28")
        self.assertEqual(goal["target_amount"], Decimal("1000.25")); self.assertEqual(goal["saved_amount"], Decimal("0.00")); self.assertEqual(goal["deadline"], "2027-02-28")
        self.assertEqual(list_goals_service(1, today=TODAY)[0]["id"], goal["id"])

    def test_contribution_withdrawal_completion_reopen_and_overfund(self):
        goal=self.goal("100")
        self.move(goal["id"], "contribution", "150.01")
        state=get_goal_service(goal["id"],1,today=TODAY); self.assertTrue(state["completed"]); self.assertEqual(state["progress_percentage"],Decimal("150.01")); self.assertEqual(state["remaining_amount"],Decimal("0.00"))
        self.move(goal["id"], "withdrawal", "60.01")
        state=get_goal_service(goal["id"],1,today=TODAY); self.assertFalse(state["completed"]); self.assertEqual(state["saved_amount"],Decimal("90.00"))

    def test_future_movement_not_effective_and_history_preserved(self):
        goal=self.goal(); self.move(goal["id"],"contribution","200","2026-10-08")
        self.assertEqual(get_goal_service(goal["id"],1,today=TODAY)["saved_amount"],Decimal("0.00"))
        history=list_goal_movements_service(goal["id"],1,today=TODAY); self.assertFalse(history[0]["effective"])
        self.assertEqual(delete_goal_service(goal["id"],1),"archived"); self.assertEqual(len(list_goal_movements_service(goal["id"],1,today=TODAY)),1)

    def test_empty_goal_is_deleted_but_history_goal_archived(self):
        empty=self.goal(); self.assertEqual(delete_goal_service(empty["id"],1),"deleted")
        historical=self.goal(); self.move(historical["id"],"contribution","1"); self.assertEqual(delete_goal_service(historical["id"],1),"archived")
        with self.assertRaises(GoalConflictError): self.move(historical["id"],"contribution","1")

    def test_target_update_recalculates_without_editing_saved_amount(self):
        goal=self.goal("100"); self.move(goal["id"],"contribution","50")
        updated=update_goal_service(goal["id"],1,{"target_amount":"40.00","name":"Nova reserva"},today=TODAY)
        self.assertEqual(updated["saved_amount"],Decimal("50.00")); self.assertEqual(updated["progress_percentage"],Decimal("125.00")); self.assertTrue(updated["completed"])

    def test_invalid_values_excess_withdrawal_and_chronological_invariant(self):
        for value in ("0","-1","NaN","Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError): self.goal(value)
        goal=self.goal(); self.move(goal["id"],"contribution","50","2026-10-05")
        with self.assertRaises(GoalConflictError): self.move(goal["id"],"withdrawal","50.01","2026-10-05")
        self.move(goal["id"],"withdrawal","40","2026-10-07")
        with self.assertRaises(GoalConflictError): self.move(goal["id"],"withdrawal","20","2026-10-06")

    def test_idempotency_replays_same_movement_and_rejects_reuse(self):
        goal=self.goal(); first=self.move(goal["id"],"contribution","10",key="12345678-key")
        replay=self.move(goal["id"],"contribution","10",key="12345678-key"); self.assertEqual(first["id"],replay["id"])
        with self.assertRaises(GoalConflictError): self.move(goal["id"],"contribution","11",key="12345678-key")

    def test_multiuser_isolation_and_no_bank_balance_effect(self):
        goal=self.goal(); other=self.goal(user=2)
        before=listar_contas_formatadas(1)[0]["saldo_atual"]; self.move(goal["id"],"contribution","300")
        self.assertEqual(listar_contas_formatadas(1)[0]["saldo_atual"],before)
        with self.assertRaises(LookupError): get_goal_service(other["id"],1,today=TODAY)
        with self.assertRaises(LookupError): self.move(other["id"],"contribution","1",user=1)

    def test_concurrent_withdrawals_cannot_make_negative(self):
        goal=self.goal(); self.move(goal["id"],"contribution","100"); barrier=threading.Barrier(2)
        def withdraw(_):
            barrier.wait(timeout=10)
            try: self.move(goal["id"],"withdrawal","80"); return "ok"
            except GoalConflictError: return "conflict"
        with ThreadPoolExecutor(max_workers=2) as executor: outcomes=list(executor.map(withdraw,range(2)))
        self.assertEqual(sorted(outcomes),["conflict","ok"]); self.assertEqual(get_goal_service(goal["id"],1,today=TODAY)["saved_amount"],Decimal("20.00"))


if __name__=="__main__": unittest.main()
