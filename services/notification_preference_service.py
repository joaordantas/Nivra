from __future__ import annotations

from repositories.notification_preference_repo import (
    list_explicit_notification_preferences,
    notification_event_was_suppressed,
    record_notification_preference_suppression,
    upsert_notification_preferences,
)
from services.notification_types import (
    NOTIFICATION_PREFERENCES,
    NotificationPreference,
)


DEFAULT_NOTIFICATION_PREFERENCES = {
    preference.value: True for preference in NotificationPreference
}


class NotificationPreferenceService:
    def get_effective(self, usuario_id: int) -> dict[str, bool]:
        if usuario_id < 1:
            raise ValueError("Usuario invalido para preferencias de notificacao.")
        effective = dict(DEFAULT_NOTIFICATION_PREFERENCES)
        effective.update(list_explicit_notification_preferences(usuario_id))
        return effective

    def update(self, usuario_id: int, updates: dict[str, bool]) -> dict[str, bool]:
        if usuario_id < 1:
            raise ValueError("Usuario invalido para preferencias de notificacao.")
        if not updates:
            raise ValueError("Informe ao menos uma preferencia para atualizar.")
        unexpected = set(updates) - NOTIFICATION_PREFERENCES
        if unexpected:
            raise ValueError("Preferencia de notificacao invalida.")
        if any(type(value) is not bool for value in updates.values()):
            raise ValueError("Preferencias de notificacao aceitam apenas booleanos.")
        upsert_notification_preferences(usuario_id, updates)
        return self.get_effective(usuario_id)

    def suppress_event(
        self,
        usuario_id: int,
        preference: NotificationPreference,
        dedupe_key: str,
    ) -> None:
        if not dedupe_key or len(dedupe_key) > 160:
            raise ValueError("Chave de evento invalida para supressao.")
        record_notification_preference_suppression(
            usuario_id,
            preference.value,
            dedupe_key,
        )

    def event_was_suppressed(self, usuario_id: int, dedupe_key: str) -> bool:
        return notification_event_was_suppressed(usuario_id, dedupe_key)


notification_preference_service = NotificationPreferenceService()
