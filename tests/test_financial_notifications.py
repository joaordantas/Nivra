import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from database.connection import get_connection
from services.cartao_service import criar_cartao_service, criar_compra_service
from services.categoria_service import criar_categoria_service
from services.financial_notification_service import (
    FinancialNotificationService,
    build_financial_notification_events,
    financial_notification_service,
)
from services.insight_service import obter_insights_financeiros_service
from services.notification_service import notification_service
from services.transacao_service import criar_transacao_service
from services.conta_service import criar_conta_service
from tests.auth_support import authenticate_existing_user
from tests.db_support import remove_test_database, reset_test_database


def card_fact(
    card_id: int = 10,
    *,
    percentage: float = 20,
    invoice_amount: float = 0,
    due_date: str | None = None,
    status: str | None = None,
) -> dict:
    return {
        "card_id": card_id,
        "name": f"Cartão {card_id}",
        "total_limit": 1000.0,
        "committed": percentage * 10,
        "available": max(1000 - percentage * 10, 0),
        "committed_percent": percentage,
        "current_invoice_amount": invoice_amount,
        "closing_date": None,
        "due_date": due_date,
        "invoice_status": status,
        "next_due_invoice_amount": invoice_amount,
        "next_due_date": due_date,
        "next_due_status": status,
    }


def commitment(*cards: dict) -> dict:
    return {
        "total_limit": sum(card["total_limit"] for card in cards),
        "total_committed": sum(card["committed"] for card in cards),
        "total_available": sum(card["available"] for card in cards),
        "committed_percent": None,
        "active_cards": len(cards),
        "cards": list(cards),
    }


def unusual_fact(expense_id: int = 42, *, source: str = "manual", amount: float = 500) -> dict:
    return {
        "id": expense_id,
        "description": "Compra detectada",
        "amount": amount,
        "date": "2026-10-02",
        "category": "Alimentação",
        "account": "Conta",
        "source": source,
        "baseline": 50.0,
        "times_baseline": 10.0,
        "context": "both",
        "sample_size": 8,
        "global_baseline": 50.0,
        "category_baseline": 50.0,
        "median_absolute_deviation": 0.0,
        "robust_z_score": None,
        "reason": "Detecção determinística existente.",
        "data_nature": "deterministic_inference",
    }


class FinancialNotificationRuleTests(unittest.TestCase):
    def test_invoice_far_due_overdue_and_paid_conditions(self):
        reference = date(2026, 10, 10)
        far = build_financial_notification_events(
            card_commitment=commitment(card_fact(invoice_amount=200, due_date="2026-10-20", status="fechada")),
            unusual_expenses=[],
            reference=reference,
        )
        due = build_financial_notification_events(
            card_commitment=commitment(card_fact(invoice_amount=200, due_date="2026-10-13", status="fechada")),
            unusual_expenses=[],
            reference=reference,
        )
        overdue = build_financial_notification_events(
            card_commitment=commitment(card_fact(invoice_amount=200, due_date="2026-10-09", status="vencida")),
            unusual_expenses=[],
            reference=reference,
        )
        paid = build_financial_notification_events(
            card_commitment=commitment(card_fact(invoice_amount=200, due_date="2026-10-09", status="paga")),
            unusual_expenses=[],
            reference=reference,
        )

        self.assertEqual(far, [])
        self.assertEqual(due[0].producer, "card_invoice_due_soon")
        self.assertEqual(str(due[0].severity), "warning")
        self.assertEqual(overdue[0].producer, "card_invoice_overdue")
        self.assertEqual(str(overdue[0].severity), "critical")
        self.assertEqual(paid, [])

    def test_card_thresholds_use_highest_reached_level_per_card_and_period(self):
        reference = date(2026, 10, 2)
        events = build_financial_notification_events(
            card_commitment=commitment(
                card_fact(1, percentage=74.9),
                card_fact(2, percentage=75),
                card_fact(3, percentage=92),
            ),
            unusual_expenses=[],
            reference=reference,
        )

        self.assertEqual([event.producer for event in events], ["card_limit", "card_limit"])
        self.assertEqual([str(event.severity) for event in events], ["warning", "critical"])
        self.assertEqual(events[1].dedupe_key, "card_limit_critical:3:2026-10")
        november = build_financial_notification_events(
            card_commitment=commitment(card_fact(3, percentage=92)),
            unusual_expenses=[],
            reference=date(2026, 11, 1),
        )
        self.assertNotEqual(events[1].dedupe_key, november[0].dedupe_key)

    def test_unusual_expense_uses_detector_identity_without_recalculating_baseline(self):
        first = build_financial_notification_events(
            card_commitment=commitment(),
            unusual_expenses=[unusual_fact(amount=500)],
            reference=date(2026, 10, 2),
        )[0]
        changed_baseline = unusual_fact(amount=500)
        changed_baseline["baseline"] = 75
        replay = build_financial_notification_events(
            card_commitment=commitment(),
            unusual_expenses=[changed_baseline],
            reference=date(2026, 10, 2),
        )[0]

        self.assertEqual(first.dedupe_key, "unusual_expense:manual:42")
        self.assertEqual(replay.dedupe_key, first.dedupe_key)
        self.assertIn("acima do seu padrão recente", first.message)


class FinancialNotificationPersistenceTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        connection = get_connection()
        connection.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES (1, 'Ana', 'ana-p73@example.com', 'hash')"
        )
        connection.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES (2, 'Beto', 'beto-p73@example.com', 'hash')"
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        remove_test_database()

    def _publish(self, user_id: int = 1):
        return financial_notification_service.publish_from_insights(
            user_id,
            card_commitment=commitment(card_fact(7, percentage=92)),
            unusual_expenses=[],
            reference=date(2026, 10, 2),
        )

    def test_replay_and_ownership_are_scoped_per_user(self):
        self._publish(1)
        self._publish(1)
        self._publish(2)

        user_a = notification_service.list(1)
        user_b = notification_service.list(2)
        self.assertEqual(len(user_a), 1)
        self.assertEqual(len(user_b), 1)
        self.assertNotEqual(user_a[0]["id"], user_b[0]["id"])
        self.assertEqual(user_a[0]["metadados"]["route"], "/cards")

    def test_eight_concurrent_replays_persist_one_logical_notification(self):
        workers = 8
        barrier = threading.Barrier(workers)

        def publish(_: int):
            barrier.wait(timeout=10)
            return self._publish(1)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(publish, range(workers)))

        self.assertEqual(len(notification_service.list(1)), 1)
        self.assertTrue(all(result.failed == 0 for result in results))

    def test_real_financial_core_facts_create_card_notifications(self):
        category = criar_categoria_service("Alimentação", 1)
        card = criar_cartao_service(1, "Cartão real", 1000, 13, 20)
        criar_compra_service(card["id"], 1, 920, "Compra real fictícia", category["id"], "2024-09-06")

        result = obter_insights_financeiros_service(
            1,
            "2024-09-01",
            "2024-09-30",
            hoje=date(2024, 9, 18),
            emitir_notificacoes=True,
        )
        notifications = notification_service.list(1)

        self.assertEqual(result["card_commitment"]["cards"][0]["committed_percent"], 92.0)
        self.assertEqual(
            {item["metadados"]["source_type"] for item in notifications},
            {"card_limit_critical", "card_invoice_due_soon"},
        )

    def test_real_anomaly_output_is_published_without_duplicate(self):
        account = criar_conta_service("Conta", "digital", 0, 1)
        category = criar_categoria_service("Alimentação", 1)
        for day in range(1, 9):
            criar_transacao_service(50, "saida", category["id"], f"Histórico {day}", f"2024-08-{day:02d}", 1, account["id"])
        criar_transacao_service(500, "saida", category["id"], "Compra grande", "2024-09-05", 1, account["id"])

        for _ in range(2):
            obter_insights_financeiros_service(
                1,
                "2024-09-01",
                "2024-09-30",
                hoje=date(2024, 9, 20),
                emitir_notificacoes=True,
            )

        notifications = notification_service.list(1)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["tipo"], "financial_alert")
        self.assertEqual(notifications[0]["metadados"]["source_type"], "unusual_expense")

    def test_notification_failure_does_not_break_financial_insight(self):
        with patch.object(
            financial_notification_service,
            "publish_from_insights",
            side_effect=RuntimeError("secondary failure"),
        ):
            result = obter_insights_financeiros_service(
                1,
                "2024-09-01",
                "2024-09-30",
                hoje=date(2024, 9, 20),
                emitir_notificacoes=True,
            )
        self.assertEqual(result["summary"]["expenses"], 0.0)

    def test_individual_notification_failure_is_sanitized_and_non_fatal(self):
        service = FinancialNotificationService()
        with patch.object(
            notification_service,
            "notify",
            side_effect=RuntimeError("do not expose R$ 999 or identity"),
        ), patch("services.financial_notification_service.logger.error") as log_error:
            result = service.publish_from_insights(
                1,
                card_commitment=commitment(card_fact(7, percentage=92)),
                unusual_expenses=[],
                reference=date(2026, 10, 2),
            )

        self.assertEqual(result.failed, 1)
        log_error.assert_called_once()
        joined = " ".join(str(value) for value in log_error.call_args.args)
        self.assertNotIn("999", joined)
        self.assertNotIn("identity", joined)


class FinancialNotificationEndpointTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        connection = get_connection()
        connection.execute(
            "INSERT INTO usuarios (id, usuario, email, senha) VALUES (1, 'Ana', 'ana-p73-route@example.com', 'hash')"
        )
        connection.commit()
        connection.close()
        self.client = TestClient(app)
        authenticate_existing_user(self.client, 1)

    def tearDown(self):
        self.client.close()
        remove_test_database()

    def test_authenticated_insight_recalculation_explicitly_runs_owned_producers(self):
        with patch.object(
            financial_notification_service,
            "publish_from_insights",
            wraps=financial_notification_service.publish_from_insights,
        ) as publish:
            response = self.client.get(
                "/api/insights",
                params={"data_inicio": "2026-10-01", "data_fim": "2026-10-31"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        publish.assert_called_once()
        self.assertEqual(publish.call_args.args[0], 1)


if __name__ == "__main__":
    unittest.main()
