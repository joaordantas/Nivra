"""P6.5 integration gate. Run explicitly; never included in SQLite unit discovery.

Usage: .venv/Scripts/python.exe -m tests.integration.lumi_postgres_gate --preflight
       .venv/Scripts/python.exe -m tests.integration.lumi_postgres_gate --execute
       .venv/Scripts/python.exe -m tests.integration.lumi_postgres_gate --resume
The second form migrates and writes ONLY to an empty, guarded test PostgreSQL.
Resume accepts ONLY the exact fictional fixture left after the migration smoke.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from scripts.lumi_postgres_gate_guard import (
    preflight_empty_database, prepare_test_environment, test_url_from_env,
)


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def verify_resume_fixture(raw: str) -> tuple[int, int, int, int]:
    """Separate read-only audit of the exact partial fixture left by the first run."""
    prepare_test_environment(raw)
    from sqlalchemy import text
    from database.connection import get_engine

    with get_engine().connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        require(conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() ==
                "b5c7d9e1f203", "resume at expected Alembic head")
        users = conn.execute(text("SELECT id, email FROM usuarios ORDER BY id")).all()
        require(len(users) == 2 and {row[1] for row in users} ==
                {"p65-gate-a@example.invalid", "p65-gate-b@example.invalid"},
                "resume contains only fictional users")
        user = next(row[0] for row in users if row[1] == "p65-gate-a@example.invalid")
        other = next(row[0] for row in users if row[1] == "p65-gate-b@example.invalid")
        rows = conn.execute(text(
            "SELECT id, status, execution_eligible FROM lumi_action_confirmations ORDER BY id"
        )).all()
        require(len(rows) == 2 and {row[1] for row in rows} == {"pending", "confirmed"}
                and all(not row[2] for row in rows), "resume contains only ineligible legacy confirmations")
        require(conn.execute(text("SELECT count(*) FROM transacoes")).scalar_one() == 0,
                "resume has no financial transactions")
        account = conn.execute(text("SELECT id FROM contas WHERE usuario_id=:user AND nome='Gate Account'"),
                               {"user": user}).scalar_one()
        category = conn.execute(text("SELECT id FROM categorias WHERE usuario_id=:user AND nome='Gate Category'"),
                                {"user": user}).scalar_one()
        require(conn.execute(text("SELECT count(*) FROM contas")).scalar_one() == 1 and
                conn.execute(text("SELECT count(*) FROM categorias")).scalar_one() == 1,
                "resume has only one fictional account and category")
        return user, other, account, category


def verify_final_state(raw: str) -> None:
    """Read-only economic and audit check after the successful test run."""
    prepare_test_environment(raw)
    from sqlalchemy import text
    from database.connection import get_engine

    with get_engine().connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        require(conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() ==
                "b5c7d9e1f203", "final migration head")
        users = conn.execute(text("SELECT id, email FROM usuarios")).all()
        require(len(users) == 2 and {row[1] for row in users} ==
                {"p65-gate-a@example.invalid", "p65-gate-b@example.invalid"},
                "final database contains only fictional users")
        user = next(row[0] for row in users if row[1] == "p65-gate-a@example.invalid")
        require(conn.execute(text("SELECT count(*) FROM transacoes")).scalar_one() == 7,
                "exactly seven authorized economic transactions")
        require(conn.execute(text(
            "SELECT count(*) FROM lumi_action_confirmations "
            "WHERE status='executed' AND executed_transaction_id IS NOT NULL "
            "AND executed_at IS NOT NULL AND usuario_id=:user"
        ), {"user": user}).scalar_one() == 7, "seven complete authorization audit links")
        require(conn.execute(text(
            "SELECT count(*) FROM transacoes t LEFT JOIN lumi_action_confirmations c "
            "ON c.executed_transaction_id=t.id WHERE c.id IS NULL OR t.usuario_id<>c.usuario_id"
        )).scalar_one() == 0, "no orphan or cross-user economic transaction")
        require(conn.execute(text(
            "SELECT count(*) FROM lumi_action_confirmations "
            "WHERE execution_eligible=false AND status IN ('pending', 'confirmed')"
        )).scalar_one() == 2, "legacy authorizations remain ineligible")
        print("Final PostgreSQL verification passed; read-only.")


def run(raw: str, *, resume: bool = False) -> None:
    prepare_test_environment(raw)
    from alembic import command
    from sqlalchemy import text
    from database.connection import get_engine
    from database.migrations import get_alembic_config
    from services.session_service import gerar_token, hash_token

    cfg = get_alembic_config()
    engine = get_engine()
    old_tokens = (gerar_token(), gerar_token())
    if resume:
        user, other, account, category = verify_resume_fixture(raw)
        with engine.begin() as conn:
            for status, token in zip(("pending", "confirmed"), old_tokens):
                conn.execute(text(
                    "UPDATE lumi_action_confirmations SET token_hash=:hash "
                    "WHERE usuario_id=:user AND status=:status AND execution_eligible=false"
                ), {"hash": hash_token(token), "user": user, "status": status})
    else:
        command.upgrade(cfg, "e9a2d6c3b4f1")
        with engine.begin() as conn:
            user = conn.execute(text(
                "INSERT INTO usuarios (usuario, email, senha) VALUES "
                "('P65 Gate A', 'p65-gate-a@example.invalid', 'test-only') RETURNING id"
            )).scalar_one()
            for status, token in zip(("pending", "confirmed"), old_tokens):
                conn.execute(text(
                    "INSERT INTO lumi_action_confirmations "
                    "(usuario_id, token_hash, action_type, payload_json, status, expira_em) "
                    "VALUES (:user, :hash, 'create_expense', '{}', :status, :expiry)"
                ), {"user": user, "hash": hash_token(token), "status": status,
                    "expiry": datetime.now(timezone.utc) + timedelta(hours=1)})
        command.upgrade(cfg, "head")
        command.check(cfg)
        with engine.connect() as conn:
            revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            require(revision == "b5c7d9e1f203", "upgrade head")
            require(conn.execute(text(
                "SELECT count(*) FROM lumi_action_confirmations WHERE execution_eligible = false"
            )).scalar_one() == 2, "legacy confirmations ineligible")
        command.downgrade(cfg, "-1")
        command.upgrade(cfg, "head")
        command.check(cfg)
        with engine.connect() as conn:
            require(conn.execute(text(
                "SELECT count(*) FROM lumi_action_confirmations WHERE execution_eligible = false"
            )).scalar_one() == 2, "downgrade/upgrade preserves legacy ineligibility")
            constraints = {row[0] for row in conn.execute(text(
                "SELECT conname FROM pg_constraint WHERE conrelid = 'lumi_action_confirmations'::regclass"
            ))}
            require({"ck_lumi_action_confirmations_execution", "ck_lumi_action_confirmations_status",
                     "uq_lumi_action_confirmations_executed_transaction_id"}.issubset(constraints),
                    "execution status/check/unique constraints present")

    from fastapi.testclient import TestClient
    from backend.main import app
    from tests.auth_support import authenticate_existing_user
    from services.lumi_action_confirmation_service import (
        criar_confirmacao_pendente, executar_acao_confirmada,
        LumiActionConfirmationStateError,
    )

    if not resume:
        with engine.begin() as conn:
            other = conn.execute(text(
                "INSERT INTO usuarios (usuario, email, senha) VALUES "
                "('P65 Gate B', 'p65-gate-b@example.invalid', 'test-only') RETURNING id"
            )).scalar_one()
            account = conn.execute(text(
                "INSERT INTO contas (nome, tipo, saldo_inicial, usuario_id) "
                "VALUES ('Gate Account', 'digital', 1000.00, :user) RETURNING id"
            ), {"user": user}).scalar_one()
            category = conn.execute(text(
                "INSERT INTO categorias (nome, usuario_id) VALUES ('Gate Category', :user) RETURNING id"
            ), {"user": user}).scalar_one()

    def proposal(kind="create_expense", amount="10.01", *, account_ref=None, category_ref=None):
        return criar_confirmacao_pendente(user, kind, {
            "amount": amount, "description": "P65 Gate", "date": "2026-09-22",
            "account": account_ref or {"id": account, "name": "Gate Account"},
            "category": category_ref or {"id": category, "name": "Gate Category"},
        }).confirmation_id

    def client_for(who):
        client = TestClient(app)
        headers = authenticate_existing_user(client, who)
        return client, headers

    def confirm(client, headers, token, **extras):
        started = time.monotonic()
        response = client.post("/api/lumi/actions/confirm", json={"confirmation_id": token, **extras}, headers=headers)
        return response, round((time.monotonic() - started) * 1000)

    client, headers = client_for(user)
    intruder, intruder_headers = client_for(other)
    try:
        for token in old_tokens:
            response, _ = confirm(client, headers, token)
            require(response.status_code == 409, "legacy confirmation cannot execute")

        token = proposal()
        response, expense_ms = confirm(client, headers, token)
        require(response.status_code == 200 and response.json()["status"] == "executed", "expense HTTP execution")
        expense_id = response.json()["transaction_id"]
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT t.valor, t.tipo, t.usuario_id, t.conta_id, t.categoria_id, t.data, t.comentario, "
                "c.status, c.executed_transaction_id, c.executed_at "
                "FROM transacoes t JOIN lumi_action_confirmations c ON c.executed_transaction_id=t.id "
                "WHERE t.id=:id"
            ), {"id": expense_id}).one()
            require(row[:7] == (Decimal("10.01"), "saida", user, account, category,
                                datetime(2026, 9, 22).date(), "P65 Gate"), "expense exact PostgreSQL values")
            require(row[7] == "executed" and row[8] == expense_id and row[9] is not None,
                    "expense audit link")
        replay, replay_ms = confirm(client, headers, token)
        require(replay.status_code == 200 and replay.json()["transaction_id"] == expense_id,
                "replay/lost response returns committed transaction")
        income_token = proposal("create_income", "2.34")
        income, income_ms = confirm(client, headers, income_token)
        require(income.status_code == 200, "income HTTP execution")
        with engine.connect() as conn:
            require(conn.execute(text("SELECT valor, tipo FROM transacoes WHERE id=:id"),
                                 {"id": income.json()["transaction_id"]}).one() == (Decimal("2.34"), "entrada"),
                    "income exact PostgreSQL values")
        history = client.get("/api/transactions")
        summary = client.get("/api/transactions/summary")
        require(history.status_code == 200 and len(history.json()) == 2, "ordinary transaction history")
        require(summary.status_code == 200 and summary.json()["saidas"] == 10.01
                and summary.json()["entradas"] == 2.34, "ordinary financial summary")
        accounts = client.get("/api/accounts")
        require(accounts.status_code == 200 and
                next(item for item in accounts.json() if item["id"] == account)["saldo_atual"] == 992.33,
                "ordinary account balance reflects expense and income")
        insights = client.get("/api/insights", params={"data_inicio": "2026-09-01", "data_fim": "2026-09-30"})
        require(insights.status_code == 200, "ordinary financial insights endpoint")

        private_token = proposal()
        require(confirm(intruder, intruder_headers, private_token)[0].status_code == 404,
                "cross-user token concealed")
        require(confirm(client, headers, private_token)[0].status_code == 200,
                "owner can still execute after cross-user attempt")
        own = proposal()
        require(confirm(client, {}, own)[0].status_code == 403, "CSRF required")
        for extra in ({"amount": "999.00"}, {"usuario_id": other},
                      {"account": {"id": 999}}, {"category": {"id": 999}},
                      {"description": "Tampered"}, {"date": "2026-09-23"},
                      {"action_type": "create_income"}):
            require(confirm(client, headers, own, **extra)[0].status_code == 422,
                    "frontend payload cannot override snapshot: " + next(iter(extra)))
        cancelled = proposal()
        cancel = client.post("/api/lumi/actions/cancel", json={"confirmation_id": cancelled}, headers=headers)
        require(cancel.status_code == 200 and confirm(client, headers, cancelled)[0].status_code == 409,
                "cancelled proposal cannot execute")
        expired = proposal()
        with engine.begin() as conn:
            conn.execute(text("UPDATE lumi_action_confirmations SET expira_em=:now WHERE token_hash=:hash"),
                         {"now": datetime.now(timezone.utc), "hash": hash_token(expired)})
        require(confirm(client, headers, expired)[0].status_code == 410, "expiry boundary blocks execution")

        renamed_account = proposal()
        with engine.begin() as conn:
            conn.execute(text("UPDATE contas SET nome='Changed Account' WHERE id=:id"), {"id": account})
        require(confirm(client, headers, renamed_account)[0].status_code == 409,
                "account changed after proposal blocks execution")
        with engine.begin() as conn:
            conn.execute(text("UPDATE contas SET nome='Gate Account' WHERE id=:id"), {"id": account})
        renamed_category = proposal()
        with engine.begin() as conn:
            conn.execute(text("UPDATE categorias SET nome='Changed Category' WHERE id=:id"), {"id": category})
        require(confirm(client, headers, renamed_category)[0].status_code == 409,
                "category changed after proposal blocks execution")
        with engine.begin() as conn:
            conn.execute(text("UPDATE categorias SET nome='Gate Category' WHERE id=:id"), {"id": category})
            disposable_account = conn.execute(text(
                "INSERT INTO contas (nome, tipo, saldo_inicial, usuario_id) "
                "VALUES ('Disposable Account', 'digital', 0, :user) RETURNING id"
            ), {"user": user}).scalar_one()
            disposable_category = conn.execute(text(
                "INSERT INTO categorias (nome, usuario_id) VALUES ('Disposable Category', :user) RETURNING id"
            ), {"user": user}).scalar_one()
        removed_account = proposal(account_ref={"id": disposable_account, "name": "Disposable Account"})
        removed_category = proposal(category_ref={"id": disposable_category, "name": "Disposable Category"})
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM contas WHERE id=:id"), {"id": disposable_account})
            conn.execute(text("DELETE FROM categorias WHERE id=:id"), {"id": disposable_category})
        require(confirm(client, headers, removed_account)[0].status_code == 409,
                "removed account blocks execution")
        require(confirm(client, headers, removed_category)[0].status_code == 409,
                "removed category blocks execution")

        before = len(client.get("/api/transactions").json())
        rollback_token = proposal()
        with patch("services.lumi_action_confirmation_service.finalizar_execucao", side_effect=RuntimeError("gate fault")):
            try:
                executar_acao_confirmada(rollback_token, user)
            except RuntimeError:
                pass
            else:
                raise AssertionError("rollback fault did not fire")
        with engine.connect() as conn:
            state = conn.execute(text(
                "SELECT status, executed_transaction_id FROM lumi_action_confirmations WHERE token_hash=:hash"
            ), {"hash": hash_token(rollback_token)}).one()
            require(state == ("pending", None), "failed transaction leaves confirmation pending")
        require(len(client.get("/api/transactions").json()) == before, "failed transaction leaves no row")
        require(confirm(client, headers, rollback_token)[0].status_code == 200, "retry after rollback")

        for workers in (2, 5):
            concurrent_token = proposal()
            clients = [client_for(user) for _ in range(workers)]
            try:
                started = time.monotonic()
                barrier = threading.Barrier(workers)
                def simultaneous(pair):
                    barrier.wait(timeout=10)
                    return confirm(pair[0], pair[1], concurrent_token)[0]
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    results = list(executor.map(simultaneous, clients))
                elapsed = round((time.monotonic() - started) * 1000)
                ids = [result.json().get("transaction_id") for result in results if result.status_code == 200]
                require(len(ids) == workers and len(set(ids)) == 1,
                        f"{workers} concurrent HTTP confirmations return one transaction ({elapsed} ms)")
                with engine.connect() as conn:
                    count = conn.execute(text(
                        "SELECT count(*) FROM transacoes WHERE id=:id"
                    ), {"id": ids[0]}).scalar_one()
                    require(count == 1, f"{workers} concurrent confirmations persist one transaction")
            finally:
                for entry, _ in clients:
                    entry.close()

        offline = proposal()
        with patch("services.groq_lumi_provider.GroqProvider.create_response", side_effect=AssertionError("Groq called")) as groq, \
             patch("services.openai_lumi_provider.OpenAIProvider.create_response", side_effect=AssertionError("OpenAI called")) as openai:
            require(confirm(client, headers, offline)[0].status_code == 200,
                    "provider offline; zero provider calls during confirmation")
            groq.assert_not_called()
            openai.assert_not_called()
        print(json.dumps({"confirmation_ms": expense_ms, "replay_ms": replay_ms,
                          "income_ms": income_ms, "provider_calls_during_confirmation": 0}))
    finally:
        client.close()
        intruder.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarded P6.5 PostgreSQL integration gate")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true", help="read-only safety and empty-database check")
    group.add_argument("--execute", action="store_true", help="migrate and write fictional test data")
    group.add_argument("--resume-preflight", action="store_true", help="read-only audit of exact partial test fixture")
    group.add_argument("--resume", action="store_true", help="resume only the exact fictional fixture after migration smoke")
    group.add_argument("--verify-final", action="store_true", help="read-only post-run economic and audit check")
    args = parser.parse_args()
    try:
        raw = test_url_from_env()
        if args.resume or args.resume_preflight or args.verify_final:
            from sqlalchemy.engine import make_url
            url = make_url(raw)
            print(f"Guarded fixture audit: host={url.host}, database={url.database}; credentials hidden")
            if args.resume_preflight:
                verify_resume_fixture(raw)
                print("Read-only fixture audit passed; no writes made.")
            elif args.verify_final:
                verify_final_state(raw)
            else:
                run(raw, resume=True)
        else:
            host, database = preflight_empty_database(raw)
            print(f"Disposable PostgreSQL confirmed: host={host}, database={database}; credentials hidden")
            if args.execute:
                run(raw)
            else:
                print("Read-only preflight passed; no writes made.")
    except Exception as exc:
        # psycopg/SQLAlchemy connection exceptions may embed URLs. Never print them.
        if isinstance(exc, (RuntimeError, AssertionError)):
            print(f"Gate stopped: {exc}")
        else:
            print(f"Gate stopped: {type(exc).__name__}; details suppressed to protect credentials.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
