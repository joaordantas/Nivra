from datetime import datetime

from pydantic import BaseModel, ConfigDict, StrictBool, model_validator

from services.notification_types import NotificationSeverity, NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    tipo: NotificationType
    severidade: NotificationSeverity
    titulo: str
    mensagem: str
    metadados: dict[str, str | int | bool]
    lida: bool
    criada_em: datetime
    lida_em: datetime | None


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int


class NotificationReadAllResponse(BaseModel):
    updated_count: int


class NotificationPreferencesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_due_soon: bool
    invoice_overdue: bool
    card_limit: bool
    unusual_expense: bool
    weekly_summary: bool
    monthly_summary: bool


class NotificationPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_due_soon: StrictBool | None = None
    invoice_overdue: StrictBool | None = None
    card_limit: StrictBool | None = None
    unusual_expense: StrictBool | None = None
    weekly_summary: StrictBool | None = None
    monthly_summary: StrictBool | None = None

    @model_validator(mode="after")
    def require_explicit_boolean(self):
        if not self.model_fields_set:
            raise ValueError("Informe ao menos uma preferencia para atualizar.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Preferencias aceitam apenas valores booleanos.")
        return self
