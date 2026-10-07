"""Guarded P7.4 notification-preference gate for disposable PostgreSQL."""

from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from tests.integration.notification_postgres_gate import _driver_url, require


EXPECTED_HEAD = "f9a0b1c2d3e4"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = "nivra_p74_gate"


def _identity(raw: str) -> tuple[str, str]:
    url = make_url(raw)
    host = (url.host or "").casefold().removeprefix("pooler.").replace("-pooler.", ".")
    return host, (url.database or "").casefold()


def test_url_from_env() -> str:
    local = dotenv_values(ROOT / ".env")
    preview = os.environ.get("P65_PREVIEW_BRANCH_DATABASE_URL") or local.get(
        "P65_PREVIEW_BRANCH_DATABASE_URL"
    )
    raw = os.environ.get("P74_TEST_DATABASE_URL") or local.get("P74_TEST_DATABASE_URL")
    if not raw and preview:
        database = os.environ.get("P74_TEST_DATABASE_NAME", DEFAULT_DATABASE).strip().lower()
        raw = make_url(preview).set(
            drivername="postgresql+pg8000",
            database=database,
            query={},
        ).render_as_string(hide_password=False)
    raw = str(raw or "").strip()
    if not raw:
        raise RuntimeError("P74_TEST_DATABASE_URL e obrigatoria.")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("O gate P7.4 exige PostgreSQL.")
    if not url.database or "p74" not in url.database.casefold():
        raise RuntimeError("O database descartavel deve conter p74 no nome.")
    candidate = _identity(raw)
    if preview:
        preview_identity = _identity(str(preview))
        if candidate[0] != preview_identity[0] or candidate[1] == preview_identity[1]:
            raise RuntimeError("O gate P7.4 exige outro database no endpoint conhecido de Preview.")
    for variable in ("DATABASE_URL", "DATABASE_URL_UNPOOLED", "TEST_DATABASE_URL"):
        configured = os.environ.get(variable) or local.get(variable)
        configured = str(configured or "").strip()
        if configured and candidate == _identity(configured):
            raise RuntimeError(f"O alvo P7.4 nao pode coincidir com {variable}.")
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
            require(
                connection.execute(text("SELECT current_database()" )).scalar_one()
                == url.database,
                "target database identity",
            )
            tables = connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            ).scalars().all()
            require(not tables, "empty public schema")
    finally:
        engine.dispose()
    return url.host or "postgresql", url.database or "p74"


def _commitment() -> dict:
    return {
        "total_limit": 1000.0,
        "total_committed": 920.0,
        "total_available": 80.0,
        "committed_percent": 92.0,
        "active_cards": 1,
        "cards": [{
            "card_id": 74,
            "name": "Cartao ficticio P74",
            "total_limit": 1000.0,
            "committed": 920.0,
            "available": 80.0,
            "committed_percent": 92.0,
            "current_invoice_amount": 0.0,
            "closing_date": None,
            "due_date": None,
            "invoice_status": None,
            "next_due_invoice_amount": 0.0,
            "next_due_date": None,
            "next_due_status": None,
        }],
    }


def _unusual(event_id: int) -> dict:
    return {
        "id": event_id,
        "description": "Evento ficticio P74",
        "amount": 500.0,
        "date": "2026-10-06",
        "category": "Categoria ficticia",
        "account": "Conta ficticia",
        "source": "manual",
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
    from services.notification_preference_service import notification_preference_service
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
                "('P74 Gate A', 'p74-gate-a@example.invalid', 'test-only') RETURNING id"
            )
        ).scalar_one()
        user_b = connection.execute(
            text(
                "INSERT INTO usuarios (usuario, email, senha) VALUES "
                "('P74 Gate B', 'p74-gate-b@example.invalid', 'test-only') RETURNING id"
            )
        ).scalar_one()

    require(
        all(notification_preference_service.get_effective(user_a).values()),
        "absence keeps every preference enabled",
    )
    notification_preference_service.update(user_a, {"unusual_expense": False})
    first = financial_notification_service.publish_from_insights(
        user_a,
        card_commitment=_commitment(),
        unusual_expenses=[_unusual(740)],
        reference=date(2026, 10, 6),
    )
    require(first.suppressed == 1, "disabled preference suppresses persistence")
    require(len(notification_service.list(user_a)) == 1, "other producer remains enabled")

    notification_preference_service.update(user_a, {"unusual_expense": True})
    financial_notification_service.publish_from_insights(
        user_a,
        card_commitment=_commitment(),
        unusual_expenses=[_unusual(740)],
        reference=date(2026, 10, 6),
    )
    require(len(notification_service.list(user_a)) == 1, "reactivation does not backfill")
    financial_notification_service.publish_from_insights(
        user_a,
        card_commitment=_commitment(),
        unusual_expenses=[_unusual(741)],
        reference=date(2026, 10, 6),
    )
    require(len(notification_service.list(user_a)) == 2, "reenabled producer creates future event")

    financial_notification_service.publish_from_insights(
        user_b,
        card_commitment=_commitment(),
        unusual_expenses=[_unusual(741)],
        reference=date(2026, 10, 6),
    )
    require(len(notification_service.list(user_b)) == 2, "default state and ownership are isolated")

    with engine.connect() as connection:
        require(
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == EXPECTED_HEAD,
            "Alembic head updated",
        )
        explicit = connection.execute(
            text(
                "SELECT preference_key, enabled FROM notification_preferences "
                "WHERE usuario_id=:user"
            ),
            {"user": user_a},
        ).all()
        require(explicit == [("unusual_expense", True)], "idempotent typed preference upsert")
        constraints = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid='notification_preferences'::regclass"
                )
            )
        }
        require(
            {"pk_notification_preferences", "ck_notification_preferences_key"}.issubset(constraints),
            "preference constraints",
        )
        suppression_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM notification_preference_suppressions "
                "WHERE usuario_id=:user"
            ),
            {"user": user_a},
        ).scalar_one()
        require(suppression_count == 1, "suppressed event ledger")
    print("P7.4 PostgreSQL preference gate passed; only fictional data was used.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarded P7.4 PostgreSQL preference gate")
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
