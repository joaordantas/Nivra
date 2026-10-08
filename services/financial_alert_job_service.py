from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from typing import Callable

from sqlalchemy.exc import DBAPIError, OperationalError, TimeoutError as SqlAlchemyTimeoutError

from repositories.periodic_summary_job_repo import (
    claim_job_run,
    finish_job_run,
    renew_job_lease,
)
from repositories.usuario_repo import contar_usuarios, listar_ids_usuarios_em_lote
from services.financial_threshold_alert_service import (
    FinancialThresholdAlertService,
    financial_threshold_alert_service,
    financial_threshold_alerts_enabled,
)
from services.periodic_summary_job_service import (
    DEFAULT_BATCH_SIZE,
    LEASE_SECONDS,
    MAX_BATCH_SIZE,
    MAX_JOB_ATTEMPTS,
    MAX_USER_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    JobCounters,
    JobRunResult,
)


logger = logging.getLogger("nivra.financial_alert_jobs")
JOB_TYPE = "financial_alerts"


def _transient_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (OperationalError, SqlAlchemyTimeoutError, TimeoutError, ConnectionError),
    ) or (isinstance(exc, DBAPIError) and exc.connection_invalidated)


class FinancialAlertJobRunner:
    def __init__(
        self,
        *,
        alert_service: FinancialThresholdAlertService = financial_threshold_alert_service,
        utc_now: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.alert_service = alert_service
        self.utc_now = utc_now or (lambda: datetime.now(timezone.utc))
        self.sleeper = sleeper

    def run(
        self,
        *,
        reference: date,
        batch_size: int = DEFAULT_BATCH_SIZE,
        dry_run: bool = False,
    ) -> JobRunResult:
        started = time.monotonic()
        counters = JobCounters()
        if not 1 <= batch_size <= MAX_BATCH_SIZE:
            raise ValueError("Batch size fora do limite seguro.")
        if dry_run:
            counters.skipped = contar_usuarios()
            return self._result(reference, "dry_run", "validated", None, counters, started)
        if not financial_threshold_alerts_enabled():
            return self._result(
                reference, "skipped", "feature_flag_off", None, counters, started
            )

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
            return self._result(
                reference, status, claim.reason, claim.attempt, counters, started
            )
        assert claim.run_id is not None and claim.lease_token is not None
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
                    counters.failed += 1
                    break
                user_ids, query_retries = self._load_batch(last_user_id, batch_size)
                counters.retries += query_retries
                if not user_ids:
                    break
                for usuario_id in user_ids:
                    outcome, retries, user_error = self._process_user(
                        usuario_id, reference
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
                        error_code = user_error or "alert_evaluation_failed"
                last_user_id = user_ids[-1]
                if len(user_ids) < batch_size:
                    break
        except Exception as exc:
            counters.failed += 1
            error_code = "database_unavailable" if _transient_error(exc) else "unexpected_error"

        status = "success" if counters.failed == 0 else (
            "partial_success" if counters.processed > counters.failed else "failed"
        )
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
            finished_at=self.utc_now(),
        ):
            return self._result(
                reference, "failed", "lock_conflict", claim.attempt, counters, started
            )
        return self._result(
            reference,
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
                return listar_ids_usuarios_em_lote(
                    depois_de=last_user_id, limite=size
                ), retries
            except Exception as exc:
                if not _transient_error(exc) or attempt + 1 >= MAX_USER_ATTEMPTS:
                    raise
                self.sleeper(RETRY_BACKOFF_SECONDS[attempt])
                retries += 1
        raise AssertionError("unreachable")

    def _process_user(
        self, usuario_id: int, reference: date
    ) -> tuple[str, int, str | None]:
        retries = 0
        for attempt in range(MAX_USER_ATTEMPTS):
            try:
                result = self.alert_service.evaluate_user(
                    usuario_id, reference=reference, baseline_missing=True
                )
                if result.failed:
                    return "failed", retries, "notification_delivery_failed"
                if result.delivered_or_deduplicated:
                    return "success", retries, None
                if result.suppressed:
                    return "suppressed", retries, None
                return "skipped", retries, None
            except Exception as exc:
                if not _transient_error(exc) or attempt + 1 >= MAX_USER_ATTEMPTS:
                    code = "database_unavailable" if _transient_error(exc) else "unexpected_error"
                    return "failed", retries, code
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
        logger.info(
            "financial_alert_job status=%s reason=%s processed=%s failed=%s",
            status,
            reason,
            counters.processed,
            counters.failed,
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


financial_alert_job_runner = FinancialAlertJobRunner()
