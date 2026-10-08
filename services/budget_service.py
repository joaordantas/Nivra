import calendar
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError

from repositories.budget_repo import (
    create_budget,
    delete_budget,
    get_budget,
    list_budgets,
    update_budget_limit,
)
from repositories.categoria_repo import buscar_categoria_por_id
from services.insight_service import obter_despesas_por_categoria_service


_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_CENT = Decimal("0.01")
_PERCENT = Decimal("0.01")
_NON_EXPENSE_SYSTEM_CATEGORIES = {"income", "transfers"}


class BudgetConflictError(ValueError):
    pass


def parse_period(value: str) -> date:
    if not isinstance(value, str) or not _MONTH.fullmatch(value):
        raise ValueError("Informe o período no formato AAAA-MM.")
    return date.fromisoformat(f"{value}-01")


def normalize_money(value: object) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Informe um limite monetário válido.") from exc
    if not amount.is_finite():
        raise ValueError("Informe um limite monetário válido.")
    amount = amount.quantize(_CENT, rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise ValueError("O limite deve ser maior que zero.")
    if amount >= Decimal("1000000000000"):
        raise ValueError("O limite informado excede o valor permitido.")
    return amount


def _month_end(period: date) -> date:
    return period.replace(day=calendar.monthrange(period.year, period.month)[1])


def _category_for_budget(category_id: int, user_id: int) -> tuple:
    category = buscar_categoria_por_id(category_id, user_id)
    if category is None:
        raise ValueError("Categoria não encontrada.")
    if category[2] in _NON_EXPENSE_SYSTEM_CATEGORIES:
        raise ValueError("Escolha uma categoria de despesa para o orçamento.")
    return category


def _format_budget(row: tuple, spent_by_category: dict[int, Decimal]) -> dict:
    budget_id, _user_id, category_id, category_name, category_key, period, limit, created, updated = row
    limit_amount = normalize_money(limit)
    spent = spent_by_category.get(int(category_id), Decimal("0.00")).quantize(_CENT)
    remaining = (limit_amount - spent).quantize(_CENT)
    percentage = (spent * Decimal("100") / limit_amount).quantize(
        _PERCENT, rounding=ROUND_HALF_UP
    )
    return {
        "id": int(budget_id),
        "period": str(period)[:7],
        "category": {
            "id": int(category_id),
            "name": str(category_name),
            "system_key": str(category_key) if category_key is not None else None,
        },
        "limit": limit_amount,
        "spent": spent,
        "remaining": remaining,
        "usage_percentage": percentage,
        "created_at": str(created),
        "updated_at": str(updated),
    }


def _spent_for_rows(user_id: int, period: date, rows: list[tuple], today: date) -> dict[int, Decimal]:
    if not rows or period > today:
        return {}
    effective_end = min(_month_end(period), today)
    category_ids = {int(row[2]) for row in rows}
    return {
        category_id: amount
        for category_id, amount in obter_despesas_por_categoria_service(
            user_id, period, effective_end
        ).items()
        if category_id in category_ids
    }


def create_budget_service(
    user_id: int, category_id: int, period_value: str, limit_value: object,
    *, today: date | None = None,
) -> dict:
    period = parse_period(period_value)
    limit = normalize_money(limit_value)
    _category_for_budget(category_id, user_id)
    try:
        budget_id = create_budget(user_id, category_id, period, limit)
    except IntegrityError as exc:
        raise BudgetConflictError("Já existe um orçamento para esta categoria no período.") from exc
    result = get_budget_service(budget_id, user_id, today=today)
    from services.financial_threshold_alert_service import best_effort_evaluate_budget

    best_effort_evaluate_budget(user_id, budget_id, today or date.today())
    return result


def list_budgets_service(
    user_id: int, period_value: str, *, today: date | None = None,
) -> list[dict]:
    period = parse_period(period_value)
    rows = list_budgets(user_id, period)
    spent = _spent_for_rows(user_id, period, rows, today or date.today())
    return [_format_budget(row, spent) for row in rows]


def get_budget_service(
    budget_id: int, user_id: int, *, today: date | None = None,
) -> dict:
    row = get_budget(budget_id, user_id)
    if row is None:
        raise LookupError("Orçamento não encontrado.")
    period = date.fromisoformat(str(row[5])[:10])
    spent = _spent_for_rows(user_id, period, [row], today or date.today())
    return _format_budget(row, spent)


def update_budget_service(
    budget_id: int, user_id: int, limit_value: object, *, today: date | None = None,
) -> dict:
    if get_budget(budget_id, user_id) is None:
        raise LookupError("Orçamento não encontrado.")
    update_budget_limit(budget_id, user_id, normalize_money(limit_value))
    result = get_budget_service(budget_id, user_id, today=today)
    from services.financial_threshold_alert_service import best_effort_evaluate_budget

    best_effort_evaluate_budget(user_id, budget_id, today or date.today())
    return result


def delete_budget_service(budget_id: int, user_id: int) -> bool:
    return delete_budget(budget_id, user_id)
