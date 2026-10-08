import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import patch

from database.connection import get_connection
from repositories.financial_alert_state_repo import list_financial_alert_states
from services.financial_threshold_alert_service import financial_threshold_alert_service
from services.goal_service import (
    add_goal_movement_service,
    create_goal_service,
    update_goal_service,
)
from services.notification_preference_service import notification_preference_service
from services.notification_service import notification_service
from tests.db_support import remove_test_database, reset_test_database


REFERENCE = date(2026, 10, 7)


def budget_fact(source_id: int, percentage: str, period: str = "2026-10") -> dict:
    return {
        "id": source_id,
        "period": period,
        "category": {"id": source_id, "name": f"Categoria {source_id}", "system_key": None},
        "limit": "100.00",
        "spent": percentage,
        "remaining": "0.00",
        "usage_percentage": percentage,
        "created_at": "2026-10-01",
        "updated_at": "2026-10-01",
    }


def goal_fact(
    source_id: int,
    percentage: str,
    *,
    status: str = "active",
) -> dict:
    return {
        "id": source_id,
        "name": f"Meta {source_id}",
        "description": None,
        "target_amount": "100.00",
        "saved_amount": percentage,
        "remaining_amount": "0.00",
        "progress_percentage": percentage,
        "deadline": None,
        "lifecycle_status": status,
        "completed": float(percentage) >= 100,
        "created_at": "2026-10-01",
        "updated_at": "2026-10-01",
    }


class FinancialThresholdAlertTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        connection = get_connection()
        connection.execute(
            "INSERT INTO usuarios (id,usuario,email,senha) VALUES "
            "(1,'A','p77-a@example.com','x'),(2,'B','p77-b@example.com','x')"
        )
        connection.commit()
        connection.close()
        self.flag = patch.dict(os.environ, {"FINANCIAL_ALERTS_ENABLED": "true"})
        self.flag.start()

    def tearDown(self):
        self.flag.stop()
        remove_test_database()

    def evaluate(self, budgets=None, goals=None, *, user_id=1, baseline=False):
        with patch(
            "services.financial_threshold_alert_service.list_budgets_service",
            return_value=budgets or [],
        ), patch(
            "services.financial_threshold_alert_service.list_goals_service",
            return_value=goals or [],
        ):
            return financial_threshold_alert_service.evaluate_user(
                user_id, reference=REFERENCE, baseline_missing=baseline
            )

    def test_budget_threshold_boundaries_and_overspend_preserve_actual_percentage(self):
        cases = ((79, 0, None), (80, 1, "warning"), (99, 1, "warning"),
                 (100, 1, "critical"), (135, 1, "critical"))
        for source_id, (percentage, count, severity) in enumerate(cases, start=100):
            with self.subTest(percentage=percentage):
                self.evaluate([budget_fact(source_id, str(percentage))])
                items = [
                    item for item in notification_service.list(1, limit=100)
                    if item["metadados"].get("source_id") == str(source_id)
                ]
                self.assertEqual(len(items), count)
                if items:
                    self.assertEqual(items[0]["severidade"], severity)
                    self.assertIn(f"{percentage:.2f}%", items[0]["mensagem"])

    def test_budget_direct_jump_replay_regression_and_new_month(self):
        self.evaluate([budget_fact(200, "115")])
        self.evaluate([budget_fact(200, "115")])
        self.evaluate([budget_fact(200, "60")])
        self.evaluate([budget_fact(200, "85")])
        self.evaluate([budget_fact(200, "115", "2026-11")])
        items = notification_service.list(1, limit=100)
        self.assertEqual(len(items), 2)
        self.assertTrue(all(item["metadados"]["source_type"] == "budget_threshold_100" for item in items))
        self.assertEqual({item["metadados"]["route"] for item in items}, {"/budgets"})

    def test_goal_milestones_sequential_and_direct_completion(self):
        for percentage in (49, 50, 75, 100, 125):
            self.evaluate(goals=[goal_fact(300, str(percentage))])
        sequential = [
            item for item in notification_service.list(1, limit=100)
            if item["metadados"].get("source_id") == "300"
        ]
        self.assertEqual(
            {item["metadados"]["source_type"] for item in sequential},
            {"goal_progress_50", "goal_progress_75", "goal_progress_100"},
        )
        self.evaluate(goals=[goal_fact(301, "100")])
        direct = [
            item for item in notification_service.list(1, limit=100)
            if item["metadados"].get("source_id") == "301"
        ]
        self.assertEqual(len(direct), 1)
        self.assertEqual(direct[0]["metadados"]["source_type"], "goal_progress_100")

    def test_goal_withdrawal_and_target_change_never_repeat_old_milestones(self):
        for percentage in (75, 40, 50, 75, 100):
            self.evaluate(goals=[goal_fact(400, str(percentage))])
        items = [
            item["metadados"]["source_type"]
            for item in notification_service.list(1, limit=100)
            if item["metadados"].get("source_id") == "400"
        ]
        self.assertEqual(sorted(items), ["goal_progress_100", "goal_progress_75"])

    def test_future_contribution_is_ignored_by_canonical_goal_service_and_hook(self):
        goal = create_goal_service(1, "Reserva", None, "100", None, today=REFERENCE)
        add_goal_movement_service(
            1, goal["id"], "contribution", "100", "2026-10-08", None, "future", today=REFERENCE
        )
        self.assertEqual(notification_service.list(1), [])
        states = list_financial_alert_states(1, "goal")
        self.assertEqual(states[(goal["id"], "lifetime")], 0)

    def test_goal_archive_and_reactivation_baseline_without_historical_alert(self):
        goal = create_goal_service(1, "Viagem", None, "100", None, today=REFERENCE)
        add_goal_movement_service(
            1, goal["id"], "contribution", "40", "2026-10-07", None, "initial", today=REFERENCE
        )
        update_goal_service(goal["id"], 1, {"lifecycle_status": "archived"}, today=REFERENCE)
        update_goal_service(goal["id"], 1, {"target_amount": "40"}, today=REFERENCE)
        update_goal_service(goal["id"], 1, {"lifecycle_status": "active"}, today=REFERENCE)
        self.assertEqual(notification_service.list(1), [])
        self.assertEqual(
            list_financial_alert_states(1, "goal")[(goal["id"], "lifetime")], 100
        )

    def test_disabled_preferences_consume_milestone_and_reenable_is_not_retroactive(self):
        notification_preference_service.update(1, {
            "budget_threshold": False,
            "goal_progress": False,
        })
        self.evaluate([budget_fact(500, "100")], [goal_fact(501, "100")])
        notification_preference_service.update(1, {
            "budget_threshold": True,
            "goal_progress": True,
        })
        self.evaluate([budget_fact(500, "100")], [goal_fact(501, "100")])
        self.assertEqual(notification_service.list(1), [])

    def test_first_reconciliation_baselines_existing_sources_without_mass_alerts(self):
        result = self.evaluate(
            [budget_fact(600, "120")], [goal_fact(601, "100")], baseline=True
        )
        self.assertEqual(result.baselined, 2)
        self.assertEqual(notification_service.list(1), [])
        self.evaluate([budget_fact(600, "120")], [goal_fact(601, "100")])
        self.assertEqual(notification_service.list(1), [])

    def test_retry_concurrency_and_multiuser_are_persistent_and_isolated(self):
        with patch.object(notification_service, "notify", side_effect=RuntimeError("private")):
            failed = self.evaluate([budget_fact(700, "100")])
        self.assertEqual(failed.failed, 1)
        self.assertEqual(list_financial_alert_states(1, "budget"), {})

        workers = 8
        barrier = threading.Barrier(workers)

        def run(_index):
            barrier.wait(timeout=10)
            return self.evaluate([budget_fact(700, "100")])

        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(run, range(workers)))
        self.evaluate([budget_fact(700, "100")], user_id=2)
        self.assertEqual(len(notification_service.list(1)), 1)
        self.assertEqual(len(notification_service.list(2)), 1)

    def test_feature_flag_and_producers_do_not_change_financial_tables(self):
        connection = get_connection()
        try:
            before = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("transacoes", "contas", "budgets", "goals", "goal_movements")
            }
        finally:
            connection.close()
        with patch.dict(os.environ, {"FINANCIAL_ALERTS_ENABLED": "false"}):
            result = self.evaluate([budget_fact(800, "100")], [goal_fact(801, "100")])
        self.assertEqual(result.evaluated, 0)
        connection = get_connection()
        try:
            after = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in before
            }
        finally:
            connection.close()
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
