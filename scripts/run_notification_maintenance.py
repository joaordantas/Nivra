"""Safe operational CLI for notification retention and job status."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime

from repositories.periodic_summary_job_repo import list_latest_job_runs
from services.notification_maintenance_service import notification_maintenance_runner
from services.periodic_summary_job_service import current_civil_date


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Inspect or clean notification operations")
    subcommands = command.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status")
    cleanup = subcommands.add_parser("cleanup")
    cleanup.add_argument("--reference", type=date.fromisoformat)
    cleanup.add_argument("--read-days", type=int)
    cleanup.add_argument("--job-days", type=int)
    cleanup.add_argument("--batch-size", type=int)
    cleanup.add_argument("--dry-run", action="store_true")
    return command


def _json_value(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "status":
        print(json.dumps(
            {"status": "ok", "latest_runs": list_latest_job_runs()},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=_json_value,
        ))
        return 0
    result = notification_maintenance_runner.run(
        reference=args.reference or current_civil_date(),
        read_days=args.read_days,
        job_days=args.job_days,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.public_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 1 if result.status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
