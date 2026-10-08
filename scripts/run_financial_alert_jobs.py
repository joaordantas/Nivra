"""Safe operational CLI for budget and goal alert reconciliation."""

from __future__ import annotations

import argparse
import json
from datetime import date

from services.financial_alert_job_service import financial_alert_job_runner
from services.periodic_summary_job_service import current_civil_date


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Run financial threshold alerts")
    command.add_argument("--reference", type=date.fromisoformat)
    command.add_argument("--batch-size", type=int, default=250)
    command.add_argument("--dry-run", action="store_true")
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = financial_alert_job_runner.run(
        reference=args.reference or current_civil_date(),
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.public_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 1 if result.status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
