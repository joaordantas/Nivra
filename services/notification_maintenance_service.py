from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, datetime, time as clock_time, timedelta, timezone
from typing import Callable

from sqlalchemy.exc import DBAPIError, OperationalError, TimeoutError as SqlAlchemyTimeoutError

from repositories.notification_maintenance_repo import (
    count_expired_job_runs,
    count_expired_read_notifications,
    delete_expired_job_runs,
    delete_expired_read_notifications,
)
from repositories.periodic_summary_job_repo import claim_job_run, finish_job_run, renew_job_lease
from services.periodic_summary_job_service import (
    LEASE_SECONDS,
    MAX_BATCH_SIZE,
    MAX_JOB_ATTEMPTS,
    MAX_USER_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    JobCounters,
    JobRunResult,
)


logger = logging.getLogger("nivra.notification_maintenance")
JOB_TYPE = "cleanup"
DEFAULT_BATCH_SIZE = 250


def notification_maintenance_enabled() -> bool:
    return os.environ.get("NOTIFICATION_MAINTENANCE_ENABLED", "").strip().casefold() == "true"


def _positive_days(name: str, override: int | None) -> int:
    raw = str(override) if override is not None else os.environ.get(name, "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} deve ser configurado explicitamente.") from exc
    if not 1 <= value <= 3_650:
        raise RuntimeError(f"{name} fora do limite seguro.")
    return value


def configured_retention(
    *,
    read_days: int | None = None,
    job_days: int | None = None,
    batch_size: int | None = None,
) -> tuple[int, int, int]:
    resolved_batch = batch_size
    if resolved_batch is None:
        raw = os.environ.get("NOTIFICATION_MAINTENANCE_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)).strip()
        try:
            resolved_batch = int(raw)
        except ValueError as exc:
            raise RuntimeError("NOTIFICATION_MAINTENANCE_BATCH_SIZE inválido.") from exc
    if not 1 <= resolved_batch <= MAX_BATCH_SIZE:
        raise RuntimeError("NOTIFICATION_MAINTENANCE_BATCH_SIZE fora do limite seguro.")
    return (
        _positive_days("NOTIFICATION_READ_RETENTION_DAYS", read_days),
        _positive_days("NOTIFICATION_JOB_RETENTION_DAYS", job_days),
        resolved_batch,
    )


def _transient_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (OperationalError, SqlAlchemyTimeoutError, TimeoutError, ConnectionError),
    ) or (isinstance(exc, DBAPIError) and exc.connection_invalidated)


def _log(event: str, **dimensions: str | int) -> None:
    allowed = {
        "status", "reason", "attempt", "notifications_deleted", "job_runs_deleted",
        "retries", "duration_ms", "batch_size", "error_code",
    }
    payload = {"event": event}
    payload.update({key: value for key, value in dimensions.items() if key in allowed})
    logger.info(
        "notification_maintenance %s",
        json.dumps(payload, separators=(",", ":"), sort_keys=True),
    )


class NotificationMaintenanceRunner:
    def __init__(
        self,
        *,
        utc_now: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.utc_now = utc_now or (lambda: datetime.now(timezone.utc))
        self.sleeper = sleeper

    def run(
        self,
        *,
        reference: date,
        read_days: int | None = None,
        job_days: int | None = None,
        batch_size: int | None = None,
        dry_run: bool = False,
    ) -> JobRunResult:
        started = time.monotonic()
        counters = JobCounters()
        if not dry_run and not notification_maintenance_enabled():
            return self._result(reference, "skipped", "feature_flag_off", None, counters, started)
        resolved_read_days, resolved_job_days, size = configured_retention(
            read_days=read_days,
            job_days=job_days,
            batch_size=batch_size,
        )
        reference_end = datetime.combine(reference, clock_time.min, tzinfo=timezone.utc)
        notification_cutoff = reference_end - timedelta(days=resolved_read_days)
        job_cutoff = reference_end - timedelta(days=resolved_job_days)
        if dry_run:
            counters.success = count_expired_read_notifications(notification_cutoff)
            counters.skipped = count_expired_job_runs(job_cutoff)
            counters.processed = counters.success + counters.skipped
            return self._result(reference, "dry_run", "validated", None, counters, started)
        claim = claim_job_run(
            job_type=JOB_TYPE,
            period_start=reference,
            period_end=reference,
            reference_date=reference,
            now=self.utc_now(),
            lease_seconds=LEASE_SECONDS,
            max_attempts=MAX_JOB_ATTEMPTS,
        )
        if not claim.acquired:
            status = "success" if claim.reason == "already_completed" else "skipped"
            return self._result(reference, status, claim.reason, claim.attempt, counters, started)
        assert claim.run_id is not None and claim.lease_token is not None
        error_code: str | None = None
        try:
            while True:
                self._renew_or_raise(claim.run_id, claim.lease_token)
                deleted, retries = self._retry(
                    lambda: delete_expired_read_notifications(notification_cutoff, limit=size)
                )
                counters.success += deleted
                counters.processed += deleted
                counters.retries += retries
                if deleted < size:
                    break
            while True:
                self._renew_or_raise(claim.run_id, claim.lease_token)
                deleted, retries = self._retry(
                    lambda: delete_expired_job_runs(
                        job_cutoff,
                        limit=size,
                        exclude_run_id=claim.run_id,
                    )
                )
                counters.skipped += deleted
                counters.processed += deleted
                counters.retries += retries
                if deleted < size:
                    break
        except Exception as exc:
            counters.failed += 1
            error_code = "database_unavailable" if _transient_error(exc) else str(exc)
            if error_code != "lock_conflict" and not _transient_error(exc):
                error_code = "unexpected_error"

        status = "success" if counters.failed == 0 else (
            "partial_success" if counters.processed else "failed"
        )
        duration_ms = max(0, round((time.monotonic() - started) * 1_000))
        if not finish_job_run(
            claim.run_id,
            claim.lease_token,
            status=status,
            processed_count=counters.processed,
            success_count=counters.success,
            suppressed_count=0,
            skipped_count=counters.skipped,
            failure_count=counters.failed,
            retry_count=counters.retries,
            error_code=error_code if counters.failed else None,
            finished_at=self.utc_now(),
            duration_ms=duration_ms,
        ):
            return self._result(reference, "failed", "lock_conflict", claim.attempt, counters, started)
        return self._result(reference, status, error_code or "completed", claim.attempt, counters, started)

    def _renew_or_raise(self, run_id: int, token: str) -> None:
        if not renew_job_lease(
            run_id,
            token,
            now=self.utc_now(),
            lease_seconds=LEASE_SECONDS,
        ):
            raise RuntimeError("lock_conflict")

    def _retry(self, operation: Callable[[], int]) -> tuple[int, int]:
        retries = 0
        for attempt in range(MAX_USER_ATTEMPTS):
            try:
                return operation(), retries
            except Exception as exc:
                if not _transient_error(exc) or attempt + 1 >= MAX_USER_ATTEMPTS:
                    raise
                self.sleeper(RETRY_BACKOFF_SECONDS[attempt])
                retries += 1
        raise AssertionError("unreachable")

    @staticmethod
    def _result(
        reference: date,
        status: str,
        reason: str,
        attempt: int | None,
        counters: JobCounters,
        started: float,
    ) -> JobRunResult:
        duration_ms = max(0, round((time.monotonic() - started) * 1_000))
        _log(
            "finished",
            status=status,
            reason=reason,
            attempt=attempt or 0,
            notifications_deleted=counters.success,
            job_runs_deleted=counters.skipped,
            retries=counters.retries,
            duration_ms=duration_ms,
        )
        return JobRunResult(
            job_type=JOB_TYPE,
            period_start=reference.isoformat(),
            period_end=reference.isoformat(),
            status=status,
            reason=reason,
            attempt=attempt,
            counters=counters,
            duration_ms=duration_ms,
        )


notification_maintenance_runner = NotificationMaintenanceRunner()
