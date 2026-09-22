from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MAX_LUMI_HISTORY_MESSAGES = 6
MAX_LUMI_HISTORY_ITEM_CHARS = 4_000
MAX_LUMI_HISTORY_TOTAL_CHARS = 12_000


class LumiHistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_LUMI_HISTORY_ITEM_CHARS)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Uma mensagem do contexto não pode ficar vazia.")
        return normalized


class LumiMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2_000)
    history: list[LumiHistoryMessage] = Field(
        default_factory=list,
        max_length=MAX_LUMI_HISTORY_MESSAGES,
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("A mensagem não pode ficar vazia.")
        return normalized

    @model_validator(mode="after")
    def validate_history(self) -> "LumiMessageRequest":
        if len(self.history) % 2 != 0:
            raise ValueError("O contexto deve conter turnos completos.")
        for index, item in enumerate(self.history):
            expected_role = "user" if index % 2 == 0 else "assistant"
            if item.role != expected_role:
                raise ValueError("O contexto deve alternar usuário e Lumi.")
        total_chars = sum(len(item.content) for item in self.history)
        if total_chars > MAX_LUMI_HISTORY_TOTAL_CHARS:
            raise ValueError("O contexto temporário excedeu o limite permitido.")
        return self


class LumiMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["message"] = "message"
    message: str
    tools_used: list[str]


class LumiActionEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str


class LumiActionProposalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: str | None
    description: str | None
    date: str | None
    account: LumiActionEntity | None
    category: LumiActionEntity | None


class LumiActionConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_id: str
    status: Literal["pending"]
    expires_at: datetime


class LumiActionProposalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["action_proposal"] = "action_proposal"
    message: str
    tools_used: list[str] = Field(default_factory=list)
    action_type: Literal["create_expense", "create_income"]
    summary: str
    payload: LumiActionProposalPayload
    missing_fields: list[str]
    warnings: list[str]
    confirmation: LumiActionConfirmation | None
    execution_enabled: bool = False


LumiResponse = Annotated[
    Union[LumiMessageResponse, LumiActionProposalResponse],
    Field(discriminator="type"),
]


class LumiActionConfirmationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: Literal["create_expense", "create_income"]
    status: Literal["pending", "confirmed", "cancelled", "expired", "executed"]
    expires_at: datetime
    message: str
    execution_enabled: bool = False
    transaction_id: int | None = None


class LumiActionDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LumiActionTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_id: str = Field(min_length=32, max_length=128)
