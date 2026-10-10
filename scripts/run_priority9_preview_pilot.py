from __future__ import annotations

import json
import os
import secrets
from datetime import date
from unittest.mock import patch

from sqlalchemy.engine import make_url

from database.connection import database_target_fingerprint, get_connection, get_database_url
from repositories.categoria_repo import listar_categorias_sistema
from services.auth_service import registrar
from services.budget_service import create_budget_service
from services.conta_service import criar_conta_service
from services.financial_alert_job_service import FinancialAlertJobRunner
from services.goal_service import add_goal_movement_service, create_goal_service
from services.periodic_summary_job_service import PeriodicSummaryJobRunner
from services.transacao_service import criar_transacao_service


REFERENCE = date(2026, 10, 10)
NAME = "P9-FINAL-20261010"
EMAIL = "p9-final-20261010@example.invalid"


def _assert_preview_target() -> str:
    if os.environ.get("APP_ENV", "").strip().casefold() != "preview":
        raise RuntimeError("O piloto exige APP_ENV=preview.")
    expected_host = os.environ.get("P9_EXPECTED_DATABASE_HOST_FRAGMENT", "").strip()
    host = make_url(get_database_url()).host or ""
    if not expected_host or expected_host.casefold() not in host.casefold():
        raise RuntimeError("O host configurado não corresponde ao Preview autorizado.")
    return database_target_fingerprint()


def _existing_user() -> int | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM usuarios WHERE usuario = ? OR email = ?",
            (NAME, EMAIL),
        ).fetchone()
        return int(row[0]) if row else None
    finally:
        conn.close()


def _prepare_user() -> int:
    if _existing_user() is not None:
        raise RuntimeError("Já existe resíduo do namespace do piloto.")
    os.environ["FINANCIAL_ALERTS_ENABLED"] = "false"
    user_id = registrar(NAME, EMAIL, secrets.token_urlsafe(24), "pessoal")
    try:
        categories = {str(row[2]): int(row[0]) for row in listar_categorias_sistema(user_id)}
        food_id = categories["food"]
        account = criar_conta_service("P9 Conta Sintética", "digital", 1000, user_id)
        account_id = int(account["id"])
        criar_transacao_service(
            85, "saida", food_id, "P9 orçamento 85%", "2026-10-02", user_id, account_id
        )
        criar_transacao_service(
            120, "entrada", categories["income"], "P9 resumo setembro",
            "2026-09-30", user_id, account_id,
        )
        create_budget_service(user_id, food_id, "2026-10", 100, today=REFERENCE)
        goal = create_goal_service(
            user_id, "P9 Meta Sintética", "Evidência descartável", 100, None,
            today=REFERENCE,
        )
        add_goal_movement_service(
            user_id, int(goal["id"]), "contribution", 50, "2026-10-02",
            "P9 marco 50%", "p9-final-goal-50", today=REFERENCE,
        )
    except Exception:
        _cleanup(user_id)
        raise
    return user_id


def _only_user(user_id: int):
    def loader(*, depois_de: int = 0, limite: int = 250) -> list[int]:
        del limite
        return [user_id] if depois_de < user_id else []

    return loader


def _run_jobs(user_id: int) -> dict:
    os.environ["PERIODIC_SUMMARY_JOBS_ENABLED"] = "true"
    os.environ["FINANCIAL_ALERTS_ENABLED"] = "true"
    loader = _only_user(user_id)
    with patch(
        "services.periodic_summary_job_service.listar_ids_usuarios_em_lote",
        side_effect=loader,
    ):
        summaries_first = PeriodicSummaryJobRunner().run_all(reference=REFERENCE)
        summaries_replay = PeriodicSummaryJobRunner().run_all(reference=REFERENCE)
    with patch(
        "services.financial_alert_job_service.listar_ids_usuarios_em_lote",
        side_effect=loader,
    ):
        alerts_first = FinancialAlertJobRunner().run(reference=REFERENCE)
        alerts_replay = FinancialAlertJobRunner().run(reference=REFERENCE)

    conn = get_connection()
    try:
        notification_count = int(conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE usuario_id = ?", (user_id,)
        ).fetchone()[0])
        ledger_count = int(conn.execute(
            "SELECT COUNT(*) FROM notification_dedupe_ledger WHERE usuario_id = ?",
            (user_id,),
        ).fetchone()[0])
        state_count = int(conn.execute(
            "SELECT COUNT(*) FROM financial_alert_states WHERE usuario_id = ?",
            (user_id,),
        ).fetchone()[0])
    finally:
        conn.close()

    return {
        "summaries_first": [item.public_dict() for item in summaries_first],
        "summaries_replay": [item.public_dict() for item in summaries_replay],
        "alerts_first": alerts_first.public_dict(),
        "alerts_replay": alerts_replay.public_dict(),
        "notifications": notification_count,
        "ledger": ledger_count,
        "financial_states": state_count,
    }


def _cleanup(user_id: int) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT usuario, email FROM usuarios WHERE id = ?", (user_id,)
        ).fetchone()
        if row != (NAME, EMAIL):
            raise RuntimeError("A identidade do piloto mudou; limpeza abortada.")
        deleted = {}
        for table in ("transacoes", "budgets", "contas", "categorias"):
            result = conn.execute(f"DELETE FROM {table} WHERE usuario_id = ?", (user_id,))
            deleted[table] = result.rowcount
        deleted["usuarios"] = conn.execute(
            "DELETE FROM usuarios WHERE id = ? AND usuario = ? AND email = ?",
            (user_id, NAME, EMAIL),
        ).rowcount
        if deleted["usuarios"] != 1:
            raise RuntimeError("O usuário sintético não foi removido exatamente uma vez.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return deleted


def main() -> int:
    fingerprint = _assert_preview_target()
    user_id: int | None = None
    evidence: dict = {"database_fingerprint": fingerprint, "reference": REFERENCE.isoformat()}
    try:
        user_id = _prepare_user()
        evidence["pilot_user_id"] = user_id
        evidence["jobs"] = _run_jobs(user_id)
    finally:
        os.environ["PERIODIC_SUMMARY_JOBS_ENABLED"] = "false"
        os.environ["FINANCIAL_ALERTS_ENABLED"] = "false"
        if user_id is not None:
            evidence["cleanup"] = _cleanup(user_id)
            evidence["residue_user"] = _existing_user() is not None
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
