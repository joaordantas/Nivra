from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import DBAPIError, OperationalError, TimeoutError as SqlAlchemyTimeoutError

from repositories.periodic_summary_job_repo import (
    claim_job_run,
    finish_job_run,
    renew_job_lease,
)
from repositories.usuario_repo import contar_usuarios, listar_ids_usuarios_em_lote
from services.periodic_financial_summary_service import (
    PeriodicFinancialSummaryService,
    SummaryPeriod,
    monthly_period,
    periodic_financial_summary_service,
    weekly_period,
)


logger = logging.getLogger("nivra.periodic_summary_jobs")

DEFAULT_BATCH_SIZE = 250
MAX_BATCH_SIZE = 1_000
LEASE_SECONDS = 15 * 60
MAX_JOB_ATTEMPTS = 4
MAX_USER_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (0.25, 0.5)


class JobKind(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class JobCounters:
    processed: int = 0
    success: int = 0
    suppressed: int = 0
    skipped: int = 0
    failed: int = 0
    retries: int = 0


@dataclass(frozen=True)
class JobRunResult:
    job_type: str
    period_start: str
    period_end: str
    status: str
    reason: str
    attempt: int | None
    counters: JobCounters
    duration_ms: int

    def public_dict(self) -> dict:
        return {
            "job_type": self.job_type,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "status": self.status,
            "reason": self.reason,
            "attempt": self.attempt,
            **asdict(self.counters),
            "duration_ms": self.duration_ms,
        }


def periodic_summary_jobs_enabled() -> bool:
    return os.environ.get("PERIODIC_SUMMARY_JOBS_ENABLED", "").strip().casefold() == "true"


def configured_batch_size() -> int:
    raw = os.environ.get("PERIODIC_SUMMARY_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("PERIODIC_SUMMARY_BATCH_SIZE inválido.") from exc
    if not 1 <= value <= MAX_BATCH_SIZE:
        raise RuntimeError("PERIODIC_SUMMARY_BATCH_SIZE fora do limite seguro.")
    return value


def current_civil_date() -> date:
    name = os.environ.get("PERIODIC_SUMMARY_TIMEZONE", "America/Sao_Paulo").strip()
    try:
        zone = ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError("PERIODIC_SUMMARY_TIMEZONE inválido.") from exc
    return datetime.now(zone).date()


def _log(event: str, **dimensions: str | int) -> None:
    # Alembic's test logging configuration may disable pre-existing loggers.
    logger.disabled = False
    logger.setLevel(logging.INFO)
    allowed = {
        "job_type", "period", "status", "reason", "attempt", "processed",
        "success", "suppressed", "skipped", "failed", "retries", "duration_ms",
        "batch_size", "error_code",
    }
    payload = {"event": event}
    payload.update({key: value for key, value in dimensions.items() if key in allowed})
    logger.info("periodic_summary_job %s", json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _transient_error(exc: Exception) -> bool:
    return isinstance(exc, (OperationalError, SqlAlchemyTimeoutError, TimeoutError, ConnectionError)) or (
        isinstance(exc, DBAPIError) and exc.connection_invalidated
    )


class PeriodicSummaryJobRunner:
    def __init__(
        self,
        *,
        summary_service: PeriodicFinancialSummaryService = periodic_financial_summary_service,
        utc_now: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.summary_service = summary_service
        self.utc_now = utc_now or (lambda: datetime.now(timezone.utc))
        self.sleeper = sleeper

    def run_all(
        self,
        *,
        reference: date,
        batch_size: int | None = None,
        dry_run: bool = False,
    ) -> list[JobRunResult]:
        return [
            self.run(JobKind.WEEKLY, reference=reference, batch_size=batch_size, dry_run=dry_run),
            self.run(JobKind.MONTHLY, reference=reference, batch_size=batch_size, dry_run=dry_run),
        ]

    def run(
        self,
        kind: JobKind | str,
        *,
        reference: date,
        batch_size: int | None = None,
        dry_run: bool = False,
    ) -> JobRunResult:
        normalized_kind = JobKind(kind)
        size = batch_size if batch_size is not None else configured_batch_size()
        if not 1 <= size <= MAX_BATCH_SIZE:
            raise ValueError("Batch size fora do limite seguro.")
        period = self._period(normalized_kind, reference)
        started = time.monotonic()
        counters = JobCounters()
        if dry_run:
            counters.skipped = contar_usuarios()
            return self._result(
                normalized_kind, period, "dry_run", "validated", None, counters, started
            )

        claim = claim_job_run(
            job_type=normalized_kind.value,
            period_start=period.start,
            period_end=period.end,
            reference_date=reference,
            now=self.utc_now(),
            lease_seconds=LEASE_SECONDS,
            max_attempts=MAX_JOB_ATTEMPTS,
        )
        if not claim.acquired:
            status = "success" if claim.reason == "already_completed" else "skipped"
            return self._result(
                normalized_kind, period, status, claim.reason, claim.attempt, counters, started
            )
        assert claim.run_id is not None and claim.lease_token is not None
        _log(
            "started",
            job_type=normalized_kind.value,
            period=period.start.isoformat(),
            attempt=claim.attempt or 1,
            batch_size=size,
        )
        error_code: str | None = None
        try:
            last_user_id = 0
            while True:
                if not renew_job_lease(
                    claim.run_id,
                    claim.lease_token,
                    now=self.utc_now(),
                    lease_seconds=LEASE_SECONDS,
                ):
                    error_code = "lock_conflict"
                    return self._result(
                        normalized_kind,
                        period,
                        "failed",
                        error_code,
                        claim.attempt,
                        counters,
                        started,
                    )
                user_ids, query_retries = self._load_batch(last_user_id, size)
                counters.retries += query_retries
                if not user_ids:
                    break
                for user_id in user_ids:
                    outcome, retries, user_error = self._process_user(
                        normalized_kind, user_id, reference, period
                    )
                    counters.processed += 1
                    counters.retries += retries
                    if outcome == "success":
                        counters.success += 1
                    elif outcome == "suppressed":
                        counters.suppressed += 1
                    elif outcome == "skipped":
                        counters.skipped += 1
                    else:
                        counters.failed += 1
                        error_code = user_error or "summary_generation_failed"
                        _log(
                            "user_failed",
                            job_type=normalized_kind.value,
                            period=period.start.isoformat(),
                            error_code=error_code,
                        )
                last_user_id = user_ids[-1]
                if len(user_ids) < size:
                    break
        except Exception as exc:
            error_code = "database_unavailable" if _transient_error(exc) else "unexpected_error"
            counters.failed += 1

        status = self._final_status(counters)
        finished_at = self.utc_now()
        if not finish_job_run(
            claim.run_id,
            claim.lease_token,
            status=status,
            processed_count=counters.processed,
            success_count=counters.success,
            suppressed_count=counters.suppressed,
            skipped_count=counters.skipped,
            failure_count=counters.failed,
            retry_count=counters.retries,
            error_code=error_code if counters.failed else None,
            finished_at=finished_at,
        ):
            return self._result(
                normalized_kind, period, "failed", "lock_conflict", claim.attempt, counters, started
            )
        return self._result(
            normalized_kind,
            period,
            status,
            error_code or "completed",
            claim.attempt,
            counters,
            started,
        )

    def _load_batch(self, last_user_id: int, size: int) -> tuple[list[int], int]:
        retries = 0
        for attempt in range(MAX_USER_ATTEMPTS):
            try:
                return listar_ids_usuarios_em_lote(depois_de=last_user_id, limite=size), retries
            except Exception as exc:
                if not _transient_error(exc) or attempt + 1 >= MAX_USER_ATTEMPTS:
                    raise
                self.sleeper(RETRY_BACKOFF_SECONDS[attempt])
                retries += 1
        raise AssertionError("unreachable")

    def _process_user(
        self,
        kind: JobKind,
        user_id: int,
        reference: date,
        period: SummaryPeriod,
    ) -> tuple[str, int, str | None]:
        retries = 0
        for attempt in range(MAX_USER_ATTEMPTS):
            try:
                if kind is JobKind.WEEKLY:
                    result = self.summary_service.generate_weekly_summary(
                        user_id, reference=reference, period_start=period.start
                    )
                else:
                    result = self.summary_service.generate_monthly_summary(
                        user_id, reference=reference, period_start=period.start
                    )
                if result.outcome == "delivered_or_deduplicated":
                    return "success", retries, None
                if result.outcome == "suppressed":
                    return "suppressed", retries, None
                if result.outcome == "no_activity":
                    return "skipped", retries, None
                retryable = result.retryable
                error_code = result.error_code or "summary_generation_failed"
            except Exception as exc:
                retryable = _transient_error(exc)
                error_code = "database_unavailable" if retryable else "unexpected_error"
            if not retryable or attempt + 1 >= MAX_USER_ATTEMPTS:
                return "failed", retries, error_code
            self.sleeper(RETRY_BACKOFF_SECONDS[attempt])
            retries += 1
        raise AssertionError("unreachable")

    @staticmethod
    def _period(kind: JobKind, reference: date) -> SummaryPeriod:
        return weekly_period(reference) if kind is JobKind.WEEKLY else monthly_period(reference)

    @staticmethod
    def _final_status(counters: JobCounters) -> str:
        if counters.failed == 0:
            return "success"
        if counters.processed > counters.failed:
            return "partial_success"
        return "failed"

    @staticmethod
    def _result(
        kind: JobKind,
        period: SummaryPeriod,
        status: str,
        reason: str,
        attempt: int | None,
        counters: JobCounters,
        started: float,
    ) -> JobRunResult:
        duration_ms = max(0, round((time.monotonic() - started) * 1_000))
        result = JobRunResult(
            job_type=kind.value,
            period_start=period.start.isoformat(),
            period_end=period.end.isoformat(),
            status=status,
            reason=reason,
            attempt=attempt,
            counters=counters,
            duration_ms=duration_ms,
        )
        _log(
            "finished",
            job_type=result.job_type,
            period=result.period_start,
            status=result.status,
            reason=result.reason,
            attempt=result.attempt or 0,
            processed=counters.processed,
            success=counters.success,
            suppressed=counters.suppressed,
            skipped=counters.skipped,
            failed=counters.failed,
            retries=counters.retries,
            duration_ms=duration_ms,
        )
        return result


periodic_summary_job_runner = PeriodicSummaryJobRunner()
