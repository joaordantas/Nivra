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


class NotificationPreference(StrEnum):
    INVOICE_DUE_SOON = "invoice_due_soon"
    INVOICE_OVERDUE = "invoice_overdue"
    CARD_LIMIT = "card_limit"
    UNUSUAL_EXPENSE = "unusual_expense"
    WEEKLY_SUMMARY = "weekly_summary"
    MONTHLY_SUMMARY = "monthly_summary"


NOTIFICATION_TYPES = frozenset(item.value for item in NotificationType)
NOTIFICATION_SEVERITIES = frozenset(item.value for item in NotificationSeverity)
NOTIFICATION_PREFERENCES = frozenset(item.value for item in NotificationPreference)
