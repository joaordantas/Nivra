from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, delete, exists, func, select

from database.connection import get_engine
from database.models import notifications, periodic_summary_job_runs


TERMINAL_JOB_STATUSES = ("success", "partial_success", "failed")


def count_expired_read_notifications(cutoff: datetime) -> int:
    engine = get_engine()
    with engine.connect() as connection:
        return int(connection.scalar(
            select(func.count()).select_from(notifications).where(
                notifications.c.lida.is_(True),
                notifications.c.lida_em < cutoff,
            )
        ) or 0)


def delete_expired_read_notifications(cutoff: datetime, *, limit: int) -> int:
    ids = (
        select(notifications.c.id)
        .where(
            notifications.c.lida.is_(True),
            notifications.c.lida_em < cutoff,
        )
        .order_by(notifications.c.lida_em, notifications.c.id)
        .limit(limit)
    )
    engine = get_engine()
    with engine.begin() as connection:
        result = connection.execute(delete(notifications).where(notifications.c.id.in_(ids)))
        return int(result.rowcount)


def _expired_job_filter(cutoff: datetime, *, exclude_run_id: int | None = None):
    newer = periodic_summary_job_runs.alias("newer_job_run")
    conditions = [
        periodic_summary_job_runs.c.status.in_(TERMINAL_JOB_STATUSES),
        periodic_summary_job_runs.c.finished_at < cutoff,
        exists(
            select(newer.c.id).where(
                newer.c.job_type == periodic_summary_job_runs.c.job_type,
                newer.c.id > periodic_summary_job_runs.c.id,
            )
        ),
    ]
    if exclude_run_id is not None:
        conditions.append(periodic_summary_job_runs.c.id != exclude_run_id)
    return and_(*conditions)


def count_expired_job_runs(cutoff: datetime, *, exclude_run_id: int | None = None) -> int:
    engine = get_engine()
    with engine.connect() as connection:
        return int(connection.scalar(
            select(func.count()).select_from(periodic_summary_job_runs).where(
                _expired_job_filter(cutoff, exclude_run_id=exclude_run_id)
            )
        ) or 0)


def delete_expired_job_runs(
    cutoff: datetime,
    *,
    limit: int,
    exclude_run_id: int,
) -> int:
    ids = (
        select(periodic_summary_job_runs.c.id)
        .where(_expired_job_filter(cutoff, exclude_run_id=exclude_run_id))
        .order_by(periodic_summary_job_runs.c.finished_at, periodic_summary_job_runs.c.id)
        .limit(limit)
    )
    engine = get_engine()
    with engine.begin() as connection:
        result = connection.execute(
            delete(periodic_summary_job_runs).where(periodic_summary_job_runs.c.id.in_(ids))
        )
        return int(result.rowcount)
