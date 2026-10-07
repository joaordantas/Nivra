from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from backend.dependencies.auth import CurrentUser, CurrentUserCsrf
from backend.schemas.budgets import BudgetCreate, BudgetResponse, BudgetUpdate
from services.budget_service import (
    BudgetConflictError,
    create_budget_service,
    delete_budget_service,
    get_budget_service,
    list_budgets_service,
    update_budget_service,
)


router = APIRouter(prefix="/budgets", tags=["budgets"])


def _current_period() -> str:
    return date.today().strftime("%Y-%m")


@router.get("", response_model=list[BudgetResponse])
def list_budgets(
    current_user: CurrentUser,
    period: str = Query(default_factory=_current_period),
) -> list[BudgetResponse]:
    try:
        return [BudgetResponse(**item) for item in list_budgets_service(current_user.id, period)]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(payload: BudgetCreate, current_user: CurrentUserCsrf) -> BudgetResponse:
    try:
        return BudgetResponse(**create_budget_service(
            current_user.id, payload.category_id, payload.period, payload.limit
        ))
    except BudgetConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{budget_id}", response_model=BudgetResponse)
def get_budget(budget_id: int, current_user: CurrentUser) -> BudgetResponse:
    try:
        return BudgetResponse(**get_budget_service(budget_id, current_user.id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: int, payload: BudgetUpdate, current_user: CurrentUserCsrf,
) -> BudgetResponse:
    try:
        return BudgetResponse(**update_budget_service(budget_id, current_user.id, payload.limit))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(budget_id: int, current_user: CurrentUserCsrf) -> None:
    if not delete_budget_service(budget_id, current_user.id):
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
