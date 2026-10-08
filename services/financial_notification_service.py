from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from services.financial_alert_rules import classify_card_limit, classify_invoice_alert
from services.notification_preference_service import notification_preference_service
from services.notification_service import notification_service
from services.notification_types import (
    NotificationPreference,
    NotificationSeverity,
    NotificationType,
)


logger = logging.getLogger("nivra.financial_notifications")


@dataclass(frozen=True)
class FinancialNotificationEvent:
    producer: str
    preference: NotificationPreference
    notification_type: NotificationType
    severity: NotificationSeverity
    title: str
    message: str
    route: str
    source_type: str
    source_id: str
    dedupe_key: str


@dataclass(frozen=True)
class FinancialNotificationResult:
    attempted: int
    delivered_or_deduplicated: int
    suppressed: int
    failed: int
    generated: int = 0
    deduplicated: int = 0


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _format_brl(value: object) -> str:
    amount = _money(value)
    sign = "-" if amount < 0 else ""
    formatted = f"{abs(amount):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{sign}R$ {formatted}"


def _period(reference: date) -> str:
    return reference.strftime("%Y-%m")


def _card_limit_event(card: dict, reference: date) -> FinancialNotificationEvent | None:
    percentage_value = card.get("committed_percent")
    level = classify_card_limit(percentage_value)
    if level is None:
        return None
    percentage = _money(percentage_value)
    card_id = int(card["card_id"])
    card_name = str(card["name"])
    if level == "critical":
        severity = NotificationSeverity.CRITICAL
        title = f"{card_name} está com o limite crítico"
        message = (
            f"{percentage:.0f}% do limite está comprometido. "
            f"O valor disponível é {_format_brl(card['available'])}."
        )
    else:
        severity = NotificationSeverity.WARNING
        title = f"{card_name} está próximo do limite"
        message = f"{percentage:.0f}% do limite já está comprometido."
    period = _period(reference)
    return FinancialNotificationEvent(
        producer="card_limit",
        preference=NotificationPreference.CARD_LIMIT,
        notification_type=NotificationType.CARD_ALERT,
        severity=severity,
        title=title,
        message=message,
        route="/cards",
        source_type=f"card_limit_{level}",
        source_id=f"{card_id}:{period}",
        dedupe_key=f"card_limit_{level}:{card_id}:{period}",
    )


def _invoice_event(card: dict, reference: date) -> FinancialNotificationEvent | None:
    amount = _money(card.get("next_due_invoice_amount", 0))
    due_date_value = card.get("next_due_date")
    status = card.get("next_due_status")
    classification = classify_invoice_alert(
        amount=amount,
        status=status,
        due_date=due_date_value,
        reference=reference,
    )
    if classification is None:
        return None
    due_date = classification.due_date
    card_id = int(card["card_id"])
    card_name = str(card["name"])
    source_id = f"{card_id}:{due_date.isoformat()}"
    if classification.kind == "overdue":
        return FinancialNotificationEvent(
            producer="card_invoice_overdue",
            preference=NotificationPreference.INVOICE_OVERDUE,
            notification_type=NotificationType.CARD_ALERT,
            severity=NotificationSeverity.CRITICAL,
            title=f"A fatura de {card_name} está vencida",
            message=f"O valor em aberto é {_format_brl(amount)}.",
            route="/cards",
            source_type="card_invoice_overdue",
            source_id=source_id,
            dedupe_key=f"card_invoice_overdue:{source_id}",
        )
    days = classification.days_until_due
    day_label = "hoje" if days == 0 else f"em {days} {'dia' if days == 1 else 'dias'}"
    return FinancialNotificationEvent(
        producer="card_invoice_due_soon",
        preference=NotificationPreference.INVOICE_DUE_SOON,
        notification_type=NotificationType.CARD_ALERT,
        severity=NotificationSeverity.WARNING,
        title=f"A fatura de {card_name} vence em breve",
        message=f"O valor de {_format_brl(amount)} vence {day_label}.",
        route="/cards",
        source_type="card_invoice_due_soon",
        source_id=source_id,
        dedupe_key=f"card_invoice_due:{source_id}",
    )


def _unusual_expense_events(unusual_expenses: Iterable[dict]) -> list[FinancialNotificationEvent]:
    events = []
    for expense in unusual_expenses:
        source = str(expense["source"])
        expense_id = int(expense["id"])
        category = str(expense.get("category") or "Sem categoria")
        events.append(FinancialNotificationEvent(
            producer="unusual_expense",
            preference=NotificationPreference.UNUSUAL_EXPENSE,
            notification_type=NotificationType.FINANCIAL_ALERT,
            severity=NotificationSeverity.WARNING,
            title="Gasto fora do padrão detectado",
            message=(
                f"Um gasto de {_format_brl(expense['amount'])} em {category} "
                "ficou acima do seu padrão recente."
            ),
            route="/transactions",
            source_type="unusual_expense",
            source_id=f"{source}:{expense_id}",
            dedupe_key=f"unusual_expense:{source}:{expense_id}",
        ))
    return events


def build_financial_notification_events(
    *,
    card_commitment: dict,
    unusual_expenses: Iterable[dict],
    reference: date,
) -> list[FinancialNotificationEvent]:
    events: list[FinancialNotificationEvent] = []
    for card in card_commitment.get("cards", []):
        card_limit = _card_limit_event(card, reference)
        invoice = _invoice_event(card, reference)
        if card_limit is not None:
            events.append(card_limit)
        if invoice is not None:
            events.append(invoice)
    events.extend(_unusual_expense_events(unusual_expenses))
    return events


class FinancialNotificationService:
    def publish_from_insights(
        self,
        usuario_id: int,
        *,
        card_commitment: dict,
        unusual_expenses: Iterable[dict],
        reference: date,
    ) -> FinancialNotificationResult:
        events = build_financial_notification_events(
            card_commitment=card_commitment,
            unusual_expenses=unusual_expenses,
            reference=reference,
        )
        preferences = notification_preference_service.get_effective(usuario_id)
        delivered = 0
        suppressed = 0
        failed = 0
        generated = 0
        deduplicated = 0
        for event in events:
            if not preferences[event.preference.value]:
                notification_preference_service.suppress_event(
                    usuario_id,
                    event.preference,
                    event.dedupe_key,
                )
                suppressed += 1
                logger.info(
                    "financial_notification_event producer=%s type=%s outcome=disabled",
                    event.producer,
                    event.notification_type,
                )
                continue
            if notification_preference_service.event_was_suppressed(
                usuario_id,
                event.dedupe_key,
            ):
                suppressed += 1
                logger.info(
                    "financial_notification_event producer=%s type=%s outcome=previously_disabled",
                    event.producer,
                    event.notification_type,
                )
                continue
            try:
                delivery = notification_service.deliver(
                    usuario_id,
                    event.notification_type,
                    event.title,
                    event.message,
                    severity=event.severity,
                    metadata={
                        "route": event.route,
                        "source_type": event.source_type,
                        "source_id": event.source_id,
                    },
                    dedupe_key=event.dedupe_key,
                )
                delivered += 1
                generated += int(delivery.created)
                deduplicated += int(delivery.deduplicated)
                logger.info(
                    "financial_notification_event producer=%s type=%s outcome=delivered_or_deduplicated",
                    event.producer,
                    event.notification_type,
                )
            except Exception:
                failed += 1
                logger.error(
                    "financial_notification_event producer=%s type=%s outcome=failed",
                    event.producer,
                    event.notification_type,
                )
        return FinancialNotificationResult(
            attempted=len(events),
            delivered_or_deduplicated=delivered,
            suppressed=suppressed,
            failed=failed,
            generated=generated,
            deduplicated=deduplicated,
        )


financial_notification_service = FinancialNotificationService()
