from typing import Literal

from pydantic import BaseModel


class InsightPeriod(BaseModel):
    start: str
    end: str
    previous_start: str
    previous_end: str


class InsightSummary(BaseModel):
    income: float
    expenses: float
    savings: float


class PeriodComparison(BaseModel):
    expense_change_amount: float
    expense_change_percent: float | None
    income_change_amount: float
    income_change_percent: float | None
    savings_change_amount: float


class CategoryInsight(BaseModel):
    category_id: int | None
    category: str
    category_key: str | None
    total: float
    percentage: float


class UnusualExpense(BaseModel):
    id: int
    description: str
    amount: float
    date: str
    category: str
    account: str
    source: Literal["manual", "open_finance", "card"]
    baseline: float
    times_baseline: float


class LargestExpense(BaseModel):
    id: int
    description: str
    amount: float
    date: str
    category: str
    account: str
    source: Literal["manual", "open_finance", "card"]
    percentage: float


class MonthlyTrendPoint(InsightSummary):
    month: str
    start: str
    end: str


class MonthlyTrend(BaseModel):
    comparison_basis: Literal["same_day", "full_month"]
    months_analyzed: int
    points: list[MonthlyTrendPoint]
    expense_direction: Literal["up", "down", "stable", "insufficient_data"]
    expense_change_percent: float | None
    income_direction: Literal["up", "down", "stable", "insufficient_data"]
    income_change_percent: float | None
    savings_direction: Literal["up", "down", "stable"]
    savings_change_amount: float
    sustained_expense_growth: bool


class AttentionItem(BaseModel):
    code: str
    severity: Literal["info", "positive", "warning", "danger"]
    title: str
    description: str
    reason: str
    action_label: str | None
    action_path: str | None


class MonthlyProjection(BaseModel):
    as_of: str
    realized: InsightSummary
    known_future: InsightSummary
    projected: InsightSummary
    known_future_entries: int


class CardCommitmentDetail(BaseModel):
    card_id: int
    name: str
    total_limit: float
    committed: float
    available: float
    committed_percent: float | None
    current_invoice_amount: float
    closing_date: str | None
    due_date: str | None
    invoice_status: Literal["aberta", "fechada", "paga", "vencida"] | None
    next_due_invoice_amount: float
    next_due_date: str | None
    next_due_status: Literal["aberta", "fechada", "paga", "vencida"] | None


class CardCommitmentSummary(BaseModel):
    total_limit: float
    total_committed: float
    total_available: float
    committed_percent: float | None
    active_cards: int
    cards: list[CardCommitmentDetail]


class FinancialInsights(BaseModel):
    period: InsightPeriod
    summary: InsightSummary
    previous_summary: InsightSummary
    comparison: PeriodComparison
    top_expense_categories: list[CategoryInsight]
    top_income_categories: list[CategoryInsight]
    unusual_expenses: list[UnusualExpense]
    largest_expenses: list[LargestExpense]
    monthly_trend: MonthlyTrend
    monthly_projection: MonthlyProjection
    card_commitment: CardCommitmentSummary
    attention: list[AttentionItem]
