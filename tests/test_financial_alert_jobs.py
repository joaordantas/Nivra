import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from database.connection import get_connection
from repositories.periodic_summary_job_repo import get_job_run
from services.financial_alert_job_service import FinancialAlertJobRunner
from tests.db_support import remove_test_database, reset_test_database


NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


class FakeAlertService:
    def __init__(self, outcomes=None):
        self.outcomes = outcomes or {}
        self.calls = []
        self.counts = {}

    def evaluate_user(self, user_id, *, reference, baseline_missing):
        self.calls.append((user_id, reference, baseline_missing))
        count = self.counts.get(user_id, 0)
        self.counts[user_id] = count + 1
        sequence = self.outcomes.get(user_id, ["success"])
        outcome = sequence[min(count, len(sequence) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(
            failed=1 if outcome == "failed" else 0,
            delivered_or_deduplicated=1 if outcome == "success" else 0,
            suppressed=1 if outcome == "suppressed" else 0,
            generated=1 if outcome == "success" else 0,
            deduplicated=0,
        )


class FinancialAlertJobTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        connection = get_connection()
        for user_id in range(1, 6):
            connection.execute(
                "INSERT INTO usuarios (id,usuario,email,senha) VALUES (?,?,?,?)",
                (user_id, f"User {user_id}", f"p77-{user_id}@example.com", "x"),
            )
        connection.commit()
        connection.close()

    def tearDown(self):
        remove_test_database()

    def runner(self, service):
        return FinancialAlertJobRunner(
            alert_service=service,
            utc_now=lambda: NOW,
            sleeper=lambda _seconds: None,
        )

    def test_flag_off_and_dry_run_do_not_claim_or_process(self):
        service = FakeAlertService()
        with patch.dict(os.environ, {"FINANCIAL_ALERTS_ENABLED": "false"}):
            disabled = self.runner(service).run(reference=date(2026, 10, 7))
            dry = self.runner(service).run(reference=date(2026, 10, 7), dry_run=True)
        self.assertEqual((disabled.status, disabled.reason), ("skipped", "feature_flag_off"))
        self.assertEqual(dry.counters.skipped, 5)
        self.assertEqual(service.calls, [])
        self.assertIsNone(get_job_run("financial_alerts", date(2026, 10, 7)))

    def test_batches_partial_failure_and_isolation_continue_other_users(self):
        service = FakeAlertService({2: ["suppressed"], 3: ["failed"], 4: ["skipped"]})
        with patch.dict(os.environ, {"FINANCIAL_ALERTS_ENABLED": "true"}):
            result = self.runner(service).run(reference=date(2026, 10, 7), batch_size=2)
        self.assertEqual(result.status, "partial_success")
        self.assertEqual([call[0] for call in service.calls], [1, 2, 3, 4, 5])
        self.assertEqual(
            (result.counters.success, result.counters.suppressed, result.counters.skipped, result.counters.failed),
            (2, 1, 1, 1),
        )
        tracked = get_job_run("financial_alerts", date(2026, 10, 7))
        self.assertEqual((tracked["generated_count"], tracked["deduplicated_count"]), (2, 0))
        self.assertGreaterEqual(tracked["duration_ms"], 0)

    def test_transient_exception_retries_and_daily_replay_is_idempotent(self):
        service = FakeAlertService({1: [TimeoutError(), "success"]})
        with patch.dict(os.environ, {"FINANCIAL_ALERTS_ENABLED": "true"}):
            first = self.runner(service).run(reference=date(2026, 10, 7))
            replay = self.runner(service).run(reference=date(2026, 10, 7))
        self.assertEqual(first.status, "success")
        self.assertEqual(first.counters.retries, 1)
        self.assertEqual(replay.reason, "already_completed")

    def test_eight_concurrent_runners_have_one_owner(self):
        barrier = threading.Barrier(8)

        def invoke(_index):
            barrier.wait(timeout=10)
            return self.runner(FakeAlertService()).run(reference=date(2026, 10, 7))

        with patch.dict(os.environ, {"FINANCIAL_ALERTS_ENABLED": "true"}), \
             ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(invoke, range(8)))
        self.assertEqual(sum(item.counters.processed for item in results), 5)
        self.assertEqual(get_job_run("financial_alerts", date(2026, 10, 7))["status"], "success")


if __name__ == "__main__":
    unittest.main()
