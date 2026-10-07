"""P7.6 gate for the isolated disposable PostgreSQL database."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import make_url

from tests.integration.notification_postgres_gate import _driver_url, require


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DATABASE = "nivra_p76_gate"
EXPECTED_HEAD = "b1c2d3e4f5a6"
FIXED_NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def test_url_from_env() -> str:
    values = dotenv_values(ROOT / ".env")
    preview = os.environ.get("P65_PREVIEW_BRANCH_DATABASE_URL") or values.get(
        "P65_PREVIEW_BRANCH_DATABASE_URL"
    )
    raw = os.environ.get("P76_TEST_DATABASE_URL") or values.get("P76_TEST_DATABASE_URL")
    if not raw and preview:
        raw = make_url(str(preview)).set(
            drivername="postgresql+pg8000", database=EXPECTED_DATABASE, query={}
        ).render_as_string(hide_password=False)
    raw = str(raw or "").strip()
    url = make_url(raw) if raw else None
    if url is None or url.get_backend_name() != "postgresql":
        raise RuntimeError("P76_TEST_DATABASE_URL PostgreSQL é obrigatória.")
    if (url.database or "").casefold() != EXPECTED_DATABASE:
        raise RuntimeError("O gate exige o banco descartável nivra_p76_gate.")
    candidate = ((url.host or "").casefold(), (url.database or "").casefold())
    for variable in ("DATABASE_URL", "DATABASE_URL_UNPOOLED", "TEST_DATABASE_URL"):
        configured = str(os.environ.get(variable) or values.get(variable) or "").strip()
        if not configured:
            continue
        configured_url = make_url(configured)
        configured_target = (
            (configured_url.host or "").casefold(),
            (configured_url.database or "").casefold(),
        )
        if candidate == configured_target:
            raise RuntimeError(f"O alvo P7.6 não pode coincidir com {variable}.")
    return raw


class OneUserFailureService:
    def __init__(self, delegate, failing_user: int) -> None:
        self.delegate = delegate
        self.failing_user = failing_user

    def generate_weekly_summary(self, user_id, *, reference, period_start=None):
        if user_id == self.failing_user:
            from services.periodic_financial_summary_service import (
                PeriodicSummaryResult,
                weekly_period,
            )

            return PeriodicSummaryResult(
                period=weekly_period(reference, period_start),
                outcome="failed",
                error_code="summary_generation_failed",
                retryable=False,
            )
        return self.delegate.generate_weekly_summary(
            user_id, reference=reference, period_start=period_start
        )


def run(raw: str) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["TEST_DATABASE_URL"] = _driver_url(raw)
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DATABASE_URL_UNPOOLED", None)

    from alembic import command
    from database.connection import dispose_engine, get_engine
    from database.migrations import get_alembic_config
    from repositories.periodic_summary_job_repo import claim_job_run, finish_job_run
    from services.notification_preference_service import notification_preference_service
    from services.periodic_financial_summary_service import periodic_financial_summary_service
    from services.periodic_summary_job_service import JobKind, PeriodicSummaryJobRunner

    dispose_engine()
    config = get_alembic_config()
    command.upgrade(config, "head")
    command.check(config)
    engine = get_engine()
    active_users: list[int] = []
    with engine.begin() as connection:
        for index in range(1, 8):
            user_id = connection.execute(
                text(
                    "INSERT INTO usuarios (usuario,email,senha) VALUES "
                    "(:name,:email,'test') RETURNING id"
                ),
                {"name": f"P76 Fictício {index}", "email": f"p76-{index}@example.invalid"},
            ).scalar_one()
            active_users.append(user_id)
            category = connection.execute(
                text(
                    "INSERT INTO categorias (nome,usuario_id) "
                    "VALUES ('Alimentação',:user) RETURNING id"
                ),
                {"user": user_id},
            ).scalar_one()
            account = connection.execute(
                text(
                    "INSERT INTO contas (nome,tipo,saldo_inicial,usuario_id,principal) "
                    "VALUES ('Conta','digital',0,:user,FALSE) RETURNING id"
                ),
                {"user": user_id},
            ).scalar_one()
            for transaction_date in (date(2026, 9, 30), date(2026, 9, 2)):
                connection.execute(
                    text(
                        "INSERT INTO transacoes "
                        "(valor,tipo,categoria_id,comentario,data,usuario_id,conta_id) "
                        "VALUES (100,'saida',:category,'Fictício',:day,:user,:account)"
                    ),
                    {
                        "category": category,
                        "day": transaction_date,
                        "user": user_id,
                        "account": account,
                    },
                )
        connection.execute(
            text(
                "INSERT INTO usuarios (usuario,email,senha) VALUES "
                "('P76 Sem Atividade','p76-empty@example.invalid','test')"
            )
        )

    notification_preference_service.update(active_users[1], {"monthly_summary": False})
    workers = 8
    barrier = threading.Barrier(workers)

    def run_weekly(_index):
        barrier.wait(timeout=20)
        return PeriodicSummaryJobRunner(
            utc_now=lambda: FIXED_NOW,
            sleeper=lambda _seconds: None,
        ).run(JobKind.WEEKLY, reference=date(2026, 10, 7), batch_size=3)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        weekly_results = list(executor.map(run_weekly, range(workers)))
    require(sum(item.counters.processed for item in weekly_results) == 8, "single concurrent owner")
    require(
        sum(item.counters.success for item in weekly_results) == 7,
        "weekly real-service fan-out",
    )
    require(
        all(item.reason in {"completed", "lock_conflict", "already_completed"} for item in weekly_results),
        "duplicate scheduler calls converge",
    )

    monthly = PeriodicSummaryJobRunner(
        utc_now=lambda: FIXED_NOW,
        sleeper=lambda _seconds: None,
    ).run(JobKind.MONTHLY, reference=date(2026, 10, 7), batch_size=3)
    require(monthly.status == "success", "monthly job success")
    require(
        (monthly.counters.success, monthly.counters.suppressed, monthly.counters.skipped)
        == (6, 1, 1),
        "preferences and no-activity outcomes",
    )
    notification_preference_service.update(active_users[1], {"monthly_summary": True})
    monthly_replay = PeriodicSummaryJobRunner(utc_now=lambda: FIXED_NOW).run(
        JobKind.MONTHLY, reference=date(2026, 10, 8), batch_size=3
    )
    require(monthly_replay.reason == "already_completed", "no suppressed-period backfill")

    partial = PeriodicSummaryJobRunner(
        summary_service=OneUserFailureService(
            periodic_financial_summary_service, active_users[1]
        ),
        utc_now=lambda: FIXED_NOW,
        sleeper=lambda _seconds: None,
    ).run(JobKind.WEEKLY, reference=date(2026, 9, 9), batch_size=3)
    recovered = PeriodicSummaryJobRunner(
        utc_now=lambda: FIXED_NOW + timedelta(minutes=1),
        sleeper=lambda _seconds: None,
    ).run(JobKind.WEEKLY, reference=date(2026, 9, 9), batch_size=3)
    require(partial.status == "partial_success", "per-user fault isolation")
    require(recovered.status == "success" and recovered.attempt == 2, "partial-run recovery")

    first_claim = claim_job_run(
        job_type="monthly",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        reference_date=date(2026, 9, 1),
        now=FIXED_NOW,
        lease_seconds=60,
        max_attempts=4,
    )
    concurrent_claim = claim_job_run(
        job_type="monthly",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        reference_date=date(2026, 9, 1),
        now=FIXED_NOW,
        lease_seconds=60,
        max_attempts=4,
    )
    recovered_claim = claim_job_run(
        job_type="monthly",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        reference_date=date(2026, 9, 1),
        now=FIXED_NOW + timedelta(seconds=61),
        lease_seconds=60,
        max_attempts=4,
    )
    require(first_claim.acquired, "persistent lease acquired")
    require(concurrent_claim.reason == "lock_conflict", "live lease blocks overlap")
    require(recovered_claim.acquired and recovered_claim.attempt == 2, "expired lease recovery")
    require(
        finish_job_run(
            recovered_claim.run_id,
            recovered_claim.lease_token,
            status="success",
            processed_count=0,
            success_count=0,
            suppressed_count=0,
            skipped_count=0,
            failure_count=0,
            retry_count=0,
            error_code=None,
            finished_at=FIXED_NOW + timedelta(seconds=62),
        ),
        "recovered lease completion",
    )

    with engine.connect() as connection:
        require(
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == EXPECTED_HEAD,
            "Alembic head",
        )
        require(
            connection.execute(
                text(
                    "SELECT COUNT(*) FROM notifications "
                    "WHERE chave_dedupe='weekly_summary:2026-09-28'"
                )
            ).scalar_one()
            == 7,
            "weekly notification idempotency",
        )
        require(
            connection.execute(
                text(
                    "SELECT COUNT(*) FROM notifications "
                    "WHERE chave_dedupe='weekly_summary:2026-08-31'"
                )
            ).scalar_one()
            == 7,
            "recovery preserves per-user idempotency",
        )
        require(
            connection.execute(
                text(
                    "SELECT COUNT(*) FROM notifications WHERE usuario_id=:user "
                    "AND chave_dedupe='monthly_summary:2026-09-01'"
                ),
                {"user": active_users[1]},
            ).scalar_one()
            == 0,
            "suppressed notification remains absent",
        )
        require(
            connection.execute(
                text(
                    "SELECT COUNT(*) FROM notification_preference_suppressions "
                    "WHERE usuario_id=:user AND dedupe_key='monthly_summary:2026-09-01'"
                ),
                {"user": active_users[1]},
            ).scalar_one()
            == 1,
            "suppression ledger recorded",
        )
        tracked = connection.execute(
            text(
                "SELECT status, attempt, processed_count, success_count, failure_count "
                "FROM periodic_summary_job_runs WHERE job_type='weekly' "
                "AND period_start='2026-08-31'"
            )
        ).mappings().one()
        require(
            tracked["status"] == "success"
            and tracked["attempt"] == 2
            and tracked["processed_count"] == 8
            and tracked["success_count"] == 7
            and tracked["failure_count"] == 0,
            "job tracking counters",
        )
        columns = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='periodic_summary_job_runs'"
                )
            )
        }
        require(
            not columns.intersection({"email", "usuario_id", "title", "message", "valor"}),
            "tracking stores no PII or financial content",
        )

    dispose_engine()
    command.downgrade(config, "a0b1c2d3e4f5")
    command.upgrade(config, "head")
    command.check(config)
    with get_engine().connect() as connection:
        require(
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == EXPECTED_HEAD,
            "downgrade and re-upgrade",
        )
    dispose_engine()
    print("P7.6 PostgreSQL gate passed; only fictional data was used.")


def main() -> None:
    try:
        run(test_url_from_env())
    except Exception as exc:
        print(f"Gate stopped: {type(exc).__name__}; details suppressed.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
