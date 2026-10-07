from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=600)
    target_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    deadline: str | None = None


class GoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=600)
    target_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    deadline: str | None = None
    lifecycle_status: Literal["active", "archived"] | None = None


class GoalResponse(BaseModel):
    id: int
    name: str
    description: str | None
    target_amount: Decimal
    saved_amount: Decimal
    remaining_amount: Decimal
    progress_percentage: Decimal
    deadline: str | None
    lifecycle_status: Literal["active", "archived"]
    completed: bool
    created_at: str
    updated_at: str


class GoalMovementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    type: Literal["contribution", "withdrawal"]
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    effective_date: str
    description: str | None = Field(default=None, max_length=300)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=64)


class GoalMovementResponse(BaseModel):
    id: int
    goal_id: int
    type: Literal["contribution", "withdrawal"]
    amount: Decimal
    effective_date: str
    description: str | None
    idempotency_key: str | None
    effective: bool
    created_at: str


class GoalDeleteResponse(BaseModel):
    outcome: Literal["deleted", "archived"]
