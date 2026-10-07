import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from database.connection import get_connection
from services.cartao_service import (
    criar_cartao_service,
    criar_compra_service,
    pagar_fatura_service,
)
from services.categoria_service import criar_categoria_service
from services.conta_service import criar_conta_service
from services.insight_service import obter_agregado_periodo_financeiro_service
from services.notification_preference_service import notification_preference_service
from services.notification_service import notification_service
from services.parcelamento_service import criar_parcelamento_service
from services.periodic_financial_summary_service import (
    monthly_period,
    periodic_financial_summary_service,
    weekly_period,
)
from services.transacao_service import criar_transacao_service
from tests.db_support import remove_test_database, reset_test_database


class PeriodicFinancialSummaryTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        connection = get_connection()
        connection.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES "
            "(1, 'Resumo A', 'summary-a@example.com', 'hash'), "
            "(2, 'Resumo B', 'summary-b@example.com', 'hash')"
        )
        connection.commit()
        connection.close()
        self.account = criar_conta_service("Conta A", "digital", 5000, 1)
        self.food = criar_categoria_service("Alimentação", 1)
        self.home = criar_categoria_service("Casa", 1)

    def tearDown(self):
        remove_test_database()

    def movement(self, amount, kind, day, category=None, user_id=1, account_id=None):
        return criar_transacao_service(
            amount,
            kind,
            (category or self.food)["id"],
            "Movimento fictício",
            day,
            user_id,
            account_id if account_id is not None else self.account["id"],
        )

    def test_period_boundaries_are_closed_calendar_periods(self):
        week = weekly_period(date(2026, 10, 6))
        self.assertEqual((week.start.isoformat(), week.end.isoformat()), ("2026-09-28", "2026-10-04"))
        self.assertEqual((week.previous_start.isoformat(), week.previous_end.isoformat()), ("2026-09-21", "2026-09-27"))

        monday = weekly_period(date(2026, 10, 5))
        self.assertEqual((monday.start.isoformat(), monday.end.isoformat()), ("2026-09-28", "2026-10-04"))
        month = monthly_period(date(2026, 10, 1))
        self.assertEqual((month.start.isoformat(), month.end.isoformat()), ("2026-09-01", "2026-09-30"))

    def test_current_or_misaligned_period_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "encerrado"):
            weekly_period(date(2026, 10, 6), date(2026, 10, 5))
        with self.assertRaisesRegex(ValueError, "segunda-feira"):
            weekly_period(date(2026, 10, 20), date(2026, 10, 6))
        with self.assertRaisesRegex(ValueError, "encerrado"):
            monthly_period(date(2026, 10, 6), date(2026, 10, 1))

    def test_weekly_summary_aggregates_values_category_and_comparison(self):
        self.movement(100, "saida", "2026-09-23")
        self.movement(1000, "entrada", "2026-09-29")
        self.movement(60, "saida", "2026-09-30")
        self.movement(90, "saida", "2026-10-02")

        result = periodic_financial_summary_service.generate_weekly_summary(
            1, reference=date(2026, 10, 6)
        )
        self.assertEqual(result.outcome, "delivered_or_deduplicated")
        item = result.notification
        self.assertEqual(item["tipo"], "summary")
        self.assertEqual(item["severidade"], "info")
        self.assertIn("R$ 1.000,00", item["mensagem"])
        self.assertIn("R$ 150,00", item["mensagem"])
        self.assertIn("R$ 850,00", item["mensagem"])
        self.assertIn("Alimentação", item["mensagem"])
        self.assertIn("50% maiores", item["mensagem"])

    def test_monthly_summary_and_previous_month_comparison(self):
        self.movement(400, "saida", "2026-08-12")
        self.movement(2000, "entrada", "2026-09-02")
        self.movement(300, "saida", "2026-09-17")

        result = periodic_financial_summary_service.generate_monthly_summary(
            1, reference=date(2026, 10, 6)
        )
        item = result.notification
        self.assertEqual(item["titulo"], "Seu resumo de setembro está pronto")
        self.assertIn("25% menores", item["mensagem"])
        self.assertEqual(item["metadados"], {
            "route": "/dashboard",
            "source_id": "2026-09-01",
            "source_type": "monthly_summary",
        })

    def test_empty_week_and_month_do_not_create_notifications(self):
        weekly = periodic_financial_summary_service.generate_weekly_summary(
            1, reference=date(2026, 10, 6)
        )
        monthly = periodic_financial_summary_service.generate_monthly_summary(
            1, reference=date(2026, 10, 6)
        )
        self.assertEqual((weekly.outcome, monthly.outcome), ("no_activity", "no_activity"))
        self.assertEqual(notification_service.list(1), [])

    def test_future_and_current_period_transactions_are_excluded(self):
        self.movement(500, "saida", "2026-10-05")
        self.movement(700, "entrada", "2026-11-01")
        weekly = periodic_financial_summary_service.generate_weekly_summary(
            1, reference=date(2026, 10, 6)
        )
        monthly = periodic_financial_summary_service.generate_monthly_summary(
            1, reference=date(2026, 10, 6)
        )
        self.assertEqual(weekly.outcome, "no_activity")
        self.assertEqual(monthly.outcome, "no_activity")

    def test_category_tie_has_stable_alphabetical_winner(self):
        self.movement(100, "saida", "2026-09-10", self.home)
        self.movement(100, "saida", "2026-09-20", self.food)
        result = periodic_financial_summary_service.generate_monthly_summary(
            1, reference=date(2026, 10, 6)
        )
        self.assertIn("Alimentação", result.notification["mensagem"])

    def test_previous_period_absence_or_zero_expense_omits_percentage(self):
        self.movement(500, "entrada", "2026-08-10")
        self.movement(50, "saida", "2026-09-10")
        result = periodic_financial_summary_service.generate_monthly_summary(
            1, reference=date(2026, 10, 6)
        )
        self.assertNotIn("%", result.notification["mensagem"])

    def test_preferences_default_on_and_disabled_period_is_never_backfilled(self):
        effective = notification_preference_service.get_effective(1)
        self.assertTrue(effective["weekly_summary"])
        self.assertTrue(effective["monthly_summary"])
        self.movement(75, "saida", "2026-09-30")
        notification_preference_service.update(1, {"weekly_summary": False})
        disabled = periodic_financial_summary_service.generate_weekly_summary(
            1, reference=date(2026, 10, 6)
        )
        notification_preference_service.update(1, {"weekly_summary": True})
        replay = periodic_financial_summary_service.generate_weekly_summary(
            1, reference=date(2026, 10, 6)
        )
        self.assertEqual((disabled.outcome, replay.outcome), ("suppressed", "suppressed"))
        self.assertEqual(notification_service.list(1), [])

        self.movement(80, "saida", "2026-10-07")
        later = periodic_financial_summary_service.generate_weekly_summary(
            1, reference=date(2026, 10, 13)
        )
        self.assertEqual(later.outcome, "delivered_or_deduplicated")

    def test_monthly_preference_off_records_suppression(self):
        self.movement(50, "saida", "2026-09-10")
        notification_preference_service.update(1, {"monthly_summary": False})
        result = periodic_financial_summary_service.generate_monthly_summary(
            1, reference=date(2026, 10, 6)
        )
        self.assertEqual(result.outcome, "suppressed")
        connection = get_connection()
        try:
            row = connection.execute(
                "SELECT preference_key FROM notification_preference_suppressions "
                "WHERE usuario_id = ? AND dedupe_key = ?",
                (1, "monthly_summary:2026-09-01"),
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(row, ("monthly_summary",))

    def test_replay_periods_and_users_are_isolated(self):
        self.movement(50, "saida", "2026-09-30")
        account_b = criar_conta_service("Conta B", "digital", 1000, 2)
        category_b = criar_categoria_service("Mercado", 2)
        self.movement(90, "saida", "2026-09-30", category_b, 2, account_b["id"])
        for _ in range(2):
            periodic_financial_summary_service.generate_weekly_summary(1, reference=date(2026, 10, 6))
        periodic_financial_summary_service.generate_weekly_summary(2, reference=date(2026, 10, 6))
        self.movement(20, "saida", "2026-10-08")
        periodic_financial_summary_service.generate_weekly_summary(1, reference=date(2026, 10, 13))
        self.assertEqual(len(notification_service.list(1)), 2)
        self.assertEqual(len(notification_service.list(2)), 1)

    def test_concurrent_replays_persist_one_notification(self):
        self.movement(50, "saida", "2026-09-30")
        workers = 8
        barrier = threading.Barrier(workers)

        def publish(_):
            barrier.wait(timeout=10)
            return periodic_financial_summary_service.generate_weekly_summary(
                1, reference=date(2026, 10, 6)
            )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(publish, range(workers)))
        self.assertTrue(all(item.outcome == "delivered_or_deduplicated" for item in results))
        self.assertEqual(len(notification_service.list(1)), 1)

    def test_installments_only_impact_their_own_dates(self):
        criar_parcelamento_service(
            1, "Curso", Decimal("300.00"), 3, date(2026, 9, 15), "saida",
            self.food["id"], self.account["id"],
        )
        aggregate = obter_agregado_periodo_financeiro_service(
            1, date(2026, 9, 1), date(2026, 9, 30)
        )
        self.assertEqual(aggregate["despesas"], Decimal("100.00"))
        self.assertEqual(aggregate["quantidade"], 1)

    def test_card_purchase_is_counted_once_even_after_invoice_payment(self):
        card = criar_cartao_service(1, "Cartão teste", 1000, 13, 20)
        purchase = criar_compra_service(
            card["id"], 1, 120, "Mercado", self.food["id"], "2026-09-10"
        )
        pagar_fatura_service(purchase["fatura_id"], self.account["id"], 1, "2026-09-20")
        aggregate = obter_agregado_periodo_financeiro_service(
            1, date(2026, 9, 1), date(2026, 9, 30)
        )
        self.assertEqual(aggregate["despesas"], Decimal("120.00"))
        self.assertEqual(aggregate["quantidade"], 1)

    def test_notification_failure_is_sanitized_and_finances_remain_unchanged(self):
        self.movement(50, "saida", "2026-09-30")
        before = obter_agregado_periodo_financeiro_service(
            1, date(2026, 9, 28), date(2026, 10, 4)
        )
        with patch.object(notification_service, "notify", side_effect=RuntimeError("R$ 999 segredo")), \
             patch("services.periodic_financial_summary_service.logger.error") as log_error:
            result = periodic_financial_summary_service.generate_weekly_summary(
                1, reference=date(2026, 10, 6)
            )
        after = obter_agregado_periodo_financeiro_service(
            1, date(2026, 9, 28), date(2026, 10, 4)
        )
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(before, after)
        self.assertNotIn("999", " ".join(str(value) for value in log_error.call_args.args))


if __name__ == "__main__":
    unittest.main()
