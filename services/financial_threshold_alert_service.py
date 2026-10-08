from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from repositories.financial_alert_state_repo import (
    advance_financial_alert_state,
    list_financial_alert_states,
)
from services.budget_service import get_budget_service, list_budgets_service
from services.goal_service import get_goal_service, list_goals_service
from services.notification_preference_service import notification_preference_service
from services.notification_service import notification_service
from services.notification_types import (
    NotificationPreference,
    NotificationSeverity,
    NotificationType,
)


logger = logging.getLogger("nivra.financial_threshold_alerts")

BUDGET_THRESHOLDS = (80, 100)
GOAL_THRESHOLDS = (50, 75, 100)
GOAL_PERIOD_KEY = "lifetime"


@dataclass(frozen=True)
class ThresholdAlertEvent:
    source_kind: str
    source_id: int
    period_key: str
    milestone: int
    preference: NotificationPreference
    notification_type: NotificationType
    severity: NotificationSeverity
    title: str
    message: str
    route: str
    source_type: str
    dedupe_key: str


@dataclass
class ThresholdAlertResult:
    evaluated: int = 0
    delivered_or_deduplicated: int = 0
    suppressed: int = 0
    baselined: int = 0
    skipped: int = 0
    failed: int = 0

    def merge(self, other: "ThresholdAlertResult") -> None:
        self.evaluated += other.evaluated
        self.delivered_or_deduplicated += other.delivered_or_deduplicated
        self.suppressed += other.suppressed
        self.baselined += other.baselined
        self.skipped += other.skipped
        self.failed += other.failed


def financial_threshold_alerts_enabled() -> bool:
    return os.environ.get("FINANCIAL_ALERTS_ENABLED", "").strip().casefold() == "true"


def _highest_milestone(percentage: Decimal, thresholds: tuple[int, ...]) -> int:
    reached = [threshold for threshold in thresholds if percentage >= threshold]
    return max(reached, default=0)


def _budget_event(budget: dict, milestone: int) -> ThresholdAlertEvent:
    budget_id = int(budget["id"])
    period = str(budget["period"])
    percentage = Decimal(str(budget["usage_percentage"]))
    category = str(budget["category"]["name"])
    if milestone == 100:
        severity = NotificationSeverity.CRITICAL
        title = f"Orçamento de {category} atingiu o limite"
        message = f"O consumo no período chegou a {percentage:.2f}% do orçamento mensal."
    else:
        severity = NotificationSeverity.WARNING
        title = f"Orçamento de {category} em atenção"
        message = f"O consumo no período chegou a {percentage:.2f}% do orçamento mensal."
    return ThresholdAlertEvent(
        source_kind="budget",
        source_id=budget_id,
        period_key=period,
        milestone=milestone,
        preference=NotificationPreference.BUDGET_THRESHOLD,
        notification_type=NotificationType.BUDGET_ALERT,
        severity=severity,
        title=title,
        message=message,
        route="/budgets",
        source_type=f"budget_threshold_{milestone}",
        dedupe_key=f"budget_threshold:{budget_id}:{period}:{milestone}",
    )


def _goal_event(goal: dict, milestone: int) -> ThresholdAlertEvent:
    goal_id = int(goal["id"])
    percentage = Decimal(str(goal["progress_percentage"]))
    name = str(goal["name"])
    if milestone == 100:
        severity = NotificationSeverity.INFO
        title = f"Meta {name} concluída"
        message = f"A reserva lógica alcançou {percentage:.2f}% do valor-alvo."
    else:
        severity = NotificationSeverity.INFO
        title = f"Meta {name} chegou a {milestone}%"
        message = f"A reserva lógica alcançou {percentage:.2f}% do valor-alvo."
    return ThresholdAlertEvent(
        source_kind="goal",
        source_id=goal_id,
        period_key=GOAL_PERIOD_KEY,
        milestone=milestone,
        preference=NotificationPreference.GOAL_PROGRESS,
        notification_type=NotificationType.GOAL_ALERT,
        severity=severity,
        title=title,
        message=message,
        route="/goals",
        source_type=f"goal_progress_{milestone}",
        dedupe_key=f"goal_progress:{goal_id}:{milestone}",
    )


class FinancialThresholdAlertService:
    def _process(
        self,
        usuario_id: int,
        event: ThresholdAlertEvent | None,
        *,
        current_milestone: int,
        previous_milestone: int | None,
        baseline_missing: bool,
        preferences: dict[str, bool],
    ) -> ThresholdAlertResult:
        result = ThresholdAlertResult(evaluated=1)
        if previous_milestone is None and baseline_missing:
            assert event is not None
            advance_financial_alert_state(
                usuario_id,
                event.source_kind,
                event.source_id,
                event.period_key,
                current_milestone,
            )
            result.baselined = 1
            return result
        previous = previous_milestone or 0
        if current_milestone <= previous or event is None:
            result.skipped = 1
            return result
        try:
            if not preferences[event.preference.value]:
                notification_preference_service.suppress_event(
                    usuario_id, event.preference, event.dedupe_key
                )
                result.suppressed = 1
            elif notification_preference_service.event_was_suppressed(
                usuario_id, event.dedupe_key
            ):
                result.suppressed = 1
            else:
                notification_service.notify(
                    usuario_id,
                    event.notification_type,
                    event.title,
                    event.message,
                    severity=event.severity,
                    metadata={
                        "route": event.route,
                        "source_type": event.source_type,
                        "source_id": str(event.source_id),
                    },
                    dedupe_key=event.dedupe_key,
                )
                result.delivered_or_deduplicated = 1
            advance_financial_alert_state(
                usuario_id,
                event.source_kind,
                event.source_id,
                event.period_key,
                current_milestone,
            )
        except Exception:
            result.failed = 1
            logger.error(
                "financial_threshold_alert source=%s milestone=%s outcome=failed",
                event.source_kind,
                event.milestone,
            )
        return result

    def evaluate_user(
        self,
        usuario_id: int,
        *,
        reference: date,
        baseline_missing: bool = True,
    ) -> ThresholdAlertResult:
        if not financial_threshold_alerts_enabled():
            return ThresholdAlertResult()
        result = ThresholdAlertResult()
        preferences = notification_preference_service.get_effective(usuario_id)
        budget_states = list_financial_alert_states(usuario_id, "budget")
        period = reference.strftime("%Y-%m")
        for budget in list_budgets_service(usuario_id, period, today=reference):
            milestone = _highest_milestone(
                Decimal(str(budget["usage_percentage"])), BUDGET_THRESHOLDS
            )
            key = (int(budget["id"]), str(budget["period"]))
            event = _budget_event(budget, milestone) if milestone else None
            if event is None and key not in budget_states and baseline_missing:
                advance_financial_alert_state(usuario_id, "budget", key[0], key[1], 0)
                result.evaluated += 1
                result.baselined += 1
            else:
                result.merge(self._process(
                    usuario_id,
                    event,
                    current_milestone=milestone,
                    previous_milestone=budget_states.get(key),
                    baseline_missing=baseline_missing,
                    preferences=preferences,
                ))
        goal_states = list_financial_alert_states(usuario_id, "goal")
        for goal in list_goals_service(usuario_id, include_archived=False, today=reference):
            milestone = _highest_milestone(
                Decimal(str(goal["progress_percentage"])), GOAL_THRESHOLDS
            )
            key = (int(goal["id"]), GOAL_PERIOD_KEY)
            event = _goal_event(goal, milestone) if milestone else None
            if event is None and key not in goal_states and baseline_missing:
                advance_financial_alert_state(usuario_id, "goal", key[0], key[1], 0)
                result.evaluated += 1
                result.baselined += 1
            else:
                result.merge(self._process(
                    usuario_id,
                    event,
                    current_milestone=milestone,
                    previous_milestone=goal_states.get(key),
                    baseline_missing=baseline_missing,
                    preferences=preferences,
                ))
        return result

    def evaluate_budget(
        self,
        usuario_id: int,
        budget_id: int,
        *,
        reference: date,
        baseline_missing: bool = False,
    ) -> ThresholdAlertResult:
        if not financial_threshold_alerts_enabled():
            return ThresholdAlertResult()
        budget = get_budget_service(budget_id, usuario_id, today=reference)
        milestone = _highest_milestone(
            Decimal(str(budget["usage_percentage"])), BUDGET_THRESHOLDS
        )
        period = str(budget["period"])
        previous = list_financial_alert_states(usuario_id, "budget").get(
            (budget_id, period)
        )
        if milestone == 0 and previous is None:
            advance_financial_alert_state(usuario_id, "budget", budget_id, period, 0)
            return ThresholdAlertResult(evaluated=1, baselined=1)
        return self._process(
            usuario_id,
            _budget_event(budget, milestone) if milestone else None,
            current_milestone=milestone,
            previous_milestone=previous,
            baseline_missing=baseline_missing,
            preferences=notification_preference_service.get_effective(usuario_id),
        )

    def evaluate_goal(
        self,
        usuario_id: int,
        goal_id: int,
        *,
        reference: date,
        baseline_missing: bool = False,
        baseline_only: bool = False,
    ) -> ThresholdAlertResult:
        if not financial_threshold_alerts_enabled():
            return ThresholdAlertResult()
        goal = get_goal_service(goal_id, usuario_id, today=reference)
        if goal["lifecycle_status"] != "active":
            return ThresholdAlertResult(evaluated=1, skipped=1)
        milestone = _highest_milestone(
            Decimal(str(goal["progress_percentage"])), GOAL_THRESHOLDS
        )
        previous = list_financial_alert_states(usuario_id, "goal").get(
            (goal_id, GOAL_PERIOD_KEY)
        )
        if baseline_only:
            advance_financial_alert_state(
                usuario_id, "goal", goal_id, GOAL_PERIOD_KEY, milestone
            )
            return ThresholdAlertResult(evaluated=1, baselined=1)
        if milestone == 0 and previous is None:
            advance_financial_alert_state(usuario_id, "goal", goal_id, GOAL_PERIOD_KEY, 0)
            return ThresholdAlertResult(evaluated=1, baselined=1)
        return self._process(
            usuario_id,
            _goal_event(goal, milestone) if milestone else None,
            current_milestone=milestone,
            previous_milestone=previous,
            baseline_missing=baseline_missing,
            preferences=notification_preference_service.get_effective(usuario_id),
        )


financial_threshold_alert_service = FinancialThresholdAlertService()


def best_effort_evaluate_budget(usuario_id: int, budget_id: int, reference: date) -> None:
    try:
        financial_threshold_alert_service.evaluate_budget(
            usuario_id, budget_id, reference=reference
        )
    except Exception:
        logger.error("financial_threshold_hook source=budget outcome=failed")


def best_effort_evaluate_goal(
    usuario_id: int,
    goal_id: int,
    reference: date,
    *,
    baseline_missing: bool = False,
    baseline_only: bool = False,
) -> None:
    try:
        financial_threshold_alert_service.evaluate_goal(
            usuario_id,
            goal_id,
            reference=reference,
            baseline_missing=baseline_missing,
            baseline_only=baseline_only,
        )
    except Exception:
        logger.error("financial_threshold_hook source=goal outcome=failed")
