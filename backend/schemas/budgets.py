from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BudgetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    category_id: int = Field(gt=0)
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    limit: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class BudgetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    limit: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class BudgetCategoryResponse(BaseModel):
    id: int
    name: str
    system_key: str | None


class BudgetResponse(BaseModel):
    id: int
    period: str
    category: BudgetCategoryResponse
    limit: Decimal
    spent: Decimal
    remaining: Decimal
    usage_percentage: Decimal
    created_at: str
    updated_at: str
