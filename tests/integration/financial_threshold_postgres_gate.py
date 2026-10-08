"""P7.7 gate for the isolated disposable PostgreSQL database."""

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
EXPECTED_DATABASE = "nivra_p77_gate"
EXPECTED_HEAD = "f5a6b7c8d9e0"


def test_url_from_env() -> str:
    values = dotenv_values(ROOT / ".env")
    preview = os.environ.get("P65_PREVIEW_BRANCH_DATABASE_URL") or values.get(
        "P65_PREVIEW_BRANCH_DATABASE_URL"
    )
    raw = os.environ.get("P77_TEST_DATABASE_URL") or values.get("P77_TEST_DATABASE_URL")
    if not raw and preview:
        raw = make_url(str(preview)).set(
            drivername="postgresql+pg8000",
            database=EXPECTED_DATABASE,
            query={},
        ).render_as_string(hide_password=False)
    raw = str(raw or "").strip()
    url = make_url(raw) if raw else None
    if url is None or url.get_backend_name() != "postgresql":
        raise RuntimeError("P77_TEST_DATABASE_URL PostgreSQL é obrigatória.")
    if (url.database or "").casefold() != EXPECTED_DATABASE:
        raise RuntimeError("O gate exige o banco descartável nivra_p77_gate.")
    return raw


def run(raw: str) -> None:
    os.environ["APP_ENV"] = "test"
    os.environ["TEST_DATABASE_URL"] = _driver_url(raw)
    os.environ["FINANCIAL_ALERTS_ENABLED"] = "true"
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DATABASE_URL_UNPOOLED", None)

    from alembic import command
    from database.connection import dispose_engine, get_engine
    from database.migrations import get_alembic_config
    from services.budget_service import create_budget_service
    from services.categoria_service import criar_categoria_service
    from services.conta_service import criar_conta_service
    from services.financial_alert_job_service import FinancialAlertJobRunner
    from services.financial_threshold_alert_service import financial_threshold_alert_service
    from services.goal_service import add_goal_movement_service, create_goal_service
    from services.notification_service import notification_service
    from services.transacao_service import criar_transacao_service

    dispose_engine()
    config = get_alembic_config()
    command.upgrade(config, "head")
    command.check(config)
    engine = get_engine()
    inspector = inspect(engine)
    require("financial_alert_states" in inspector.get_table_names(), "alert state table")
    require(any(
        item["name"] == "ix_financial_alert_states_user_kind_period"
        for item in inspector.get_indexes("financial_alert_states")
    ), "alert state index")

    with engine.begin() as connection:
        user_id = connection.execute(text(
            "INSERT INTO usuarios (usuario,email,senha) "
            "VALUES ('P77','p77@example.invalid','x') RETURNING id"
        )).scalar_one()
        transactions_before = connection.execute(text("SELECT COUNT(*) FROM transacoes")).scalar_one()

    category = criar_categoria_service("Alimentação P77", user_id)
    account = criar_conta_service("Conta P77", "digital", 1000, user_id)
    criar_transacao_service(
        120, "saida", category["id"], "Evento fictício", "2026-10-07", user_id, account["id"]
    )
    transactions_after_fact = transactions_before + 1
    create_budget_service(
        user_id, category["id"], "2026-10", Decimal("100"), today=date(2026, 10, 7)
    )
    goal = create_goal_service(
        user_id, "Meta P77", None, Decimal("100"), None, today=date(2026, 10, 7)
    )
    add_goal_movement_service(
        user_id, goal["id"], "contribution", Decimal("100"), "2026-10-07",
        None, "p77-goal", today=date(2026, 10, 7)
    )
    require(
        {item["tipo"] for item in notification_service.list(user_id, limit=100)}
        == {"budget_alert", "goal_alert"},
        "canonical producers",
    )

    barrier = threading.Barrier(8)

    def reconcile(_index: int):
        barrier.wait(timeout=20)
        return financial_threshold_alert_service.evaluate_user(
            user_id, reference=date(2026, 10, 7), baseline_missing=True
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(reconcile, range(8)))
    require(len(notification_service.list(user_id, limit=100)) == 2, "concurrent dedupe")

    runner_barrier = threading.Barrier(8)

    def run_job(_index: int):
        runner_barrier.wait(timeout=20)
        return FinancialAlertJobRunner().run(reference=date(2026, 10, 7), batch_size=50)

    with ThreadPoolExecutor(max_workers=8) as executor:
        job_results = list(executor.map(run_job, range(8)))
    require(sum(item.counters.processed for item in job_results) == 1, "daily job lease")

    with engine.connect() as connection:
        require(
            connection.execute(text("SELECT COUNT(*) FROM transacoes")).scalar_one()
            == transactions_after_fact,
            "no financial side effect",
        )
        notification_count = connection.execute(text("SELECT COUNT(*) FROM notifications")).scalar_one()

    command.downgrade(config, "d3e4f5a6b7c8")
    with get_engine().connect() as connection:
        require(
            connection.execute(text("SELECT COUNT(*) FROM notifications")).scalar_one()
            == notification_count,
            "downgrade preserves notifications",
        )
    command.upgrade(config, "head")
    command.check(config)
    with get_engine().connect() as connection:
        require(
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == EXPECTED_HEAD,
            "Alembic head",
        )
    dispose_engine()
    print("P7.7 PostgreSQL gate passed; only fictional data was used.")


def main() -> None:
    try:
        run(test_url_from_env())
    except Exception as exc:
        print(f"Gate stopped: {type(exc).__name__}; details suppressed.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
