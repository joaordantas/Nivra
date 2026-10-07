from __future__ import annotations

import importlib
import logging
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from database.connection import get_connection
from repositories.periodic_summary_job_repo import claim_job_run, get_job_run
from services.periodic_summary_job_service import (
    JobKind,
    PeriodicSummaryJobRunner,
    periodic_summary_jobs_enabled,
)
from tests.db_support import remove_test_database, reset_test_database


FIXED_NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


class FakeSummaryService:
    def __init__(self, behavior=None):
        self.behavior = behavior or {}
        self.calls = []
        self.call_counts = {}

    def _call(self, kind, user_id, reference, period_start):
        self.calls.append((kind, user_id, reference, period_start))
        key = (kind, user_id)
        count = self.call_counts.get(key, 0)
        self.call_counts[key] = count + 1
        sequence = self.behavior.get(key, ["delivered_or_deduplicated"])
        value = sequence[min(count, len(sequence) - 1)]
        if isinstance(value, Exception):
            raise value
        if isinstance(value, tuple):
            outcome, retryable, error_code = value
        else:
            outcome, retryable, error_code = value, False, None
        return SimpleNamespace(outcome=outcome, retryable=retryable, error_code=error_code)

    def generate_weekly_summary(self, user_id, *, reference, period_start=None):
        return self._call("weekly", user_id, reference, period_start)

    def generate_monthly_summary(self, user_id, *, reference, period_start=None):
        return self._call("monthly", user_id, reference, period_start)


class PeriodicSummaryJobRunnerTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()

    def tearDown(self):
        remove_test_database()

    def add_users(self, count):
        connection = get_connection()
        try:
            for index in range(1, count + 1):
                connection.execute(
                    "INSERT INTO usuarios (id, usuario, email, senha) VALUES (?, ?, ?, ?)",
                    (index, f"Fictício {index}", f"fake-{index}@example.invalid", "hash"),
                )
            connection.commit()
        finally:
            connection.close()

    def runner(self, service, now=FIXED_NOW):
        return PeriodicSummaryJobRunner(
            summary_service=service,
            utc_now=lambda: now,
            sleeper=lambda _seconds: None,
        )

    def test_weekly_monthly_periods_and_year_boundaries_are_explicit(self):
        self.add_users(1)
        service = FakeSummaryService()
        results = self.runner(service).run_all(reference=date(2026, 1, 5), batch_size=1)
        self.assertEqual(
            [(item.job_type, item.period_start, item.period_end) for item in results],
            [
                ("weekly", "2025-12-29", "2026-01-04"),
                ("monthly", "2025-12-01", "2025-12-31"),
            ],
        )
        self.assertEqual({call[2] for call in service.calls}, {date(2026, 1, 5)})
        self.assertEqual({call[3] for call in service.calls}, {date(2025, 12, 29), date(2025, 12, 1)})

    def test_success_suppression_and_no_activity_are_normal_results(self):
        self.add_users(3)
        service = FakeSummaryService({
            ("weekly", 1): ["delivered_or_deduplicated"],
            ("weekly", 2): ["suppressed"],
            ("weekly", 3): ["no_activity"],
        })
        result = self.runner(service).run(JobKind.WEEKLY, reference=date(2026, 10, 7), batch_size=2)
        self.assertEqual(result.status, "success")
        self.assertEqual(
            (result.counters.processed, result.counters.success, result.counters.suppressed, result.counters.skipped),
            (3, 1, 1, 1),
        )

    def test_partial_failure_does_not_stop_other_users(self):
        self.add_users(3)
        service = FakeSummaryService({
            ("weekly", 2): [("failed", False, "summary_generation_failed")],
        })
        result = self.runner(service).run(JobKind.WEEKLY, reference=date(2026, 10, 7), batch_size=3)
        self.assertEqual(result.status, "partial_success")
        self.assertEqual((result.counters.success, result.counters.failed), (2, 1))
        self.assertEqual([call[1] for call in service.calls], [1, 2, 3])

    def test_all_users_failing_marks_job_failed(self):
        self.add_users(2)
        service = FakeSummaryService({
            ("monthly", 1): [("failed", False, "summary_generation_failed")],
            ("monthly", 2): [("failed", False, "summary_generation_failed")],
        })
        result = self.runner(service).run(JobKind.MONTHLY, reference=date(2026, 10, 7))
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.counters.failed, 2)

    def test_no_users_is_success(self):
        result = self.runner(FakeSummaryService()).run(
            JobKind.WEEKLY, reference=date(2026, 10, 7)
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(result.counters.processed, 0)

    def test_keyset_pagination_covers_three_batches_and_incomplete_last_batch(self):
        self.add_users(8)
        service = FakeSummaryService()
        result = self.runner(service).run(
            JobKind.WEEKLY, reference=date(2026, 10, 7), batch_size=3
        )
        self.assertEqual([call[1] for call in service.calls], list(range(1, 9)))
        self.assertEqual(result.counters.processed, 8)

    def test_replay_uses_tracking_and_does_not_call_service_twice(self):
        self.add_users(2)
        service = FakeSummaryService()
        runner = self.runner(service)
        first = runner.run(JobKind.WEEKLY, reference=date(2026, 10, 7))
        replay = runner.run(JobKind.WEEKLY, reference=date(2026, 10, 8))
        self.assertEqual(first.status, "success")
        self.assertEqual(replay.reason, "already_completed")
        self.assertEqual(len(service.calls), 2)

    def test_transient_failure_retries_twice_then_succeeds(self):
        self.add_users(1)
        service = FakeSummaryService({
            ("weekly", 1): [
                ("failed", True, "database_unavailable"),
                ("failed", True, "database_unavailable"),
                "delivered_or_deduplicated",
            ],
        })
        result = self.runner(service).run(JobKind.WEEKLY, reference=date(2026, 10, 7))
        self.assertEqual(result.status, "success")
        self.assertEqual(result.counters.retries, 2)
        self.assertEqual(service.call_counts[("weekly", 1)], 3)

    def test_permanent_failure_has_no_retry_and_transient_attempts_are_limited(self):
        self.add_users(2)
        service = FakeSummaryService({
            ("weekly", 1): [("failed", False, "unexpected_error")],
            ("weekly", 2): [("failed", True, "database_unavailable")],
        })
        result = self.runner(service).run(JobKind.WEEKLY, reference=date(2026, 10, 7))
        self.assertEqual(result.status, "failed")
        self.assertEqual(service.call_counts[("weekly", 1)], 1)
        self.assertEqual(service.call_counts[("weekly", 2)], 3)
        self.assertEqual(result.counters.retries, 2)

    def test_partial_run_can_be_recovered_without_blocking_completed_users(self):
        self.add_users(3)
        first_service = FakeSummaryService({
            ("weekly", 2): [("failed", False, "summary_generation_failed")],
        })
        first = self.runner(first_service).run(JobKind.WEEKLY, reference=date(2026, 10, 7))
        second_service = FakeSummaryService()
        second = self.runner(second_service).run(JobKind.WEEKLY, reference=date(2026, 10, 7))
        tracked = get_job_run("weekly", date(2026, 9, 28))
        self.assertEqual((first.status, second.status), ("partial_success", "success"))
        self.assertEqual(tracked["attempt"], 2)
        self.assertEqual(tracked["status"], "success")
        self.assertEqual([call[1] for call in second_service.calls], [1, 2, 3])

    def test_distributed_claim_blocks_overlap_and_recovers_expired_lease(self):
        first = claim_job_run(
            job_type="weekly",
            period_start=date(2026, 9, 28),
            period_end=date(2026, 10, 4),
            reference_date=date(2026, 10, 7),
            now=FIXED_NOW,
            lease_seconds=60,
            max_attempts=4,
        )
        concurrent = claim_job_run(
            job_type="weekly",
            period_start=date(2026, 9, 28),
            period_end=date(2026, 10, 4),
            reference_date=date(2026, 10, 7),
            now=FIXED_NOW,
            lease_seconds=60,
            max_attempts=4,
        )
        recovered = claim_job_run(
            job_type="weekly",
            period_start=date(2026, 9, 28),
            period_end=date(2026, 10, 4),
            reference_date=date(2026, 10, 7),
            now=FIXED_NOW + timedelta(seconds=61),
            lease_seconds=60,
            max_attempts=4,
        )
        self.assertTrue(first.acquired)
        self.assertEqual(concurrent.reason, "lock_conflict")
        self.assertTrue(recovered.acquired)
        self.assertEqual(recovered.attempt, 2)

    def test_job_attempts_are_bounded_after_repeated_recovery(self):
        now = FIXED_NOW
        claim = None
        for attempt in range(1, 5):
            claim = claim_job_run(
                job_type="weekly",
                period_start=date(2026, 9, 28),
                period_end=date(2026, 10, 4),
                reference_date=date(2026, 10, 7),
                now=now,
                lease_seconds=1,
                max_attempts=4,
            )
            self.assertTrue(claim.acquired)
            self.assertEqual(claim.attempt, attempt)
            now += timedelta(seconds=2)
        blocked = claim_job_run(
            job_type="weekly",
            period_start=date(2026, 9, 28),
            period_end=date(2026, 10, 4),
            reference_date=date(2026, 10, 7),
            now=now,
            lease_seconds=1,
            max_attempts=4,
        )
        self.assertFalse(blocked.acquired)
        self.assertEqual(blocked.reason, "attempt_limit")
        self.assertEqual(blocked.attempt, 4)

    def test_eight_concurrent_runners_have_one_logical_owner(self):
        self.add_users(1)
        barrier = threading.Barrier(8)

        def invoke(_index):
            barrier.wait(timeout=10)
            return self.runner(FakeSummaryService()).run(
                JobKind.WEEKLY, reference=date(2026, 10, 7)
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(invoke, range(8)))
        self.assertEqual(sum(item.counters.processed for item in results), 1)
        self.assertEqual(get_job_run("weekly", date(2026, 9, 28))["status"], "success")

    def test_weekly_and_monthly_do_not_collide(self):
        self.add_users(1)
        service = FakeSummaryService()
        results = self.runner(service).run_all(reference=date(2026, 10, 7))
        self.assertEqual([item.status for item in results], ["success", "success"])
        self.assertEqual({call[0] for call in service.calls}, {"weekly", "monthly"})

    def test_dry_run_counts_without_tracking_or_service_calls(self):
        self.add_users(4)
        service = FakeSummaryService()
        result = self.runner(service).run(
            JobKind.WEEKLY, reference=date(2026, 10, 7), dry_run=True
        )
        self.assertEqual(result.status, "dry_run")
        self.assertEqual(result.counters.skipped, 4)
        self.assertIsNone(get_job_run("weekly", date(2026, 9, 28)))
        self.assertEqual(service.calls, [])

    def test_logs_are_structured_and_contain_no_pii_or_financial_values(self):
        self.add_users(1)
        service = FakeSummaryService({
            ("weekly", 1): [("failed", False, "summary_generation_failed")],
        })
        with self.assertLogs("nivra.periodic_summary_jobs", level=logging.INFO) as captured:
            self.runner(service).run(JobKind.WEEKLY, reference=date(2026, 10, 7))
        joined = " ".join(captured.output)
        self.assertIn("summary_generation_failed", joined)
        self.assertNotIn("fake-1", joined)
        self.assertNotIn("Fictício", joined)
        self.assertNotIn("R$", joined)


class PeriodicSummaryJobConfigurationTests(unittest.TestCase):
    def test_feature_flag_is_closed_unless_explicitly_true(self):
        for value, expected in ((None, False), ("false", False), ("invalid", False), ("TRUE", True)):
            environment = {} if value is None else {"PERIODIC_SUMMARY_JOBS_ENABLED": value}
            with self.subTest(value=value), patch.dict(os.environ, environment, clear=True):
                self.assertEqual(periodic_summary_jobs_enabled(), expected)

    def test_import_does_not_run_jobs(self):
        import services.periodic_summary_job_service as module

        with patch.object(module.PeriodicSummaryJobRunner, "run_all") as run_all:
            importlib.reload(module)
            run_all.assert_not_called()


if __name__ == "__main__":
    unittest.main()
