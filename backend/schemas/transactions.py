from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valor: float = Field(gt=0)
    tipo: Literal["entrada", "saida"]
    categoria_id: int | None = Field(default=None, ge=1)
    comentario: str | None = Field(default=None, max_length=255)
    data: str
    conta_id: int | None = Field(default=None, ge=1)


class TransactionUpdate(TransactionCreate):
    pass


class TransactionListItem(BaseModel):
    id: int
    valor: float
    tipo: str
    categoria_id: int | None = None
    categoria: str
    comentario: str | None = None
    data: str
    conta_id: int | None = None
    conta: str = "Sem conta"
    origem: Literal["manual", "open_finance"] = "manual"
    editavel: bool = True
    status_conciliacao: Literal[
        "pendente", "possivel_correspondencia", "ambigua", "conciliada", "ignorada", "reaberta"
    ] | None = None
    transacao_nivra_id: int | None = None
    conciliada_com_banco: bool = False
    neutra: bool = False
    instituicao_nome: str | None = None
    ultima_sincronizacao_em: datetime | None = None


class TransactionSummary(BaseModel):
    entradas: float
    saidas: float
    saldo: float


class ReconciliationResponse(BaseModel):
    transacao_bancaria_id: int
    transacao_nivra_id: int | None = None
    status: Literal["conciliada", "rejeitada"]


class ReconciliationCandidate(BaseModel):
    transacao_nivra_id: int
    descricao: str
    valor: float
    data: str
    direcao: Literal["entrada", "saida"]
    confianca: Literal["alta", "media", "baixa"]
    motivos: list[str]


class ReconciliationSuggestion(BaseModel):
    transacao_bancaria_id: int
    descricao: str
    valor: float
    data: str
    direcao: Literal["entrada", "saida"]
    conta_id: int
    conta: str
    instituicao_nome: str
    ambigua: bool
    candidatos: list[ReconciliationCandidate]


class ReconciliationBatchResponse(BaseModel):
    confirmadas: int
    solicitadas: int
