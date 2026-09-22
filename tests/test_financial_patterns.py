import unittest
from datetime import date

from database.connection import get_connection
from services.categoria_service import criar_categoria_service
from services.conta_service import criar_conta_service
from services.financial_pattern_service import (
    detect_recurring_expenses,
    detect_unusual_expenses,
    normalize_financial_description,
)
from services.insight_service import obter_contexto_financeiro_lumi_service
from services.transacao_service import criar_transacao_service
from tests.db_support import remove_test_database, reset_test_database


def expense(
    identifier: int,
    value: float,
    observed_at: str,
    description: str = "Netflix",
    *,
    category: str = "Serviços e Assinaturas",
    category_key: str | None = "subscriptions",
    source: str = "manual",
    neutral: bool = False,
    installment_id: int | None = None,
) -> dict:
    return {
        "id": identifier,
        "amount": value,
        "description": description,
        "date": observed_at,
        "type": "saida",
        "category_id": None if category_key is None else 1,
        "category": category,
        "category_key": category_key,
        "account": "Conta",
        "source": source,
        "neutral": neutral,
        "parcelamento_id": installment_id,
        "numero_parcela": identifier if installment_id is not None else None,
    }


class RecurrenceDetectionTests(unittest.TestCase):
    def test_description_normalization_is_conservative(self):
        self.assertEqual(
            normalize_financial_description("COMPRA Netflix.com - pedido #ABCD1234"),
            "netflix",
        )
        self.assertEqual(
            normalize_financial_description("Netflix.com pedido #WXYZ9876"),
            "netflix",
        )
        self.assertNotEqual(
            normalize_financial_description("Uber"),
            normalize_financial_description("Uber Eats"),
        )

    def test_zero_one_or_two_occurrences_are_not_recurrences(self):
        self.assertEqual(detect_recurring_expenses([]), [])
        self.assertEqual(detect_recurring_expenses([expense(1, 40, "2024-01-05")]), [])
        self.assertEqual(
            detect_recurring_expenses([
                expense(1, 40, "2024-01-05"),
                expense(2, 40, "2024-02-05"),
            ]),
            [],
        )

    def test_monthly_end_of_month_crosses_february_and_predicts_next_date(self):
        patterns = detect_recurring_expenses([
            expense(1, 100, "2024-01-31"),
            expense(2, 100, "2024-02-29"),
            expense(3, 100, "2024-03-31"),
        ])
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["frequency"], "monthly")
        self.assertEqual(patterns[0]["next_occurrence"], "2024-04-30")
        self.assertEqual(patterns[0]["confidence"], "medium")

    def test_weekly_and_fortnightly_patterns_are_distinct(self):
        weekly = detect_recurring_expenses([
            expense(1, 30, "2024-01-01", "Academia semanal"),
            expense(2, 30, "2024-01-08", "Academia semanal"),
            expense(3, 30, "2024-01-15", "Academia semanal"),
        ])
        fortnightly = detect_recurring_expenses([
            expense(4, 80, "2024-01-01", "Limpeza"),
            expense(5, 80, "2024-01-15", "Limpeza"),
            expense(6, 80, "2024-01-29", "Limpeza"),
        ])
        self.assertEqual(weekly[0]["frequency"], "weekly")
        self.assertEqual(fortnightly[0]["frequency"], "fortnightly")

    def test_annual_pattern_requires_three_years_of_evidence(self):
        patterns = detect_recurring_expenses([
            expense(1, 250, "2022-06-20", "Seguro anual"),
            expense(2, 250, "2023-06-19", "Seguro anual"),
            expense(3, 250, "2024-06-21", "Seguro anual"),
        ])
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["frequency"], "annual")
        self.assertEqual(patterns[0]["next_occurrence"], "2025-06-21")

    def test_small_value_and_description_variations_are_accepted(self):
        patterns = detect_recurring_expenses([
            expense(1, 100, "2024-01-05", "PIX Energia ref 123456"),
            expense(2, 108, "2024-02-04", "pix energia ref 654321"),
            expense(3, 95, "2024-03-06", "Pix Energia REF 999999"),
        ])
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["frequency"], "monthly")
        self.assertEqual(patterns[0]["typical_amount"], 100.0)

    def test_excessive_value_variation_and_different_merchants_are_rejected(self):
        unstable = detect_recurring_expenses([
            expense(1, 40, "2024-01-05"),
            expense(2, 200, "2024-02-05"),
            expense(3, 600, "2024-03-05"),
        ])
        different = detect_recurring_expenses([
            expense(4, 40, "2024-01-05", "Uber"),
            expense(5, 40, "2024-02-05", "Uber Eats"),
            expense(6, 40, "2024-03-05", "Uber Trip"),
        ])
        self.assertEqual(unstable, [])
        self.assertEqual(different, [])

    def test_irregular_pattern_has_no_next_date(self):
        dates = ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-15", "2024-05-15", "2024-06-15"]
        patterns = detect_recurring_expenses([
            expense(index, 50, observed_at, "Serviço variável")
            for index, observed_at in enumerate(dates, start=1)
        ])
        self.assertEqual(len(patterns), 1)
        self.assertIn(patterns[0]["frequency"], {"monthly", "approximately_monthly"})
        self.assertIsNone(patterns[0]["next_occurrence"])

    def test_relevant_amount_change_is_explained(self):
        patterns = detect_recurring_expenses([
            expense(1, 39.90, "2024-01-05"),
            expense(2, 39.90, "2024-02-05"),
            expense(3, 39.90, "2024-03-05"),
            expense(4, 59.90, "2024-04-05"),
        ])
        change = patterns[0]["amount_change"]
        self.assertIsNotNone(change)
        self.assertEqual(change["direction"], "increase")
        self.assertAlmostEqual(change["change_percent"], 50.13, places=2)

    def test_installments_and_neutral_movements_are_ignored_but_supported_sources_work(self):
        entries = [
            expense(1, 100, "2024-01-10", "Notebook", installment_id=5),
            expense(2, 100, "2024-02-10", "Notebook", installment_id=5),
            expense(3, 100, "2024-03-10", "Notebook", installment_id=5),
            expense(4, 500, "2024-01-05", "Pagamento fatura", neutral=True),
            expense(5, 500, "2024-02-05", "Pagamento fatura", neutral=True),
            expense(6, 500, "2024-03-05", "Pagamento fatura", neutral=True),
            expense(7, 45, "2024-01-07", "Streaming", source="card"),
            expense(8, 45, "2024-02-07", "Streaming", source="card"),
            expense(9, 45, "2024-03-07", "Streaming", source="card"),
            expense(10, 25, "2024-01-09", "Nuvem", source="open_finance"),
            expense(11, 25, "2024-02-09", "Nuvem", source="open_finance"),
            expense(12, 25, "2024-03-09", "Nuvem", source="open_finance"),
        ]
        patterns = detect_recurring_expenses(entries)
        self.assertEqual({item["description"] for item in patterns}, {"Streaming", "Nuvem"})
        self.assertNotIn("Notebook", {item["description"] for item in patterns})


class AnomalyDetectionTests(unittest.TestCase):
    def test_insufficient_history_and_small_values_do_not_trigger(self):
        sparse = [expense(1, 20, "2024-01-01"), expense(2, 500, "2024-02-01")]
        small = [expense(index, 5, f"2024-01-{index:02d}") for index in range(1, 9)]
        small.append(expense(20, 30, "2024-02-01"))
        self.assertEqual(detect_unusual_expenses(sparse, date(2024, 2, 1), date(2024, 2, 29)), [])
        self.assertEqual(detect_unusual_expenses(small, date(2024, 2, 1), date(2024, 2, 29)), [])

    def test_global_anomaly_uses_only_previous_expenses(self):
        entries = [
            expense(index, 20 + index, f"2024-01-{index:02d}", f"Compra {index}", category="Diversos", category_key=None)
            for index in range(1, 9)
        ]
        entries.append(expense(20, 300, "2024-02-01", "Compra excepcional", category="Nova", category_key=None))
        unusual = detect_unusual_expenses(entries, date(2024, 2, 1), date(2024, 2, 29))
        self.assertEqual(len(unusual), 1)
        self.assertEqual(unusual[0]["context"], "global")
        self.assertEqual(unusual[0]["sample_size"], 8)
        self.assertIn("mediana recente geral", unusual[0]["reason"])

    def test_category_context_prevents_false_global_and_detects_category_outlier(self):
        entries = [
            expense(index, 40, f"2024-01-{index:02d}", f"Pequeno {index}", category="Diversos", category_key=None)
            for index in range(1, 9)
        ]
        entries.extend([
            expense(20, 600, "2024-01-10", "Aluguel", category="Moradia", category_key="housing"),
            expense(21, 610, "2024-02-10", "Aluguel", category="Moradia", category_key="housing"),
            expense(22, 590, "2024-03-10", "Aluguel", category="Moradia", category_key="housing"),
            expense(23, 605, "2024-04-10", "Aluguel", category="Moradia", category_key="housing"),
            expense(24, 610, "2024-05-10", "Aluguel", category="Moradia", category_key="housing"),
        ])
        self.assertEqual(
            detect_unusual_expenses(entries, date(2024, 5, 1), date(2024, 5, 31)),
            [],
        )

        food = [
            expense(30 + index, 20, f"2024-0{index}-12", "Lanche", category="Alimentação", category_key="food")
            for index in range(1, 5)
        ]
        food.append(expense(40, 120, "2024-05-12", "Lanche especial", category="Alimentação", category_key="food"))
        global_high = [
            expense(index, 100, f"2024-01-{index:02d}", f"Gasto {index}", category="Diversos", category_key=None)
            for index in range(1, 9)
        ]
        unusual = detect_unusual_expenses([*global_high, *food], date(2024, 5, 1), date(2024, 5, 31))
        self.assertEqual(unusual[0]["context"], "category")
        self.assertIn("categoria Alimentação", unusual[0]["reason"])

    def test_zero_median_historical_outlier_installment_and_neutral_are_safe(self):
        zero_values = [expense(index, 0, f"2024-01-{index:02d}") for index in range(1, 9)]
        zero_values.append(expense(20, 500, "2024-02-01"))
        self.assertEqual(detect_unusual_expenses(zero_values, date(2024, 2, 1), date(2024, 2, 29)), [])

        baseline = [expense(index, 20, f"2024-01-{index:02d}") for index in range(1, 8)]
        baseline.append(expense(8, 1000, "2024-01-20"))
        baseline.extend([
            expense(20, 100, "2024-02-01"),
            expense(21, 1000, "2024-02-02", installment_id=9),
            expense(22, 1000, "2024-02-03", neutral=True),
        ])
        unusual = detect_unusual_expenses(baseline, date(2024, 2, 1), date(2024, 2, 29))
        self.assertEqual([item["id"] for item in unusual], [20])


class PatternIntegrationTests(unittest.TestCase):
    def setUp(self):
        reset_test_database()
        conn = get_connection()
        conn.execute("INSERT INTO usuarios (id, usuario, email, senha) VALUES (1, 'Ana', 'ana-pattern@example.com', 'hash')")
        conn.execute("INSERT INTO usuarios (id, usuario, email, senha) VALUES (2, 'Beto', 'beto-pattern@example.com', 'hash')")
        conn.commit()
        conn.close()
        self.account = criar_conta_service("Conta Ana", "digital", 0, 1)
        self.category = criar_categoria_service("Assinaturas Ana", 1)

    def tearDown(self):
        remove_test_database()

    def test_context_contains_scoped_deterministic_recurrences(self):
        for observed_at in ("2024-07-05", "2024-08-05", "2024-09-05"):
            criar_transacao_service(49.90, "saida", self.category["id"], "Nivra Music", observed_at, 1, self.account["id"])

        other_account = criar_conta_service("Conta Beto", "digital", 0, 2)
        other_category = criar_categoria_service("Privada", 2)
        for observed_at in ("2024-07-07", "2024-08-07", "2024-09-07"):
            criar_transacao_service(999, "saida", other_category["id"], "Segredo Beto", observed_at, 2, other_account["id"])

        context = obter_contexto_financeiro_lumi_service(
            1, "2024-09-01", "2024-09-30", hoje=date(2024, 9, 20)
        )
        self.assertTrue(context["capabilities"]["recurrences_available"])
        self.assertEqual(context["evidence"]["recurrences"], "deterministic_inference")
        self.assertEqual([item["description"] for item in context["recurring_expenses"]], ["Nivra Music"])
        self.assertNotIn("Segredo Beto", str(context))


if __name__ == "__main__":
    unittest.main()
