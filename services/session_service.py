from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from repositories.sessao_repo import (
    atualizar_csrf_sessao,
    buscar_sessao,
    criar_sessao,
    limpar_sessoes_expiradas,
    revogar_sessao,
)


SESSION_COOKIE = "nivra_session"
CSRF_COOKIE = "nivra_csrf"
DEFAULT_SESSION_HOURS = 168


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    usuario: str
    email: str
    tipo_perfil: str
    token_hash: str
    csrf_hash: str
    email_verificado: bool
    email_verificado_em: str | None


def gerar_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_duration_seconds() -> int:
    raw_hours = os.environ.get("SESSION_TTL_HOURS", str(DEFAULT_SESSION_HOURS))
    try:
        hours = int(raw_hours)
    except ValueError as exc:
        raise RuntimeError("SESSION_TTL_HOURS deve ser um numero inteiro.") from exc
    if hours < 1 or hours > 24 * 365:
        raise RuntimeError("SESSION_TTL_HOURS deve ficar entre 1 e 8760 horas.")
    return hours * 3600


def cookie_is_secure() -> bool:
    app_env = os.environ.get("APP_ENV", "development").strip().lower()
    vercel_env = os.environ.get("VERCEL_ENV", "").strip().lower()
    return app_env == "production" or vercel_env == "production"


def criar_sessao_service(usuario_id: int, csrf_token: str) -> str:
    limpar_sessoes_expiradas()
    raw_token = gerar_token()
    expira_em = datetime.now(timezone.utc) + timedelta(seconds=session_duration_seconds())
    criar_sessao(usuario_id, hash_token(raw_token), hash_token(csrf_token), expira_em)
    return raw_token


def _parse_datetime(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def autenticar_sessao(raw_token: str | None) -> AuthenticatedUser | None:
    if not raw_token:
        return None
    token_hash = hash_token(raw_token)
    row = buscar_sessao(token_hash)
    if row is None:
        return None
    if _parse_datetime(row[6]) <= datetime.now(timezone.utc):
        revogar_sessao(token_hash)
        return None
    return AuthenticatedUser(
        id=int(row[0]),
        usuario=str(row[1]),
        email=str(row[2]),
        tipo_perfil=str(row[3]),
        token_hash=str(row[4]),
        csrf_hash=str(row[5]),
        email_verificado=bool(row[7]),
        email_verificado_em=str(row[8]) if row[8] is not None else None,
    )


def rotacionar_csrf_service(
    raw_session_token: str | None,
    current_csrf_token: str | None = None,
) -> str:
    if raw_session_token:
        current_user = autenticar_sessao(raw_session_token)
        if current_user:
            if current_csrf_token and secrets.compare_digest(
                hash_token(current_csrf_token), current_user.csrf_hash
            ):
                return current_csrf_token
            csrf_token = gerar_token()
            atualizar_csrf_sessao(current_user.token_hash, hash_token(csrf_token))
            return csrf_token
    return gerar_token()


def validar_csrf_service(
    current_user: AuthenticatedUser,
    header_token: str | None,
    cookie_token: str | None,
) -> bool:
    if not header_token or not cookie_token:
        return False
    if not secrets.compare_digest(header_token, cookie_token):
        return False
    return secrets.compare_digest(hash_token(header_token), current_user.csrf_hash)


def revogar_sessao_service(raw_token: str | None) -> None:
    if raw_token:
        revogar_sessao(hash_token(raw_token))
