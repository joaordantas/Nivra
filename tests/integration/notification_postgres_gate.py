"""Guarded P7.1 PostgreSQL gate; never included in ordinary test discovery.

Usage:
    python -m tests.integration.notification_postgres_gate --preflight
    python -m tests.integration.notification_postgres_gate --execute

The target must be an empty PostgreSQL database whose name contains ``p71``.
Only fictional fixtures are written and credentials are never printed.
"""

from __future__ import annotations

import argparse
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


EXPECTED_HEAD = "e8f9a0b1c2d3"


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def _driver_url(raw: str) -> str:
    url = make_url(raw)
    if url.get_backend_name() != "postgresql":
        return raw
    try:
        import psycopg  # noqa: F401
    except ImportError:
        driver = "postgresql+pg8000"
    else:
        return url.set(drivername="postgresql+psycopg").render_as_string(
            hide_password=False
        )
    query = dict(url.query)
    query.pop("sslmode", None)
    query.pop("channel_binding", None)
    return url.set(drivername=driver, query=query).render_as_string(
        hide_password=False
    )


def test_url_from_env() -> str:
    raw = os.environ.get("P71_TEST_DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError("P71_TEST_DATABASE_URL e obrigatoria.")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("O gate P7.1 exige PostgreSQL.")
    if not url.database or "p71" not in url.database.casefold():
        raise RuntimeError("O database descartavel deve conter p71 no nome.")
    candidate = (url.host or "").casefold(), url.database.casefold()
    for variable in ("DATABASE_URL", "DATABASE_URL_UNPOOLED", "TEST_DATABASE_URL"):
        configured = os.environ.get(variable, "").strip()
        if not configured:
            continue
        configured_url = make_url(configured)
        configured_target = (
            (configured_url.host or "").casefold(),
            (configured_url.database or "").casefold(),
        )
        if candidate == configured_target:
            raise RuntimeError(f"O alvo P7.1 nao pode coincidir com {variable}.")
    return raw


def preflight_empty_database(raw: str) -> tuple[str, str]:
    url = make_url(raw)
    driver_url = _driver_url(raw)
    connect_args = (
        {"timeout": 10, "ssl_context": True}
        if driver_url.startswith("postgresql+pg8000://")
        else {"connect_timeout": 10}
    )
    engine = create_engine(
        driver_url,
        future=True,
        connect_args=connect_args,
    )
    try:
        with engine.connect() as connection:
            current_database = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()
            require(current_database == url.database, "target database identity")
            tables = connection.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname='public' ORDER BY tablename"
                )
            ).scalars().all()
            require(not tables, "empty public schema")
    finally:
        engine.dispose()
    return url.host or "postgresql", url.database or "p71"


def run(raw: str) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["TEST_DATABASE_URL"] = _driver_url(raw)
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DATABASE_URL_UNPOOLED", None)

    from alembic import command

    from database.connection import dispose_engine, get_engine
    from database.migrations import get_alembic_config
    from services.notification_service import NotificationNotFoundError, notification_service
    from services.notification_types import NotificationSeverity, NotificationType

    dispose_engine()
    config = get_alembic_config()
    command.upgrade(config, "head")
    command.check(config)
    engine = get_engine()
    with engine.begin() as connection:
        user_a = connection.execute(
            text(
                "INSERT INTO usuarios (usuario, email, senha) VALUES "
                "('P71 Gate A', 'p71-gate-a@example.invalid', 'test-only') RETURNING id"
            )
        ).scalar_one()
        user_b = connection.execute(
            text(
                "INSERT INTO usuarios (usuario, email, senha) VALUES "
                "('P71 Gate B', 'p71-gate-b@example.invalid', 'test-only') RETURNING id"
            )
        ).scalar_one()

    workers = 8
    barrier = threading.Barrier(workers)

    def create_same_notification(_: int) -> dict:
        barrier.wait(timeout=15)
        return notification_service.notify(
            user_a,
            NotificationType.FINANCIAL_ALERT,
            "Fatura ficticia",
            "Evento ficticio do gate P7.1.",
            severity=NotificationSeverity.WARNING,
            metadata={"route": "/cards", "source_type": "gate", "source_id": "42"},
            dedupe_key="gate:invoice:42:2026-10",
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        concurrent = list(executor.map(create_same_notification, range(workers)))
    require(len({item["id"] for item in concurrent}) == 1, "concurrent dedupe returns one identity")

    distinct = notification_service.notify(
        user_a,
        NotificationType.SYSTEM,
        "Evento distinto",
        "Segunda notificacao legitima.",
        dedupe_key="gate:system:distinct",
    )
    other_user = notification_service.notify(
        user_b,
        NotificationType.FINANCIAL_ALERT,
        "Fatura ficticia B",
        "Mesma chave, outro usuario.",
        dedupe_key="gate:invoice:42:2026-10",
    )
    require(len(notification_service.list(user_a)) == 2, "user A lists only owned rows")
    require(len(notification_service.list(user_b)) == 1, "user B lists only owned rows")
    require(other_user["id"] not in {item["id"] for item in concurrent}, "dedupe is user scoped")
    try:
        notification_service.mark_read(user_a, other_user["id"])
    except NotificationNotFoundError:
        pass
    else:
        raise AssertionError("cross-user read must be concealed")
    require(not notification_service.delete(user_a, other_user["id"]), "cross-user delete is harmless")
    require(notification_service.mark_all_read(user_a) == 2, "read-all affects only user A")
    require(notification_service.unread_count(user_a) == 0, "user A unread count updated")
    require(notification_service.unread_count(user_b) == 1, "user B unread count isolated")
    require(notification_service.delete(user_a, distinct["id"]), "owned notification deletion")

    with engine.connect() as connection:
        require(
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == EXPECTED_HEAD,
            "Alembic head",
        )
        require(
            connection.execute(
                text(
                    "SELECT count(*) FROM notifications "
                    "WHERE usuario_id=:user AND chave_dedupe='gate:invoice:42:2026-10'"
                ),
                {"user": user_a},
            ).scalar_one()
            == 1,
            "one persisted row after concurrency",
        )
        constraints = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid='notifications'::regclass"
                )
            )
        }
        require(
            {
                "uq_notifications_user_dedupe",
                "ck_notifications_type",
                "ck_notifications_severity",
                "ck_notifications_read_state",
            }.issubset(constraints),
            "notification constraints",
        )
        indexes = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname='public' AND tablename='notifications'"
                )
            )
        }
        require(
            {"ix_notifications_user_created", "ix_notifications_user_unread_created"}.issubset(indexes),
            "query indexes",
        )
    print("P7.1 PostgreSQL gate passed; only fictional data was used.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarded P7.1 PostgreSQL integration gate")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        raw = test_url_from_env()
        host, database = preflight_empty_database(raw)
        print(f"Disposable PostgreSQL confirmed: host={host}, database={database}; credentials hidden")
        if args.execute:
            run(raw)
        else:
            print("Read-only preflight passed; no writes made.")
    except Exception as exc:
        if isinstance(exc, (RuntimeError, AssertionError, ImportError, TypeError)):
            print(f"Gate stopped: {type(exc).__name__}: {exc}")
        else:
            print(f"Gate stopped: {type(exc).__name__}; details suppressed to protect credentials.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
