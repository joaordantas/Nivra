from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InstallmentPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descricao: str = Field(min_length=1, max_length=255)
    valor_total: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    quantidade_parcelas: int = Field(ge=2)
    data_inicial: date
    tipo: Literal["entrada", "saida"]
    categoria_id: int | None = Field(default=None, ge=1)
    conta_id: int | None = Field(default=None, ge=1)


class InstallmentResponse(BaseModel):
    id: int
    numero_parcela: int
    quantidade_parcelas: int
    valor: float
    data: date
    tipo: Literal["entrada", "saida"]
    categoria_id: int | None = None
    categoria: str
    conta_id: int | None = None
    conta: str
    comentario: str | None = None
    status_temporal: Literal["data_atingida", "futura"]


class InstallmentPlanSummary(BaseModel):
    id: int
    descricao: str
    valor_total: float
    quantidade_parcelas: int
    data_inicial: date
    criado_em: datetime
    atualizado_em: datetime
    parcelas_persistidas: int
    valor_persistido: float
    primeira_parcela_data: date
    ultima_parcela_data: date
    parcelas_com_data_atingida: int
    parcelas_futuras: int
    proxima_parcela_data: date | None


class InstallmentPlanDetail(InstallmentPlanSummary):
    parcelas: list[InstallmentResponse]


class InstallmentPlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descricao: str = Field(min_length=1, max_length=255)
    categoria_id: int | None = Field(default=None, ge=1)
    conta_id: int | None = Field(default=None, ge=1)
