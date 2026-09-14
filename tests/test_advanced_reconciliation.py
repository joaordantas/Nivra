import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from database.connection import get_connection
from services.open_finance_reconciliation_service import (
    ReconciliationConflictError,
    ReconciliationNotFoundError,
    confirmar_conciliacao_service,
    detectar_candidatos_conciliacao_service,
    normalizar_descricao,
)
from tests.auth_support import csrf_headers, register_client
from tests.db_support import remove_test_database, reset_test_database
from tests.test_open_finance_sync import FakeSyncProvider, ITEM_A


class AdvancedReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_test_database()
        self.a = TestClient(app)
        self.b = TestClient(app)
        self.user_a = register_client(self.a, "Reconciliation A", "reconciliation-a@example.com")
        register_client(self.b, "Reconciliation B", "reconciliation-b@example.com")
        self.provider = FakeSyncProvider(self.user_a["id"])
        self.provider_patch = patch(
            "services.open_finance_service.get_open_finance_provider",
            return_value=self.provider,
        )
        self.provider_patch.start()
        completed = self.a.post(
            "/api/open-finance/connections/complete",
            headers=csrf_headers(self.a),
            json={"item_id": ITEM_A},
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        self.connection_id = completed.json()["id"]
        self.assertEqual(self.sync().status_code, 200)
        external = self.a.get(
            f"/api/open-finance/connections/{self.connection_id}/accounts"
        ).json()[0]
        created = self.a.post(
            f"/api/open-finance/external-accounts/{external['id']}/nivra-account",
            headers=csrf_headers(self.a),
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.account_id = created.json()["conta_nivra_id"]

    def tearDown(self) -> None:
        self.provider_patch.stop()
        self.a.close()
        self.b.close()
        remove_test_database()

    def sync(self):
        return self.a.post(
            f"/api/open-finance/connections/{self.connection_id}/sync",
            headers=csrf_headers(self.a),
        )

    def manual(self, *, amount=149.90, direction="saida", date="2026-09-02", description="Mercado manual", account_id=None):
        response = self.a.post(
            "/api/transactions",
            headers=csrf_headers(self.a),
            json={
                "valor": amount,
                "tipo": direction,
                "categoria_id": None,
                "comentario": description,
                "data": date,
                "conta_id": account_id or self.account_id,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def suggestions(self):
        response = self.a.get("/api/transactions/reconciliation/suggestions")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def market_suggestion(self):
        return next(item for item in self.suggestions() if item["descricao"] == "Mercado")

    def test_matching_score_description_and_date_window(self) -> None:
        self.assertEqual(normalizar_descricao("  COMPRA MCDÔNALD'S 123  "), "mcdonald")
        manual = self.manual(description="MERCADO!!!")
        suggestion = self.market_suggestion()
        candidate = suggestion["candidatos"][0]
        self.assertEqual(candidate["transacao_nivra_id"], manual["id"])
        self.assertEqual(candidate["confianca"], "alta")
        self.assertIn("mesmo_dia", candidate["motivos"])
        self.assertIn("descricao_semelhante", candidate["motivos"])

        rejected = self.a.post(
            f"/api/transactions/bank/{suggestion['transacao_bancaria_id']}/reconciliation/{manual['id']}/reject",
            headers=csrf_headers(self.a),
        )
        self.assertEqual(rejected.status_code, 200, rejected.text)
        near = self.manual(date="2026-09-04", description="Nome diferente")
        near_candidate = self.market_suggestion()["candidatos"][0]
        self.assertEqual(near_candidate["transacao_nivra_id"], near["id"])
        self.assertEqual(near_candidate["confianca"], "baixa")

    def test_value_direction_account_and_date_must_be_compatible(self) -> None:
        other_account = self.a.post(
            "/api/accounts",
            headers=csrf_headers(self.a),
            json={"nome": "Outra", "tipo": "digital", "saldo_inicial": 0},
        ).json()
        self.manual(amount=150)
        self.manual(direction="entrada")
        self.manual(account_id=other_account["id"])
        self.manual(date="2026-09-05")
        self.assertFalse(any(item["descricao"] == "Mercado" for item in self.suggestions()))

    def test_ambiguous_choice_confirmation_and_economic_deduplication(self) -> None:
        first = self.manual(description="Mercado A")
        second = self.manual(description="Mercado B")
        suggestion = self.market_suggestion()
        self.assertTrue(suggestion["ambigua"])
        self.assertEqual(len(suggestion["candidatos"]), 2)

        legacy = self.a.post(
            f"/api/transactions/bank/{suggestion['transacao_bancaria_id']}/reconciliation/confirm",
            headers=csrf_headers(self.a),
        )
        self.assertEqual(legacy.status_code, 409, legacy.text)
        confirmed = self.a.post(
            f"/api/transactions/bank/{suggestion['transacao_bancaria_id']}/reconciliation/{first['id']}/confirm",
            headers=csrf_headers(self.a),
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        rows = self.a.get("/api/transactions").json()
        self.assertEqual(len(rows), 3)
        self.assertTrue(next(row for row in rows if row["id"] == first["id"] and row["origem"] == "manual")["conciliada_com_banco"])
        self.assertIsNotNone(next(row for row in rows if row["id"] == second["id"] and row["origem"] == "manual"))
        self.assertEqual(self.a.get("/api/transactions/summary").json()["saidas"], 299.8)

    def test_rejection_and_detection_are_idempotent_across_resync(self) -> None:
        manual = self.manual()
        suggestion = self.market_suggestion()
        rejected = self.a.post(
            f"/api/transactions/bank/{suggestion['transacao_bancaria_id']}/reconciliation/{manual['id']}/reject",
            headers=csrf_headers(self.a),
        )
        self.assertEqual(rejected.status_code, 200, rejected.text)
        self.assertEqual(self.sync().status_code, 200)
        detectar_candidatos_conciliacao_service(self.user_a["id"])
        detectar_candidatos_conciliacao_service(self.user_a["id"])
        self.assertFalse(any(item["descricao"] == "Mercado" for item in self.suggestions()))
        conn = get_connection()
        try:
            pairs = conn.execute(
                "SELECT COUNT(*) FROM correspondencias_conciliacao WHERE transacao_nivra_id = ?",
                (manual["id"],),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(pairs, 1)

    def test_batch_only_confirms_unique_high_confidence_and_enforces_ownership(self) -> None:
        manual = self.manual(description="Mercado")
        suggestion = self.market_suggestion()
        forbidden = self.b.post(
            f"/api/transactions/bank/{suggestion['transacao_bancaria_id']}/reconciliation/{manual['id']}/confirm",
            headers=csrf_headers(self.b),
        )
        missing_csrf = self.a.post("/api/transactions/reconciliation/confirm-high-confidence")
        self.assertEqual(forbidden.status_code, 404, forbidden.text)
        self.assertEqual(missing_csrf.status_code, 403, missing_csrf.text)
        batch = self.a.post(
            "/api/transactions/reconciliation/confirm-high-confidence",
            headers=csrf_headers(self.a),
        )
        self.assertEqual(batch.status_code, 200, batch.text)
        self.assertEqual(batch.json(), {"confirmadas": 1, "solicitadas": 1})

    def test_concurrent_confirmation_has_one_final_decision(self) -> None:
        manual = self.manual(description="Mercado")
        suggestion = self.market_suggestion()
        bank_id = suggestion["transacao_bancaria_id"]

        def confirm():
            try:
                return confirmar_conciliacao_service(self.user_a["id"], bank_id, manual["id"])["status"]
            except (ReconciliationConflictError, ReconciliationNotFoundError):
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: confirm(), range(2)))
        self.assertEqual(results.count("conciliada"), 1)
        conn = get_connection()
        try:
            confirmed = conn.execute(
                "SELECT COUNT(*) FROM correspondencias_conciliacao WHERE status = 'confirmada'",
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(confirmed, 1)

    def test_financial_change_reopens_but_description_change_does_not(self) -> None:
        manual = self.manual(description="Mercado")
        suggestion = self.market_suggestion()
        confirm = self.a.post(
            f"/api/transactions/bank/{suggestion['transacao_bancaria_id']}/reconciliation/{manual['id']}/confirm",
            headers=csrf_headers(self.a),
        )
        self.assertEqual(confirm.status_code, 200, confirm.text)
        self.provider.transactions["external-account-1"][1] = replace(
            self.provider.transactions["external-account-1"][1], description="Mercado atualizado"
        )
        self.assertEqual(self.sync().status_code, 200)
        self.assertTrue(next(row for row in self.a.get("/api/transactions").json() if row["id"] == manual["id"] and row["origem"] == "manual")["conciliada_com_banco"])

        self.provider.transactions["external-account-1"][1] = replace(
            self.provider.transactions["external-account-1"][1], amount=150
        )
        self.assertEqual(self.sync().status_code, 200)
        self.assertFalse(next(row for row in self.a.get("/api/transactions").json() if row["id"] == manual["id"] and row["origem"] == "manual")["conciliada_com_banco"])

    def test_removed_bank_transaction_preserves_manual_record(self) -> None:
        manual = self.manual(description="Mercado")
        suggestion = self.market_suggestion()
        self.a.post(
            f"/api/transactions/bank/{suggestion['transacao_bancaria_id']}/reconciliation/{manual['id']}/confirm",
            headers=csrf_headers(self.a),
        )
        self.provider.transactions["external-account-1"] = [
            self.provider.transactions["external-account-1"][0]
        ]
        self.assertEqual(self.sync().status_code, 200)
        rows = self.a.get("/api/transactions").json()
        self.assertTrue(any(row["id"] == manual["id"] and row["origem"] == "manual" for row in rows))
        self.assertFalse(any(row["comentario"] == "Mercado" and row["origem"] == "open_finance" for row in rows))
        conn = get_connection()
        try:
            archived = conn.execute(
                "SELECT removida_em, transacao_nivra_id FROM transacoes_bancarias WHERE id = ?",
                (suggestion["transacao_bancaria_id"],),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(archived[0])
        self.assertIsNone(archived[1])


if __name__ == "__main__":
    unittest.main()
