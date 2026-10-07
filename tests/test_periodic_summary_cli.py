import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import date
from unittest.mock import patch

from scripts.run_periodic_summary_jobs import main
from services.periodic_summary_job_service import JobCounters, JobRunResult


def fake_result(status="success"):
    return JobRunResult(
        job_type="weekly",
        period_start="2026-09-28",
        period_end="2026-10-04",
        status=status,
        reason="completed",
        attempt=1,
        counters=JobCounters(processed=3, success=3),
        duration_ms=4,
    )


class PeriodicSummaryCliTests(unittest.TestCase):
    def test_execute_requires_feature_flag(self):
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--kind", "weekly", "--reference", "2026-10-07"]), 2)

    def test_valid_execution_and_exit_codes(self):
        environment = {"PERIODIC_SUMMARY_JOBS_ENABLED": "true"}
        with patch.dict(os.environ, environment, clear=True), \
             patch("scripts.run_periodic_summary_jobs.periodic_summary_job_runner.run", return_value=fake_result()) as run, \
             redirect_stdout(io.StringIO()) as output:
            code = main(["--kind", "weekly", "--reference", "2026-10-07", "--batch-size", "3"])
        self.assertEqual(code, 0)
        run.assert_called_once_with(
            "weekly", reference=date(2026, 10, 7), batch_size=3, dry_run=False
        )
        self.assertNotIn("R$", output.getvalue())

        with patch.dict(os.environ, environment, clear=True), \
             patch("scripts.run_periodic_summary_jobs.periodic_summary_job_runner.run", return_value=fake_result("failed")), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--kind", "weekly", "--reference", "2026-10-07"]), 1)

    def test_dry_run_is_available_with_flag_off(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch("scripts.run_periodic_summary_jobs.periodic_summary_job_runner.run", return_value=fake_result("dry_run")) as run, \
             redirect_stdout(io.StringIO()):
            code = main(["--kind", "weekly", "--reference", "2026-10-07", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertTrue(run.call_args.kwargs["dry_run"])

    def test_invalid_arguments_exit_with_code_two(self):
        with self.assertRaises(SystemExit) as raised, redirect_stdout(io.StringIO()):
            main(["--kind", "yearly"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
