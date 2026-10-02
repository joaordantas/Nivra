from datetime import datetime

from pydantic import BaseModel, ConfigDict

from services.notification_types import NotificationSeverity, NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    tipo: NotificationType
    severidade: NotificationSeverity
    titulo: str
    mensagem: str
    metadados: dict[str, str | int | bool]
    chave_dedupe: str | None
    lida: bool
    criada_em: datetime
    lida_em: datetime | None


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int


class NotificationReadAllResponse(BaseModel):
    updated_count: int
