from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
