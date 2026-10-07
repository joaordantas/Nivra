from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal


CARD_WARNING_PERCENT = Decimal("75")
CARD_CRITICAL_PERCENT = Decimal("90")
INVOICE_DUE_SOON_DAYS = 3


@dataclass(frozen=True)
class InvoiceAlertClassification:
    kind: Literal["due_soon", "overdue"]
    due_date: date
    days_until_due: int


def classify_card_limit(percentage: object | None) -> Literal["warning", "critical"] | None:
    if percentage is None:
        return None
    normalized = Decimal(str(percentage))
    if normalized >= CARD_CRITICAL_PERCENT:
        return "critical"
    if normalized >= CARD_WARNING_PERCENT:
        return "warning"
    return None


def classify_invoice_alert(
    *,
    amount: object,
    status: object,
    due_date: object,
    reference: date,
) -> InvoiceAlertClassification | None:
    normalized_amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    if normalized_amount <= 0 or status == "paga" or due_date is None:
        return None
    normalized_due_date = date.fromisoformat(str(due_date))
    days = (normalized_due_date - reference).days
    if status == "vencida":
        return InvoiceAlertClassification("overdue", normalized_due_date, days)
    if 0 <= days <= INVOICE_DUE_SOON_DAYS:
        return InvoiceAlertClassification("due_soon", normalized_due_date, days)
    return None
