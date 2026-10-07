"""Safe operational CLI for periodic financial summary jobs."""

from __future__ import annotations

import argparse
import json
from datetime import date

from services.periodic_summary_job_service import (
    JobKind,
    current_civil_date,
    periodic_summary_job_runner,
    periodic_summary_jobs_enabled,
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Run periodic financial summary jobs")
    command.add_argument("--kind", choices=("all", "weekly", "monthly"), default="all")
    command.add_argument("--reference", type=date.fromisoformat)
    command.add_argument("--batch-size", type=int)
    command.add_argument("--dry-run", action="store_true")
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.dry_run and not periodic_summary_jobs_enabled():
        print(json.dumps({"status": "disabled", "reason": "feature_flag_off"}))
        return 2
    reference = args.reference or current_civil_date()
    if args.kind == "all":
        results = periodic_summary_job_runner.run_all(
            reference=reference,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
    else:
        results = [periodic_summary_job_runner.run(
            JobKind(args.kind),
            reference=reference,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )]
    payload = {"status": "completed", "results": [result.public_dict() for result in results]}
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 1 if any(result.status == "failed" or result.reason == "attempt_limit" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
