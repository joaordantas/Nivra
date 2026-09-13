from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AccountType = Literal["corrente", "poupanca", "digital", "dinheiro", "outro"]


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str = Field(min_length=1, max_length=60)
    tipo: AccountType = "digital"
    saldo_inicial: float = 0


class AccountUpdate(AccountCreate):
    pass


class AccountStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ativo: bool


class AccountResponse(BaseModel):
    id: int
    nome: str
    tipo: AccountType
    saldo_inicial: float
    saldo_atual: float
    ativo: bool
    principal: bool = False
    percentual_uso: float = 0
    mais_utilizada: bool = False
    origem: Literal["manual", "open_finance"] = "manual"
    conta_externa_id: int | None = None
    instituicao_nome: str | None = None
    ultima_sincronizacao_em: datetime | None = None


class TransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conta_origem_id: int = Field(ge=1)
    conta_destino_id: int = Field(ge=1)
    valor: float = Field(gt=0)
    descricao: str | None = Field(default=None, max_length=255)
    data: str


class TransferUpdate(TransferCreate):
    pass


class TransferResponse(BaseModel):
    id: int
    conta_origem_id: int
    conta_destino_id: int
    valor: float
    descricao: str | None = None
    data: str


class TransferListItem(TransferResponse):
    conta_origem: str
    conta_destino: str
