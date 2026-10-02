from enum import StrEnum


class NotificationType(StrEnum):
    FINANCIAL_ALERT = "financial_alert"
    CARD_ALERT = "card_alert"
    BUDGET_ALERT = "budget_alert"
    GOAL_ALERT = "goal_alert"
    SYSTEM = "system"
    SUMMARY = "summary"


class NotificationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


NOTIFICATION_TYPES = frozenset(item.value for item in NotificationType)
NOTIFICATION_SEVERITIES = frozenset(item.value for item in NotificationSeverity)
