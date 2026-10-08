from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database.connection import get_engine
from database.models import periodic_summary_job_runs


@dataclass(frozen=True)
class JobClaim:
    acquired: bool
    reason: str
    run_id: int | None = None
    lease_token: str | None = None
    attempt: int | None = None


def _insert_for_dialect(dialect_name: str):
    if dialect_name == "postgresql":
        return postgresql_insert(periodic_summary_job_runs)
    if dialect_name == "sqlite":
        return sqlite_insert(periodic_summary_job_runs)
    return insert(periodic_summary_job_runs)


def claim_job_run(
    *,
    job_type: str,
    period_start: date,
    period_end: date,
    reference_date: date,
    now: datetime,
    lease_seconds: int,
    max_attempts: int,
) -> JobClaim:
    engine = get_engine()
    token = str(uuid4())
    expires_at = now + timedelta(seconds=lease_seconds)
    base = _insert_for_dialect(engine.dialect.name).values(
        job_type=job_type,
        period_start=period_start,
        period_end=period_end,
        reference_date=reference_date,
        status="running",
        lease_token=token,
        lease_expires_at=expires_at,
        attempt=1,
        started_at=now,
    )
    reclaimable = and_(
        periodic_summary_job_runs.c.attempt < max_attempts,
        or_(
            periodic_summary_job_runs.c.status.in_(("failed", "partial_success")),
            and_(
                periodic_summary_job_runs.c.status == "running",
                periodic_summary_job_runs.c.lease_expires_at <= now,
            ),
        ),
    )
    if engine.dialect.name in {"postgresql", "sqlite"}:
        statement = base.on_conflict_do_update(
            index_elements=["job_type", "period_start"],
            set_={
                "period_end": period_end,
                "reference_date": reference_date,
                "status": "running",
                "lease_token": token,
                "lease_expires_at": expires_at,
                "attempt": periodic_summary_job_runs.c.attempt + 1,
                "processed_count": 0,
                "success_count": 0,
                "suppressed_count": 0,
                "skipped_count": 0,
                "failure_count": 0,
                "retry_count": 0,
                "generated_count": 0,
                "deduplicated_count": 0,
                "duration_ms": 0,
                "error_code": None,
                "started_at": now,
                "finished_at": None,
            },
            where=reclaimable,
        ).returning(
            periodic_summary_job_runs.c.id,
            periodic_summary_job_runs.c.attempt,
        )
    else:
        statement = base.returning(
            periodic_summary_job_runs.c.id,
            periodic_summary_job_runs.c.attempt,
        )
    with engine.begin() as connection:
        row = connection.execute(statement).first()
        if row is not None:
            return JobClaim(True, "acquired", int(row.id), token, int(row.attempt))
        existing = connection.execute(
            select(
                periodic_summary_job_runs.c.status,
                periodic_summary_job_runs.c.attempt,
                periodic_summary_job_runs.c.lease_expires_at,
            ).where(
                periodic_summary_job_runs.c.job_type == job_type,
                periodic_summary_job_runs.c.period_start == period_start,
            )
        ).first()
    if existing is None:
        return JobClaim(False, "lock_conflict")
    if existing.status == "success":
        return JobClaim(False, "already_completed", attempt=int(existing.attempt))
    if int(existing.attempt) >= max_attempts:
        return JobClaim(False, "attempt_limit", attempt=int(existing.attempt))
    return JobClaim(False, "lock_conflict", attempt=int(existing.attempt))


def renew_job_lease(
    run_id: int,
    lease_token: str,
    *,
    now: datetime,
    lease_seconds: int,
) -> bool:
    engine = get_engine()
    with engine.begin() as connection:
        result = connection.execute(
            update(periodic_summary_job_runs)
            .where(
                periodic_summary_job_runs.c.id == run_id,
                periodic_summary_job_runs.c.status == "running",
                periodic_summary_job_runs.c.lease_token == lease_token,
            )
            .values(lease_expires_at=now + timedelta(seconds=lease_seconds))
        )
        return result.rowcount == 1


def finish_job_run(
    run_id: int,
    lease_token: str,
    *,
    status: str,
    processed_count: int,
    success_count: int,
    suppressed_count: int,
    skipped_count: int,
    failure_count: int,
    retry_count: int,
    error_code: str | None,
    finished_at: datetime,
    generated_count: int = 0,
    deduplicated_count: int = 0,
    duration_ms: int = 0,
) -> bool:
    engine = get_engine()
    with engine.begin() as connection:
        result = connection.execute(
            update(periodic_summary_job_runs)
            .where(
                periodic_summary_job_runs.c.id == run_id,
                periodic_summary_job_runs.c.status == "running",
                periodic_summary_job_runs.c.lease_token == lease_token,
            )
            .values(
                status=status,
                lease_token=None,
                lease_expires_at=None,
                processed_count=processed_count,
                success_count=success_count,
                suppressed_count=suppressed_count,
                skipped_count=skipped_count,
                failure_count=failure_count,
                retry_count=retry_count,
                generated_count=generated_count,
                deduplicated_count=deduplicated_count,
                duration_ms=duration_ms,
                error_code=error_code,
                finished_at=finished_at,
            )
        )
        return result.rowcount == 1


def get_job_run(job_type: str, period_start: date) -> dict | None:
    engine = get_engine()
    with engine.connect() as connection:
        row = connection.execute(
            select(periodic_summary_job_runs).where(
                periodic_summary_job_runs.c.job_type == job_type,
                periodic_summary_job_runs.c.period_start == period_start,
            )
        ).mappings().first()
        return dict(row) if row is not None else None


def list_latest_job_runs() -> list[dict]:
    engine = get_engine()
    ranked = select(
        periodic_summary_job_runs,
        func.row_number().over(
            partition_by=periodic_summary_job_runs.c.job_type,
            order_by=(
                periodic_summary_job_runs.c.started_at.desc(),
                periodic_summary_job_runs.c.id.desc(),
            ),
        ).label("position"),
    ).subquery()
    with engine.connect() as connection:
        rows = connection.execute(
            select(ranked).where(ranked.c.position == 1).order_by(ranked.c.job_type)
        ).mappings()
        safe_fields = {
            "id", "job_type", "period_start", "period_end", "reference_date",
            "status", "lease_expires_at", "attempt", "processed_count",
            "success_count", "suppressed_count", "skipped_count", "failure_count",
            "retry_count", "generated_count", "deduplicated_count", "duration_ms",
            "error_code", "started_at", "finished_at",
        }
        return [
            {key: value for key, value in row.items() if key in safe_fields}
            for row in rows
        ]
