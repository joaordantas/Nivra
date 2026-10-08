import io
import unittest
from contextlib import redirect_stdout
from datetime import date
from unittest.mock import patch

from scripts.run_financial_alert_jobs import main
from services.periodic_summary_job_service import JobCounters, JobRunResult


def result(status="success"):
    return JobRunResult(
        job_type="financial_alerts",
        period_start="2026-10-07",
        period_end="2026-10-07",
        status=status,
        reason="completed",
        attempt=1,
        counters=JobCounters(processed=2, success=2),
        duration_ms=3,
    )


class FinancialAlertCliTests(unittest.TestCase):
    def test_arguments_output_and_exit_codes(self):
        with patch(
            "scripts.run_financial_alert_jobs.financial_alert_job_runner.run",
            return_value=result(),
        ) as run, redirect_stdout(io.StringIO()) as output:
            code = main(["--reference", "2026-10-07", "--batch-size", "10"])
        self.assertEqual(code, 0)
        run.assert_called_once_with(
            reference=date(2026, 10, 7), batch_size=10, dry_run=False
        )
        self.assertNotIn("R$", output.getvalue())

        with patch(
            "scripts.run_financial_alert_jobs.financial_alert_job_runner.run",
            return_value=result("failed"),
        ), redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--reference", "2026-10-07"]), 1)


if __name__ == "__main__":
    unittest.main()
