"""P8.1 gate for the isolated disposable PostgreSQL database."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from tests.integration.notification_postgres_gate import _driver_url, require


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DATABASE = "nivra_p81_gate"
EXPECTED_HEAD = "c2d3e4f5a6b7"


def test_url_from_env() -> str:
    values = dotenv_values(ROOT / ".env")
    preview = os.environ.get("P65_PREVIEW_BRANCH_DATABASE_URL") or values.get("P65_PREVIEW_BRANCH_DATABASE_URL")
    raw = os.environ.get("P81_TEST_DATABASE_URL") or values.get("P81_TEST_DATABASE_URL")
    if not raw and preview:
        raw = make_url(str(preview)).set(
            drivername="postgresql+pg8000", database=EXPECTED_DATABASE, query={}
        ).render_as_string(hide_password=False)
    raw = str(raw or "").strip()
    url = make_url(raw) if raw else None
    if url is None or url.get_backend_name() != "postgresql":
        raise RuntimeError("P81_TEST_DATABASE_URL PostgreSQL é obrigatória.")
    if (url.database or "").casefold() != EXPECTED_DATABASE:
        raise RuntimeError("O gate exige o banco descartável nivra_p81_gate.")
    candidate = ((url.host or "").casefold(), (url.database or "").casefold())
    for variable in ("DATABASE_URL", "DATABASE_URL_UNPOOLED", "TEST_DATABASE_URL"):
        configured = str(os.environ.get(variable) or values.get(variable) or "").strip()
        if configured:
            other = make_url(configured)
            if candidate == ((other.host or "").casefold(), (other.database or "").casefold()):
                raise RuntimeError(f"O alvo P8.1 não pode coincidir com {variable}.")
    return raw


def run(raw: str) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["TEST_DATABASE_URL"] = _driver_url(raw)
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DATABASE_URL_UNPOOLED", None)

    from alembic import command
    from database.connection import dispose_engine, get_engine
    from database.migrations import get_alembic_config
    from services.budget_service import BudgetConflictError, create_budget_service, get_budget_service

    dispose_engine()
    config = get_alembic_config()
    command.upgrade(config, "b1c2d3e4f5a6")
    engine = get_engine()
    with engine.begin() as connection:
        user_a = connection.execute(text("INSERT INTO usuarios (usuario,email,senha) VALUES ('P81 A','p81-a@example.invalid','x') RETURNING id")).scalar_one()
        user_b = connection.execute(text("INSERT INTO usuarios (usuario,email,senha) VALUES ('P81 B','p81-b@example.invalid','x') RETURNING id")).scalar_one()
        category_a = connection.execute(text("INSERT INTO categorias (nome,usuario_id) VALUES ('Alimentação',:user) RETURNING id"), {"user": user_a}).scalar_one()
        category_b = connection.execute(text("INSERT INTO categorias (nome,usuario_id) VALUES ('Alimentação',:user) RETURNING id"), {"user": user_b}).scalar_one()
        legacy_id = connection.execute(text("INSERT INTO limites (categoria_id,valor,mes,usuario_id) VALUES (:category,800.25,'2026-10',:user) RETURNING id"), {"category": category_a, "user": user_a}).scalar_one()
    command.upgrade(config, "head")
    command.check(config)
    engine = get_engine()
    inspector = inspect(engine)
    require("budgets" in inspector.get_table_names() and "limites" not in inspector.get_table_names(), "single budget source")
    with engine.connect() as connection:
        migrated = connection.execute(text("SELECT id,periodo,limite FROM budgets WHERE id=:id"), {"id": legacy_id}).mappings().one()
        require(migrated["periodo"] == date(2026, 10, 1), "legacy period preserved")
        require(migrated["limite"] == Decimal("800.25"), "legacy precision preserved")
        numeric = next(column for column in inspector.get_columns("budgets") if column["name"] == "limite")
        require(getattr(numeric["type"], "scale", None) == 2, "numeric scale")

    barrier = threading.Barrier(8)

    def create_same(_index):
        barrier.wait(timeout=20)
        try:
            created = create_budget_service(user_b, category_b, "2026-10", Decimal("500.00"), today=date(2026, 10, 7))
            return f"created:{created['id']}"
        except BudgetConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(create_same, range(8)))
    created = [outcome for outcome in outcomes if outcome.startswith("created:")]
    require(len(created) == 1 and outcomes.count("conflict") == 7, "concurrent uniqueness")
    require(int(created[0].split(":", 1)[1]) > legacy_id, "legacy sequence advanced")
    require(get_budget_service(legacy_id, user_a, today=date(2026, 10, 7))["limit"] == Decimal("800.25"), "canonical read")
    try:
        get_budget_service(legacy_id, user_b, today=date(2026, 10, 7))
    except LookupError:
        pass
    else:
        raise AssertionError("ownership isolation")

    command.downgrade(config, "b1c2d3e4f5a6")
    with get_engine().connect() as connection:
        require(connection.execute(text("SELECT COUNT(*) FROM limites")).scalar_one() == 2, "downgrade preserves rows")
    command.upgrade(config, "head")
    command.check(config)
    with get_engine().connect() as connection:
        require(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == EXPECTED_HEAD, "Alembic head")
        require(connection.execute(text("SELECT COUNT(*) FROM budgets")).scalar_one() == 2, "re-upgrade preserves rows")
    dispose_engine()
    print("P8.1 PostgreSQL gate passed; only fictional data was used.")


def main() -> None:
    try:
        run(test_url_from_env())
    except Exception as exc:
        print(f"Gate stopped: {type(exc).__name__}; details suppressed.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
