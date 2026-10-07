import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError

from tests.db_support import remove_test_database, reset_test_database

from database.connection import get_connection
from services.budget_service import (
    BudgetConflictError,
    create_budget_service,
    delete_budget_service,
    get_budget_service,
    list_budgets_service,
    normalize_money,
    parse_period,
    update_budget_service,
)
from services.cartao_service import criar_cartao_service, criar_compra_service, pagar_fatura_service
from services.categoria_service import criar_categoria_service, deletar_categoria_service
from services.conta_service import criar_conta_service
from services.parcelamento_service import criar_parcelamento_service
from services.transacao_service import criar_transacao_service
from services.transferencia_service import criar_transferencia_service


REFERENCE = date(2026, 10, 7)


class BudgetDomainTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        conn = get_connection()
        conn.execute("INSERT INTO usuarios (id,usuario,email,senha) VALUES (1,'A','a@example.com','x')")
        conn.execute("INSERT INTO usuarios (id,usuario,email,senha) VALUES (2,'B','b@example.com','x')")
        conn.commit()
        conn.close()
        self.category = criar_categoria_service("Alimentação", 1)
        self.other_category = criar_categoria_service("Alimentação", 2)
        self.account = criar_conta_service("Conta A", "digital", 1000, 1)
        self.other_account = criar_conta_service("Conta B", "digital", 1000, 2)

    def tearDown(self):
        remove_test_database()

    def create(self, limit="800.00", category_id=None, user_id=1, period="2026-10"):
        return create_budget_service(
            user_id, category_id or self.category["id"], period, limit, today=REFERENCE
        )

    def test_create_uses_stable_id_decimal_and_zero_spend(self):
        budget = self.create("800.25")
        self.assertIsInstance(budget["id"], int)
        self.assertEqual(budget["period"], "2026-10")
        self.assertEqual(budget["limit"], Decimal("800.25"))
        self.assertEqual(budget["spent"], Decimal("0.00"))
        self.assertEqual(budget["remaining"], Decimal("800.25"))
        self.assertEqual(budget["usage_percentage"], Decimal("0.00"))

    def test_money_and_period_validation(self):
        self.assertEqual(normalize_money("10.005"), Decimal("10.01"))
        for value in ("0", "-1", "NaN", "Infinity", "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_money(value)
        for value in ("outubro", "2026-1", "2026-13", "2026-10-01"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_period(value)

    def test_category_must_exist_and_belong_to_user(self):
        with self.assertRaisesRegex(ValueError, "Categoria não encontrada"):
            self.create(category_id=999)
        with self.assertRaisesRegex(ValueError, "Categoria não encontrada"):
            self.create(category_id=self.other_category["id"])

    def test_income_and_transfer_system_categories_are_rejected(self):
        conn = get_connection()
        conn.execute("INSERT INTO categorias (nome,usuario_id,chave_sistema) VALUES ('Renda',1,'income')")
        income_id = int(conn.execute("SELECT id FROM categorias WHERE chave_sistema='income'").fetchone()[0])
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(ValueError, "categoria de despesa"):
            self.create(category_id=income_id)

    def test_duplicate_is_rejected_and_concurrent_create_has_one_winner(self):
        self.create()
        with self.assertRaises(BudgetConflictError):
            self.create()
        category = criar_categoria_service("Mercado", 1)
        barrier = threading.Barrier(2)

        def attempt(_index):
            barrier.wait(timeout=10)
            try:
                create_budget_service(1, category["id"], "2026-10", "50", today=REFERENCE)
                return "created"
            except BudgetConflictError:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(attempt, range(2)))
        self.assertEqual(sorted(outcomes), ["conflict", "created"])

    def test_list_get_update_delete_and_multiuser_isolation(self):
        first = self.create()
        second = create_budget_service(2, self.other_category["id"], "2026-10", "900", today=REFERENCE)
        self.assertEqual([item["id"] for item in list_budgets_service(1, "2026-10", today=REFERENCE)], [first["id"]])
        with self.assertRaises(LookupError):
            get_budget_service(second["id"], 1, today=REFERENCE)
        updated = update_budget_service(first["id"], 1, "950.35", today=REFERENCE)
        self.assertEqual(updated["id"], first["id"])
        self.assertEqual(updated["limit"], Decimal("950.35"))
        self.assertFalse(delete_budget_service(second["id"], 1))
        self.assertTrue(delete_budget_service(first["id"], 1))
        with self.assertRaises(LookupError):
            get_budget_service(first["id"], 1, today=REFERENCE)

    def test_spent_remaining_and_percentages_below_equal_and_above_limit(self):
        budget = self.create("100")
        criar_transacao_service(50, "saida", self.category["id"], "A", "2026-10-01", 1, self.account["id"])
        state = get_budget_service(budget["id"], 1, today=REFERENCE)
        self.assertEqual((state["spent"], state["remaining"], state["usage_percentage"]), (Decimal("50.00"), Decimal("50.00"), Decimal("50.00")))
        criar_transacao_service(50, "saida", self.category["id"], "B", "2026-10-07", 1, self.account["id"])
        state = get_budget_service(budget["id"], 1, today=REFERENCE)
        self.assertEqual(state["usage_percentage"], Decimal("100.00"))
        criar_transacao_service(50, "saida", self.category["id"], "C", "2026-10-07", 1, self.account["id"])
        state = get_budget_service(budget["id"], 1, today=REFERENCE)
        self.assertEqual((state["remaining"], state["usage_percentage"]), (Decimal("-50.00"), Decimal("150.00")))

    def test_future_movements_and_transfers_do_not_inflate_spend(self):
        budget = self.create("500")
        destination = criar_conta_service("Reserva", "digital", 0, 1)
        criar_transacao_service(90, "saida", self.category["id"], "Hoje", "2026-10-07", 1, self.account["id"])
        criar_transacao_service(200, "saida", self.category["id"], "Futura", "2026-10-08", 1, self.account["id"])
        criar_transferencia_service(self.account["id"], destination["id"], 100, "Interna", "2026-10-07", 1)
        state = get_budget_service(budget["id"], 1, today=REFERENCE)
        self.assertEqual(state["spent"], Decimal("90.00"))

    def test_card_purchase_counts_once_after_invoice_payment(self):
        budget = self.create("500")
        card = criar_cartao_service(1, "Cartão", 1000, 13, 20)
        purchase = criar_compra_service(card["id"], 1, 120, "Mercado", self.category["id"], "2026-10-06")
        pagar_fatura_service(purchase["fatura_id"], self.account["id"], 1, "2026-10-07")
        self.assertEqual(get_budget_service(budget["id"], 1, today=REFERENCE)["spent"], Decimal("120.00"))

    def test_reconciled_open_finance_expense_is_counted_once(self):
        conn = get_connection()
        conn.execute("INSERT INTO categorias (nome,usuario_id,chave_sistema) VALUES ('Alimentação padrão',1,'food')")
        category_id = int(conn.execute("SELECT id FROM categorias WHERE usuario_id=1 AND chave_sistema='food'").fetchone()[0])
        conn.commit()
        conn.close()
        budget = self.create("200", category_id=category_id)
        manual = criar_transacao_service(40, "saida", category_id, "Compra conciliada", "2026-10-06", 1, self.account["id"])
        conn = get_connection()
        conn.execute("INSERT INTO conexoes_bancarias (id,usuario_id,provider,external_item_id,client_user_ref,instituicao_nome,status) VALUES (1,1,'pluggy','item','user-1','Banco','ativo')")
        conn.execute("INSERT INTO contas_bancarias_externas (id,conexao_id,external_account_id,conta_nivra_id,nome,tipo) VALUES (1,1,'account',?,'Conta','BANK')", (self.account["id"],))
        conn.execute("INSERT INTO transacoes_bancarias (conta_bancaria_externa_id,external_transaction_id,descricao,valor,data,direcao,status_conciliacao,transacao_nivra_id,metadata_provider) VALUES (1,'bank-1','Compra conciliada',40,'2026-10-06','saida','conciliada',?,'{\"category_name\":\"Food\"}')", (manual["id"],))
        conn.commit()
        conn.close()
        self.assertEqual(get_budget_service(budget["id"], 1, today=REFERENCE)["spent"], Decimal("40.00"))

    def test_installments_only_count_applicable_dates(self):
        budget = self.create("500")
        criar_parcelamento_service(1, "Curso", Decimal("300"), 3, date(2026, 10, 1), "saida", self.category["id"], self.account["id"])
        self.assertEqual(get_budget_service(budget["id"], 1, today=REFERENCE)["spent"], Decimal("100.00"))

    def test_listing_calls_canonical_aggregate_once(self):
        self.create(category_id=self.category["id"])
        second = criar_categoria_service("Saúde", 1)
        self.create(category_id=second["id"])
        with patch("services.budget_service.obter_despesas_por_categoria_service", return_value={}) as aggregate:
            result = list_budgets_service(1, "2026-10", today=REFERENCE)
        self.assertEqual(len(result), 2)
        aggregate.assert_called_once()

    def test_category_in_use_by_budget_cannot_be_deleted_and_crud_keeps_finances(self):
        budget = self.create()
        before = get_connection()
        try:
            transaction_count = before.execute("SELECT COUNT(*) FROM transacoes").fetchone()[0]
        finally:
            before.close()
        with self.assertRaisesRegex(ValueError, "em uso"):
            deletar_categoria_service(self.category["id"], 1)
        update_budget_service(budget["id"], 1, "900", today=REFERENCE)
        delete_budget_service(budget["id"], 1)
        after = get_connection()
        try:
            self.assertEqual(after.execute("SELECT COUNT(*) FROM transacoes").fetchone()[0], transaction_count)
        finally:
            after.close()


if __name__ == "__main__":
    unittest.main()
