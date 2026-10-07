"""P7.5 gate for the isolated disposable PostgreSQL database."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import make_url

from tests.integration.notification_postgres_gate import _driver_url, require


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DATABASE = "nivra_p75_gate"
EXPECTED_HEAD = "a0b1c2d3e4f5"


def test_url_from_env() -> str:
    values = dotenv_values(ROOT / ".env")
    preview = os.environ.get("P65_PREVIEW_BRANCH_DATABASE_URL") or values.get(
        "P65_PREVIEW_BRANCH_DATABASE_URL"
    )
    raw = os.environ.get("P75_TEST_DATABASE_URL") or values.get("P75_TEST_DATABASE_URL")
    if not raw and preview:
        raw = make_url(str(preview)).set(
            drivername="postgresql+pg8000", database=EXPECTED_DATABASE, query={}
        ).render_as_string(hide_password=False)
    raw = str(raw or "").strip()
    url = make_url(raw) if raw else None
    if url is None or url.get_backend_name() != "postgresql":
        raise RuntimeError("P75_TEST_DATABASE_URL PostgreSQL é obrigatória.")
    if (url.database or "").casefold() != EXPECTED_DATABASE:
        raise RuntimeError("O gate exige o banco descartável nivra_p75_gate.")
    for variable in ("DATABASE_URL", "DATABASE_URL_UNPOOLED", "TEST_DATABASE_URL"):
        configured = str(os.environ.get(variable) or values.get(variable) or "").strip()
        if configured and make_url(configured).database == url.database:
            raise RuntimeError(f"O alvo P7.5 não pode coincidir com {variable}.")
    return raw


def run(raw: str) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["TEST_DATABASE_URL"] = _driver_url(raw)
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DATABASE_URL_UNPOOLED", None)

    from alembic import command
    from database.connection import dispose_engine, get_engine
    from database.migrations import get_alembic_config
    from services.notification_preference_service import notification_preference_service
    from services.notification_service import notification_service
    from services.periodic_financial_summary_service import periodic_financial_summary_service

    dispose_engine()
    config = get_alembic_config()
    command.upgrade(config, "head")
    command.check(config)
    engine = get_engine()
    with engine.begin() as connection:
        user_a = connection.execute(text(
            "INSERT INTO usuarios (usuario,email,senha) VALUES "
            "('P75 A','p75-a@example.invalid','test') RETURNING id"
        )).scalar_one()
        user_b = connection.execute(text(
            "INSERT INTO usuarios (usuario,email,senha) VALUES "
            "('P75 B','p75-b@example.invalid','test') RETURNING id"
        )).scalar_one()
        categories = {}
        for user_id in (user_a, user_b):
            categories[user_id] = connection.execute(text(
                "INSERT INTO categorias (nome,usuario_id) VALUES ('Alimentação',:user) RETURNING id"
            ), {"user": user_id}).scalar_one()
            account = connection.execute(text(
                "INSERT INTO contas (nome,tipo,saldo_inicial,usuario_id,principal) "
                "VALUES ('Conta','digital',0,:user,FALSE) RETURNING id"
            ), {"user": user_id}).scalar_one()
            connection.execute(text(
                "INSERT INTO transacoes (valor,tipo,categoria_id,comentario,data,usuario_id,conta_id) "
                "VALUES (100,'saida',:category,'Fictício','2026-09-30',:user,:account)"
            ), {"category": categories[user_id], "user": user_id, "account": account})

    workers = 8
    barrier = threading.Barrier(workers)

    def publish(_):
        barrier.wait(timeout=15)
        return periodic_financial_summary_service.generate_weekly_summary(
            user_a, reference=date(2026, 10, 6)
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        outcomes = list(executor.map(publish, range(workers)))
    require(all(item.outcome == "delivered_or_deduplicated" for item in outcomes), "concurrent calls")
    require(len(notification_service.list(user_a)) == 1, "concurrent deduplication")
    periodic_financial_summary_service.generate_weekly_summary(user_b, reference=date(2026, 10, 6))
    require(len(notification_service.list(user_b)) == 1, "multi-user isolation")

    notification_preference_service.update(user_a, {"monthly_summary": False})
    suppressed = periodic_financial_summary_service.generate_monthly_summary(
        user_a, reference=date(2026, 10, 6)
    )
    notification_preference_service.update(user_a, {"monthly_summary": True})
    replay = periodic_financial_summary_service.generate_monthly_summary(
        user_a, reference=date(2026, 10, 6)
    )
    require(suppressed.outcome == replay.outcome == "suppressed", "ledger prevents backfill")

    with engine.connect() as connection:
        require(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == EXPECTED_HEAD, "Alembic head")
        require(connection.execute(text(
            "SELECT COUNT(*) FROM notification_preference_suppressions WHERE usuario_id=:user"
        ), {"user": user_a}).scalar_one() == 1, "suppression ledger")
        require(connection.execute(text(
            "SELECT COUNT(*) FROM notifications WHERE usuario_id=:user AND chave_dedupe='weekly_summary:2026-09-28'"
        ), {"user": user_a}).scalar_one() == 1, "deterministic dedupe key")
    dispose_engine()
    command.downgrade(config, "f9a0b1c2d3e4")
    command.upgrade(config, "head")
    command.check(config)
    with get_engine().connect() as connection:
        require(
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == EXPECTED_HEAD,
            "downgrade and re-upgrade",
        )
    print("P7.5 PostgreSQL gate passed; only fictional data was used.")


def main() -> None:
    try:
        run(test_url_from_env())
    except Exception as exc:
        print(f"Gate stopped: {type(exc).__name__}; details suppressed.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
