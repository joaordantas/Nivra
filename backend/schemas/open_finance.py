from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
