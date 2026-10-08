"""Priority 9 notification operations gate for an isolated PostgreSQL database."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from tests.integration.notification_postgres_gate import _driver_url, require


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DATABASE = "nivra_p9_notifications_gate"
EXPECTED_HEAD = "f5a6b7c8d9e0"
REFERENCE = date(2026, 10, 8)
NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def test_url_from_env() -> str:
    values = dotenv_values(ROOT / ".env")
    preview = os.environ.get("P65_PREVIEW_BRANCH_DATABASE_URL") or values.get(
        "P65_PREVIEW_BRANCH_DATABASE_URL"
    )
    raw = os.environ.get("P9_TEST_DATABASE_URL") or values.get("P9_TEST_DATABASE_URL")
    if not raw and preview:
        raw = make_url(str(preview)).set(
            drivername="postgresql+pg8000",
            database=EXPECTED_DATABASE,
            query={},
        ).render_as_string(hide_password=False)
    raw = str(raw or "").strip()
    url = make_url(raw) if raw else None
    if url is None or url.get_backend_name() != "postgresql":
        raise RuntimeError("P9_TEST_DATABASE_URL PostgreSQL é obrigatória.")
    if (url.database or "").casefold() != EXPECTED_DATABASE:
        raise RuntimeError(f"O gate exige o banco descartável {EXPECTED_DATABASE}.")
    return raw


def run(raw: str) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["TEST_DATABASE_URL"] = _driver_url(raw)
    os.environ["NOTIFICATION_MAINTENANCE_ENABLED"] = "true"
    os.environ["NOTIFICATION_READ_RETENTION_DAYS"] = "30"
    os.environ["NOTIFICATION_JOB_RETENTION_DAYS"] = "30"
    os.environ["NOTIFICATION_MAINTENANCE_BATCH_SIZE"] = "1"
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DATABASE_URL_UNPOOLED", None)

    from alembic import command
    from database.connection import dispose_engine, get_engine
    from database.migrations import get_alembic_config
    from repositories.periodic_summary_job_repo import list_latest_job_runs
    from services.notification_maintenance_service import NotificationMaintenanceRunner
    from services.notification_service import notification_service
    from services.notification_types import NotificationType

    dispose_engine()
    config = get_alembic_config()
    command.upgrade(config, "head")
    command.check(config)
    engine = get_engine()
    inspector = inspect(engine)
    require("notification_dedupe_ledger" in inspector.get_table_names(), "dedupe ledger")
    job_columns = {column["name"] for column in inspector.get_columns("periodic_summary_job_runs")}
    require(
        {"generated_count", "deduplicated_count", "duration_ms"}.issubset(job_columns),
        "job observability columns",
    )

    with engine.begin() as connection:
        user_id = connection.execute(text(
            "INSERT INTO usuarios (usuario,email,senha) "
            "VALUES ('P9 Gate','p9-gate@example.invalid','x') RETURNING id"
        )).scalar_one()
        finance_before = connection.execute(text(
            "SELECT (SELECT COUNT(*) FROM transacoes) + (SELECT COUNT(*) FROM budgets) "
            "+ (SELECT COUNT(*) FROM goals)"
        )).scalar_one()

    expired = notification_service.notify(
        user_id,
        NotificationType.SYSTEM,
        "Expired read",
        "Fictional notification",
        dedupe_key="p9:expired",
    )
    unread = notification_service.notify(
        user_id,
        NotificationType.SYSTEM,
        "Unread",
        "Fictional notification",
        dedupe_key="p9:unread",
    )
    require(expired is not None and unread is not None, "notification setup")
    notification_service.mark_read(user_id, expired["id"])
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE notifications SET criada_em='2026-08-01' WHERE id IN (:expired,:unread)"),
            {"expired": expired["id"], "unread": unread["id"]},
        )
        connection.execute(
            text("UPDATE notifications SET lida_em='2026-08-02' WHERE id=:expired"),
            {"expired": expired["id"]},
        )

    barrier = threading.Barrier(8)

    def invoke(_index: int):
        barrier.wait(timeout=20)
        return NotificationMaintenanceRunner(
            utc_now=lambda: NOW,
            sleeper=lambda _seconds: None,
        ).run(reference=REFERENCE)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(invoke, range(8)))
    require(sum(item.counters.success for item in results) == 1, "single cleanup owner")

    replay = notification_service.deliver(
        user_id,
        NotificationType.SYSTEM,
        "Replay",
        "Must remain deduplicated",
        dedupe_key="p9:expired",
    )
    require(replay.deduplicated and replay.notification is None, "durable dedupe after cleanup")
    with engine.connect() as connection:
        require(connection.execute(text(
            "SELECT COUNT(*) FROM notifications WHERE chave_dedupe='p9:unread'"
        )).scalar_one() == 1, "unread retention")
        require(connection.execute(text(
            "SELECT COUNT(*) FROM notification_dedupe_ledger"
        )).scalar_one() == 2, "ledger retention")
        require(connection.execute(text(
            "SELECT (SELECT COUNT(*) FROM transacoes) + (SELECT COUNT(*) FROM budgets) "
            "+ (SELECT COUNT(*) FROM goals)"
        )).scalar_one() == finance_before, "no financial side effect")
    latest = list_latest_job_runs()
    require(any(row["job_type"] == "cleanup" and row["status"] == "success" for row in latest), "latest status")

    command.downgrade(config, "e4f5a6b7c8d9")
    with get_engine().connect() as connection:
        require(connection.execute(text("SELECT COUNT(*) FROM notifications")).scalar_one() == 1, "downgrade preserves visible notifications")
    command.upgrade(config, "head")
    command.check(config)
    with get_engine().connect() as connection:
        require(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == EXPECTED_HEAD, "Alembic head")
    dispose_engine()
    print("Priority 9 notification operations PostgreSQL gate passed; only fictional data was used.")


def main() -> None:
    try:
        run(test_url_from_env())
    except Exception as exc:
        print(f"Gate stopped: {type(exc).__name__}; details suppressed.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
