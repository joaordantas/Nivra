from fastapi import APIRouter, HTTPException, Query, status

from backend.dependencies.auth import CurrentUser, CurrentUserCsrf
from backend.schemas.goals import GoalCreate, GoalDeleteResponse, GoalMovementCreate, GoalMovementResponse, GoalResponse, GoalUpdate
from services.goal_service import GoalConflictError, add_goal_movement_service, create_goal_service, delete_goal_service, get_goal_service, list_goal_movements_service, list_goals_service, update_goal_service


router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalResponse])
def list_financial_goals(current_user: CurrentUser, include_archived: bool = Query(True)) -> list[GoalResponse]:
    return [GoalResponse(**item) for item in list_goals_service(current_user.id, include_archived=include_archived)]


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_financial_goal(payload: GoalCreate, current_user: CurrentUserCsrf) -> GoalResponse:
    try:
        return GoalResponse(**create_goal_service(current_user.id, payload.name, payload.description, payload.target_amount, payload.deadline))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{goal_id}", response_model=GoalResponse)
def get_financial_goal(goal_id: int, current_user: CurrentUser) -> GoalResponse:
    try:
        return GoalResponse(**get_goal_service(goal_id, current_user.id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_financial_goal(goal_id: int, payload: GoalUpdate, current_user: CurrentUserCsrf) -> GoalResponse:
    try:
        return GoalResponse(**update_goal_service(goal_id, current_user.id, payload.model_dump(exclude_unset=True)))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{goal_id}", response_model=GoalDeleteResponse)
def delete_financial_goal(goal_id: int, current_user: CurrentUserCsrf) -> GoalDeleteResponse:
    try:
        return GoalDeleteResponse(outcome=delete_goal_service(goal_id, current_user.id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{goal_id}/movements", response_model=list[GoalMovementResponse])
def list_financial_goal_movements(goal_id: int, current_user: CurrentUser) -> list[GoalMovementResponse]:
    try:
        return [GoalMovementResponse(**item) for item in list_goal_movements_service(goal_id, current_user.id)]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{goal_id}/movements", response_model=GoalMovementResponse, status_code=status.HTTP_201_CREATED)
def create_financial_goal_movement(goal_id: int, payload: GoalMovementCreate, current_user: CurrentUserCsrf) -> GoalMovementResponse:
    try:
        return GoalMovementResponse(**add_goal_movement_service(current_user.id, goal_id, payload.type, payload.amount, payload.effective_date, payload.description, payload.idempotency_key))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GoalConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
