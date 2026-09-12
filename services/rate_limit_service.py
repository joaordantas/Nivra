from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone

from repositories.auth_rate_limit_repo import (
    contar_eventos,
    limpar_eventos,
    registrar_evento,
)


class RateLimitExceeded(RuntimeError):
    def __init__(self, retry_after: int):
        super().__init__("Muitas tentativas. Tente novamente mais tarde.")
        self.retry_after = max(1, retry_after)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_rate_subject(*parts: str) -> str:
    normalized = "|".join(part.strip().lower() for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _parse_datetime(value: str | datetime) -> datetime:
    parsed = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(value.replace("Z", "+00:00"))
    )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def verificar_limite(
    escopo: str,
    sujeito_hash: str,
    limite: int,
    janela_segundos: int,
    *,
    agora: datetime | None = None,
) -> None:
    momento = agora or _now()
    quantidade, mais_antigo = contar_eventos(
        escopo,
        sujeito_hash,
        momento - timedelta(seconds=janela_segundos),
    )
    if quantidade >= limite:
        retry_after = janela_segundos
        if mais_antigo is not None:
            restante = janela_segundos - (
                momento - _parse_datetime(mais_antigo)
            ).total_seconds()
            retry_after = max(1, math.ceil(restante))
        raise RateLimitExceeded(retry_after)


def consumir_limite(
    escopo: str,
    sujeito_hash: str,
    limite: int,
    janela_segundos: int,
    *,
    agora: datetime | None = None,
) -> None:
    momento = agora or _now()
    verificar_limite(escopo, sujeito_hash, limite, janela_segundos, agora=momento)
    registrar_evento(escopo, sujeito_hash, momento)


def registrar_falha(
    escopo: str,
    sujeito_hash: str,
    *,
    agora: datetime | None = None,
) -> None:
    registrar_evento(escopo, sujeito_hash, agora or _now())


def limpar_limite(escopo: str, sujeito_hash: str) -> None:
    limpar_eventos(escopo, sujeito_hash)
