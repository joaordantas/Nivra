from __future__ import annotations

import json
import logging

from repositories.notification_repo import (
    count_unread_notifications,
    create_notification,
    delete_notification,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)
from services.notification_types import (
    NOTIFICATION_SEVERITIES,
    NOTIFICATION_TYPES,
    NotificationSeverity,
    NotificationType,
)


MAX_NOTIFICATION_TITLE_CHARS = 160
MAX_NOTIFICATION_MESSAGE_CHARS = 600
MAX_NOTIFICATION_DEDUPE_KEY_CHARS = 160
MAX_NOTIFICATION_METADATA_BYTES = 1_000
MAX_NOTIFICATION_PAGE_SIZE = 100
MAX_NOTIFICATION_OFFSET = 10_000
ALLOWED_METADATA_KEYS = frozenset({"route", "source_type", "source_id"})

logger = logging.getLogger("nivra.notifications")


class NotificationNotFoundError(ValueError):
    pass


def _log_event(event: str, outcome: str, **dimensions: str | int | bool) -> None:
    allowed = {"type", "severity", "deduplicated", "updated_count"}
    payload: dict[str, str | int | bool] = {"event": event, "outcome": outcome}
    payload.update({key: value for key, value in dimensions.items() if key in allowed})
    logger.info(
        "notification_event %s",
        json.dumps(payload, separators=(",", ":"), sort_keys=True),
    )


def _required_text(value: str, *, field: str, max_chars: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} nao pode ficar vazio.")
    if len(normalized) > max_chars:
        raise ValueError(f"{field} excede o limite de {max_chars} caracteres.")
    return normalized


def _normalize_metadata(metadata: dict[str, str | int | bool] | None) -> str:
    if metadata is None:
        return "{}"
    if not isinstance(metadata, dict):
        raise ValueError("Metadados devem ser um objeto simples.")
    unexpected = set(metadata) - ALLOWED_METADATA_KEYS
    if unexpected:
        raise ValueError("Metadados contem campos nao permitidos.")
    for key, value in metadata.items():
        if not isinstance(value, (str, int, bool)):
            raise ValueError("Metadados aceitam apenas valores escalares.")
        if isinstance(value, str) and len(value) > 200:
            raise ValueError(f"Metadado {key} excede o limite permitido.")
    route = metadata.get("route")
    if route is not None and (
        not isinstance(route, str)
        or not route.startswith("/")
        or route.startswith("//")
    ):
        raise ValueError("A rota da notificacao deve ser interna.")
    serialized = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    if len(serialized.encode("utf-8")) > MAX_NOTIFICATION_METADATA_BYTES:
        raise ValueError("Metadados excedem o limite permitido.")
    return serialized


def _notification_from_row(row: tuple) -> dict:
    (
        notification_id,
        notification_type,
        severity,
        title,
        message,
        metadata_json,
        _dedupe_key,
        read,
        created_at,
        read_at,
    ) = row
    return {
        "id": int(notification_id),
        "tipo": str(notification_type),
        "severidade": str(severity),
        "titulo": str(title),
        "mensagem": str(message),
        "metadados": json.loads(str(metadata_json)),
        "lida": bool(read),
        "criada_em": created_at,
        "lida_em": read_at,
    }


class NotificationService:
    def notify(
        self,
        usuario_id: int,
        notification_type: NotificationType | str,
        title: str,
        message: str,
        *,
        severity: NotificationSeverity | str = NotificationSeverity.INFO,
        metadata: dict[str, str | int | bool] | None = None,
        dedupe_key: str | None = None,
    ) -> dict:
        if usuario_id < 1:
            raise ValueError("Usuario invalido para notificacao.")
        normalized_type = str(notification_type)
        normalized_severity = str(severity)
        if normalized_type not in NOTIFICATION_TYPES:
            raise ValueError("Tipo de notificacao invalido.")
        if normalized_severity not in NOTIFICATION_SEVERITIES:
            raise ValueError("Severidade de notificacao invalida.")
        normalized_title = _required_text(
            title,
            field="Titulo",
            max_chars=MAX_NOTIFICATION_TITLE_CHARS,
        )
        normalized_message = _required_text(
            message,
            field="Mensagem",
            max_chars=MAX_NOTIFICATION_MESSAGE_CHARS,
        )
        normalized_dedupe = None
        if dedupe_key is not None:
            normalized_dedupe = _required_text(
                dedupe_key,
                field="Chave de deduplicacao",
                max_chars=MAX_NOTIFICATION_DEDUPE_KEY_CHARS,
            )
        row, created = create_notification(
            usuario_id,
            normalized_type,
            normalized_severity,
            normalized_title,
            normalized_message,
            _normalize_metadata(metadata),
            normalized_dedupe,
        )
        notification = _notification_from_row(row)
        _log_event(
            "created",
            "success",
            type=normalized_type,
            severity=normalized_severity,
            deduplicated=not created,
        )
        return notification

    def list(
        self,
        usuario_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
        unread_only: bool = False,
        notification_type: NotificationType | str | None = None,
    ) -> list[dict]:
        if not 1 <= limit <= MAX_NOTIFICATION_PAGE_SIZE:
            raise ValueError("Limite de pagina invalido.")
        if not 0 <= offset <= MAX_NOTIFICATION_OFFSET:
            raise ValueError("Offset de pagina invalido.")
        normalized_type = str(notification_type) if notification_type is not None else None
        if normalized_type is not None and normalized_type not in NOTIFICATION_TYPES:
            raise ValueError("Tipo de notificacao invalido.")
        return [
            _notification_from_row(row)
            for row in list_notifications(
                usuario_id,
                limit=limit,
                offset=offset,
                unread_only=unread_only,
                notification_type=normalized_type,
            )
        ]

    def unread_count(self, usuario_id: int) -> int:
        return count_unread_notifications(usuario_id)

    def mark_read(self, usuario_id: int, notification_id: int) -> dict:
        row = mark_notification_read(notification_id, usuario_id)
        if row is None:
            _log_event("read", "not_found")
            raise NotificationNotFoundError("Notificacao nao encontrada.")
        _log_event("read", "success")
        return _notification_from_row(row)

    def mark_all_read(self, usuario_id: int) -> int:
        updated = mark_all_notifications_read(usuario_id)
        _log_event("read_all", "success", updated_count=updated)
        return updated

    def delete(self, usuario_id: int, notification_id: int) -> bool:
        deleted = delete_notification(notification_id, usuario_id)
        _log_event("deleted", "success" if deleted else "not_found")
        return deleted


notification_service = NotificationService()
