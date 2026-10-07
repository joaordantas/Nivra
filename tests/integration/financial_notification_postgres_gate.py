"""Guarded P7.3 producer gate for an empty disposable PostgreSQL database.

Usage:
    python -m tests.integration.financial_notification_postgres_gate --preflight
    python -m tests.integration.financial_notification_postgres_gate --execute

The database name must contain ``p73``. Credentials are never printed and all
fixtures are fictional.
"""

from __future__ import annotations

import argparse
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from tests.integration.notification_postgres_gate import _driver_url, require


EXPECTED_HEAD = "f9a0b1c2d3e4"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = "nivra_p73_gate"


def _identity(raw: str) -> tuple[str, str]:
    url = make_url(raw)
    host = (url.host or "").casefold().removeprefix("pooler.").replace("-pooler.", ".")
    return host, (url.database or "").casefold()


def test_url_from_env() -> str:
    local = dotenv_values(ROOT / ".env")
    preview = os.environ.get("P65_PREVIEW_BRANCH_DATABASE_URL") or local.get(
        "P65_PREVIEW_BRANCH_DATABASE_URL"
    )
    raw = os.environ.get("P73_TEST_DATABASE_URL") or local.get("P73_TEST_DATABASE_URL")
    if not raw and preview:
        database = os.environ.get("P73_TEST_DATABASE_NAME", DEFAULT_DATABASE).strip().lower()
        raw = make_url(preview).set(
            drivername="postgresql+pg8000",
            database=database,
            query={},
        ).render_as_string(hide_password=False)
    raw = str(raw or "").strip()
    if not raw:
        raise RuntimeError("P73_TEST_DATABASE_URL e obrigatoria.")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("O gate P7.3 exige PostgreSQL.")
    if not url.database or "p73" not in url.database.casefold():
        raise RuntimeError("O database descartavel deve conter p73 no nome.")
    candidate = _identity(raw)
    if preview:
        preview_identity = _identity(str(preview))
        if candidate[0] != preview_identity[0] or candidate[1] == preview_identity[1]:
            raise RuntimeError("O gate P7.3 exige outro database no endpoint conhecido de Preview.")
    for variable in ("DATABASE_URL", "DATABASE_URL_UNPOOLED", "TEST_DATABASE_URL"):
        configured = os.environ.get(variable) or local.get(variable)
        configured = str(configured or "").strip()
        if not configured:
            continue
        if candidate == _identity(configured):
            raise RuntimeError(f"O alvo P7.3 nao pode coincidir com {variable}.")
    return raw


def preflight_empty_database(raw: str) -> tuple[str, str]:
    url = make_url(raw)
    driver_url = _driver_url(raw)
    connect_args = (
        {"timeout": 10, "ssl_context": True}
        if driver_url.startswith("postgresql+pg8000://")
        else {"connect_timeout": 10}
    )
    engine = create_engine(driver_url, future=True, connect_args=connect_args)
    try:
        with engine.connect() as connection:
            current_database = connection.execute(text("SELECT current_database()")).scalar_one()
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
    return url.host or "postgresql", url.database or "p73"


def _card_fact() -> dict:
    return {
        "card_id": 73,
        "name": "Cartao ficticio P73",
        "total_limit": 1000.0,
        "committed": 920.0,
        "available": 80.0,
        "committed_percent": 92.0,
        "current_invoice_amount": 920.0,
        "closing_date": "2026-10-10",
        "due_date": "2026-10-13",
        "invoice_status": "fechada",
        "next_due_invoice_amount": 920.0,
        "next_due_date": "2026-10-13",
        "next_due_status": "fechada",
    }


def _unusual_fact() -> dict:
    return {
        "id": 730,
        "description": "Gasto ficticio P73",
        "amount": 500.0,
        "date": "2026-10-10",
        "category": "Categoria ficticia",
        "account": "Conta ficticia",
        "source": "manual",
        "baseline": 50.0,
        "times_baseline": 10.0,
        "context": "both",
        "sample_size": 8,
        "global_baseline": 50.0,
        "category_baseline": 50.0,
        "median_absolute_deviation": 0.0,
        "robust_z_score": None,
        "reason": "Deteccao deterministica ficticia.",
        "data_nature": "deterministic_inference",
    }


def run(raw: str) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["TEST_DATABASE_URL"] = _driver_url(raw)
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DATABASE_URL_UNPOOLED", None)

    from alembic import command

    from database.connection import dispose_engine, get_engine
    from database.migrations import get_alembic_config
    from services.financial_notification_service import financial_notification_service
    from services.notification_service import notification_service

    dispose_engine()
    config = get_alembic_config()
    command.upgrade(config, "head")
    command.check(config)
    engine = get_engine()
    with engine.begin() as connection:
        user_a = connection.execute(
            text(
                "INSERT INTO usuarios (usuario, email, senha) VALUES "
                "('P73 Gate A', 'p73-gate-a@example.invalid', 'test-only') RETURNING id"
            )
        ).scalar_one()
        user_b = connection.execute(
            text(
                "INSERT INTO usuarios (usuario, email, senha) VALUES "
                "('P73 Gate B', 'p73-gate-b@example.invalid', 'test-only') RETURNING id"
            )
        ).scalar_one()

    card_commitment = {
        "total_limit": 1000.0,
        "total_committed": 920.0,
        "total_available": 80.0,
        "committed_percent": 92.0,
        "active_cards": 1,
        "cards": [_card_fact()],
    }
    workers = 8
    barrier = threading.Barrier(workers)

    def publish(_: int):
        barrier.wait(timeout=15)
        return financial_notification_service.publish_from_insights(
            user_a,
            card_commitment=card_commitment,
            unusual_expenses=[_unusual_fact()],
            reference=date(2026, 10, 10),
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(publish, range(workers)))
    require(all(result.failed == 0 for result in results), "eight concurrent producer calls")
    require(len(notification_service.list(user_a)) == 3, "one row per logical financial event")

    financial_notification_service.publish_from_insights(
        user_b,
        card_commitment=card_commitment,
        unusual_expenses=[_unusual_fact()],
        reference=date(2026, 10, 10),
    )
    require(len(notification_service.list(user_b)) == 3, "same events are isolated per user")

    with engine.connect() as connection:
        require(
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == EXPECTED_HEAD,
            "Alembic head unchanged",
        )
        keys = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT chave_dedupe FROM notifications "
                    "WHERE usuario_id=:user ORDER BY chave_dedupe"
                ),
                {"user": user_a},
            )
        }
        require(
            keys
            == {
                "card_invoice_due:73:2026-10-13",
                "card_limit_critical:73:2026-10",
                "unusual_expense:manual:730",
            },
            "deterministic producer dedupe keys",
        )
    print("P7.3 PostgreSQL producer gate passed; only fictional data was used.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarded P7.3 PostgreSQL producer gate")
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
