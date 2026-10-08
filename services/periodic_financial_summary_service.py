from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum

from sqlalchemy.exc import DBAPIError, OperationalError, TimeoutError as SqlAlchemyTimeoutError

from services.insight_service import obter_agregado_periodo_financeiro_service
from services.notification_preference_service import notification_preference_service
from services.notification_service import notification_service
from services.notification_types import (
    NotificationPreference,
    NotificationSeverity,
    NotificationType,
)


logger = logging.getLogger("nivra.periodic_financial_summaries")


class SummaryKind(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass(frozen=True)
class SummaryPeriod:
    kind: SummaryKind
    start: date
    end: date
    previous_start: date
    previous_end: date


@dataclass(frozen=True)
class PeriodicSummaryResult:
    period: SummaryPeriod
    outcome: str
    notification: dict | None = None
    error_code: str | None = None
    retryable: bool = False
    generated: int = 0
    deduplicated: int = 0


MONTH_NAMES = (
    "",
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def weekly_period(reference: date, period_start: date | None = None) -> SummaryPeriod:
    if period_start is None:
        end = reference - timedelta(days=reference.weekday() + 1)
        start = end - timedelta(days=6)
    else:
        start = period_start
        if start.weekday() != 0:
            raise ValueError("O resumo semanal deve começar em uma segunda-feira.")
        end = start + timedelta(days=6)
    if end >= reference:
        raise ValueError("O período semanal precisa estar completamente encerrado.")
    return SummaryPeriod(
        kind=SummaryKind.WEEKLY,
        start=start,
        end=end,
        previous_start=start - timedelta(days=7),
        previous_end=start - timedelta(days=1),
    )


def monthly_period(reference: date, period_start: date | None = None) -> SummaryPeriod:
    if period_start is None:
        current_month = reference.replace(day=1)
        end = current_month - timedelta(days=1)
        start = end.replace(day=1)
    else:
        start = period_start
        if start.day != 1:
            raise ValueError("O resumo mensal deve começar no primeiro dia do mês.")
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    if end >= reference:
        raise ValueError("O período mensal precisa estar completamente encerrado.")
    previous_end = start - timedelta(days=1)
    return SummaryPeriod(
        kind=SummaryKind.MONTHLY,
        start=start,
        end=end,
        previous_start=previous_end.replace(day=1),
        previous_end=previous_end,
    )


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _format_brl(value: object) -> str:
    amount = _money(value)
    sign = "-" if amount < 0 else ""
    formatted = f"{abs(amount):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{sign}R$ {formatted}"


def _expense_comparison(current: dict, previous: dict) -> str | None:
    previous_expenses = _money(previous["despesas"])
    if previous["quantidade"] == 0 or previous_expenses == 0:
        return None
    current_expenses = _money(current["despesas"])
    change = (current_expenses - previous_expenses) * Decimal("100") / previous_expenses
    rounded = abs(change).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if abs(change) < Decimal("1"):
        return "As despesas ficaram sem alteração relevante em relação ao período anterior."
    direction = "maiores" if change > 0 else "menores"
    return f"As despesas foram {rounded}% {direction} que no período anterior."


def _template(period: SummaryPeriod, current: dict, previous: dict) -> tuple[str, str]:
    if period.kind is SummaryKind.WEEKLY:
        title = "Seu resumo da semana está pronto"
    else:
        title = f"Seu resumo de {MONTH_NAMES[period.start.month]} está pronto"
    message_parts = [
        f"Você recebeu {_format_brl(current['entradas'])}, gastou {_format_brl(current['despesas'])} "
        f"e terminou o período com saldo líquido de {_format_brl(current['saldo'])}."
    ]
    if current["categoria_principal"] is not None:
        message_parts.append(
            f"Sua maior categoria de gastos foi {current['categoria_principal']}."
        )
    comparison = _expense_comparison(current, previous)
    if comparison is not None:
        message_parts.append(comparison)
    return title, " ".join(message_parts)


class PeriodicFinancialSummaryService:
    def generate_weekly_summary(
        self,
        usuario_id: int,
        *,
        reference: date,
        period_start: date | None = None,
    ) -> PeriodicSummaryResult:
        return self._generate(usuario_id, weekly_period(reference, period_start))

    def generate_monthly_summary(
        self,
        usuario_id: int,
        *,
        reference: date,
        period_start: date | None = None,
    ) -> PeriodicSummaryResult:
        return self._generate(usuario_id, monthly_period(reference, period_start))

    def _generate(self, usuario_id: int, period: SummaryPeriod) -> PeriodicSummaryResult:
        if usuario_id < 1:
            raise ValueError("Usuário inválido para resumo financeiro.")
        current = obter_agregado_periodo_financeiro_service(
            usuario_id, period.start, period.end
        )
        if current["quantidade"] == 0:
            return PeriodicSummaryResult(period=period, outcome="no_activity")
        previous = obter_agregado_periodo_financeiro_service(
            usuario_id, period.previous_start, period.previous_end
        )
        if period.kind is SummaryKind.WEEKLY:
            preference = NotificationPreference.WEEKLY_SUMMARY
            source_type = "weekly_summary"
        else:
            preference = NotificationPreference.MONTHLY_SUMMARY
            source_type = "monthly_summary"
        dedupe_key = f"{source_type}:{period.start.isoformat()}"
        preferences = notification_preference_service.get_effective(usuario_id)
        if not preferences[preference.value]:
            notification_preference_service.suppress_event(
                usuario_id, preference, dedupe_key
            )
            logger.info(
                "periodic_summary_event kind=%s outcome=disabled", period.kind.value
            )
            return PeriodicSummaryResult(period=period, outcome="suppressed")
        if notification_preference_service.event_was_suppressed(
            usuario_id, dedupe_key
        ):
            logger.info(
                "periodic_summary_event kind=%s outcome=previously_disabled",
                period.kind.value,
            )
            return PeriodicSummaryResult(period=period, outcome="suppressed")
        title, message = _template(period, current, previous)
        try:
            delivery = notification_service.deliver(
                usuario_id,
                NotificationType.SUMMARY,
                title,
                message,
                severity=NotificationSeverity.INFO,
                metadata={
                    "route": "/dashboard",
                    "source_type": source_type,
                    "source_id": period.start.isoformat(),
                },
                dedupe_key=dedupe_key,
            )
        except Exception as exc:
            retryable = isinstance(exc, (OperationalError, SqlAlchemyTimeoutError)) or (
                isinstance(exc, DBAPIError) and exc.connection_invalidated
            )
            logger.error(
                "periodic_summary_event kind=%s outcome=failed error_code=%s",
                period.kind.value,
                "database_unavailable" if retryable else "summary_generation_failed",
            )
            return PeriodicSummaryResult(
                period=period,
                outcome="failed",
                error_code=(
                    "database_unavailable" if retryable else "summary_generation_failed"
                ),
                retryable=retryable,
            )
        logger.info(
            "periodic_summary_event kind=%s outcome=delivered_or_deduplicated",
            period.kind.value,
        )
        return PeriodicSummaryResult(
            period=period,
            outcome="delivered_or_deduplicated",
            notification=delivery.notification,
            generated=int(delivery.created),
            deduplicated=int(delivery.deduplicated),
        )


periodic_financial_summary_service = PeriodicFinancialSummaryService()
