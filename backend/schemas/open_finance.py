from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class ConnectTokenResponse(BaseModel):
    connect_token: str
    provider: Literal["pluggy"] = "pluggy"
    environment: Literal["sandbox"] = "sandbox"


class OpenFinanceConnectionComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: UUID


class OpenFinanceConnectionResponse(BaseModel):
    id: int
    provider: Literal["pluggy"]
    instituicao_nome: str
    status: str
    ambiente: Literal["sandbox", "production"]
    criada_em: datetime
    atualizada_em: datetime
    ultima_sincronizacao_em: datetime | None = None
    desconectada_em: datetime | None = None
    ultimo_evento_status: str | None = None
    ultimo_erro: str | None = None


class OpenFinanceSyncResponse(BaseModel):
    conexao_id: int
    contas_criadas: int
    contas_atualizadas: int
    contas_removidas: int
    transacoes_criadas: int
    transacoes_atualizadas: int
    transacoes_removidas: int
    transacoes_processadas: int


class OpenFinanceExternalAccountResponse(BaseModel):
    id: int
    nome: str
    tipo: str
    subtipo: str | None = None
    moeda: str
    saldo: float | None = None
    quantidade_transacoes: int
    conta_nivra_id: int | None = None
    conta_nivra_nome: str | None = None
    pode_vincular_conta_nivra: bool


class OpenFinanceAccountLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conta_nivra_id: int = Field(ge=1)


class OpenFinanceAccountLinkResponse(BaseModel):
    conta_externa_id: int
    conta_nivra_id: int
    conta_nivra_nome: str


class PluggyWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    event: str = Field(min_length=1, max_length=60)
    event_id: str = Field(
        min_length=1,
        max_length=100,
        validation_alias=AliasChoices("eventId", "event_id"),
        serialization_alias="eventId",
    )
    item_id: str | None = Field(
        default=None,
        max_length=120,
        validation_alias=AliasChoices("itemId", "item_id"),
        serialization_alias="itemId",
    )
    account_id: str | None = Field(
        default=None,
        max_length=120,
        validation_alias=AliasChoices("accountId", "account_id"),
        serialization_alias="accountId",
    )
    transaction_ids: list[str] = Field(
        default_factory=list,
        max_length=1000,
        validation_alias=AliasChoices("transactionIds", "transaction_ids"),
        serialization_alias="transactionIds",
    )
    transactions_created_at_from: str | None = Field(
        default=None,
        max_length=80,
        validation_alias=AliasChoices(
            "transactionsCreatedAtFrom",
            "transactions_created_at_from",
        ),
        serialization_alias="transactionsCreatedAtFrom",
    )
    error: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_event_fields(self) -> "PluggyWebhookPayload":
        supported = {
            "item/updated",
            "item/error",
            "item/deleted",
            "transactions/created",
            "transactions/updated",
            "transactions/deleted",
        }
        if self.event not in supported:
            return self
        if not self.item_id:
            raise ValueError("itemId e obrigatorio para este evento.")
        if self.event.startswith("transactions/") and not self.account_id:
            raise ValueError("accountId e obrigatorio para eventos de transacao.")
        if self.event in {"transactions/updated", "transactions/deleted"}:
            if not self.transaction_ids:
                raise ValueError("transactionIds e obrigatorio para este evento.")
        if self.event == "transactions/created" and not (
            self.transaction_ids or self.transactions_created_at_from
        ):
            raise ValueError(
                "transactionsCreatedAtFrom ou transactionIds e obrigatorio."
            )
        if any(not value.strip() or len(value) > 120 for value in self.transaction_ids):
            raise ValueError("transactionIds contem um identificador invalido.")
        if len(set(self.transaction_ids)) != len(self.transaction_ids):
            raise ValueError("transactionIds nao pode conter duplicacoes.")
        return self


class PluggyWebhookResponse(BaseModel):
    received: bool = True
    event_id: str
    status: Literal["processed", "duplicate", "ignored"]
    processed_count: int = 0
