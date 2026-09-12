from datetime import datetime, timedelta, timezone

from repositories.auth_token_repo import (
    buscar_ultimo_token_ativo,
    confirmar_email_com_token,
    criar_token_substituindo_anteriores,
    redefinir_senha_com_token,
    revogar_token_por_hash,
)
from repositories.usuario_repo import buscar_usuario_por_email, buscar_usuario_por_id
from services.auth_service import validar_senha_nova
from services.email_service import (
    EmailDeliveryError,
    enviar_redefinicao_senha,
    enviar_verificacao_email,
)
from services.session_service import gerar_token, hash_token
from utils.security import hash_senha


EMAIL_VERIFICATION = "email_verification"
PASSWORD_RESET = "password_reset"
EMAIL_VERIFICATION_HOURS = 24
PASSWORD_RESET_MINUTES = 30
RESEND_COOLDOWN_SECONDS = 60


class VerificationCooldownError(ValueError):
    def __init__(self, retry_after: int):
        super().__init__("Aguarde antes de solicitar outro e-mail.")
        self.retry_after = max(1, retry_after)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str | datetime) -> datetime:
    parsed = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(value.replace("Z", "+00:00"))
    )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _emitir_token(usuario_id: int, finalidade: str, validade: timedelta) -> str:
    agora = _now()
    token = gerar_token()
    criar_token_substituindo_anteriores(
        usuario_id,
        finalidade,
        hash_token(token),
        agora + validade,
        agora,
    )
    return token


def solicitar_verificacao_email(
    usuario_id: int,
    *,
    respeitar_cooldown: bool = True,
) -> bool:
    usuario = buscar_usuario_por_id(usuario_id)
    if usuario is None or bool(usuario[5]):
        return False
    agora = _now()
    if respeitar_cooldown:
        ultimo = buscar_ultimo_token_ativo(usuario_id, EMAIL_VERIFICATION)
        if ultimo is not None:
            decorrido = (agora - _parse_datetime(ultimo[0])).total_seconds()
            if decorrido < RESEND_COOLDOWN_SECONDS:
                raise VerificationCooldownError(
                    int(RESEND_COOLDOWN_SECONDS - decorrido + 0.999)
                )
    token = _emitir_token(
        usuario_id,
        EMAIL_VERIFICATION,
        timedelta(hours=EMAIL_VERIFICATION_HOURS),
    )
    try:
        enviar_verificacao_email(str(usuario[2]), token)
        return True
    except EmailDeliveryError:
        revogar_token_por_hash(hash_token(token))
        return False


def verificar_email_service(token: str) -> bool:
    if not token:
        return False
    return confirmar_email_com_token(hash_token(token), _now()) is not None


def solicitar_redefinicao_senha(email: str) -> None:
    usuario = buscar_usuario_por_email(email.strip().lower())
    if usuario is None:
        return
    token = _emitir_token(
        int(usuario[0]),
        PASSWORD_RESET,
        timedelta(minutes=PASSWORD_RESET_MINUTES),
    )
    try:
        enviar_redefinicao_senha(str(usuario[2]), token)
    except EmailDeliveryError:
        revogar_token_por_hash(hash_token(token))


def redefinir_senha_service(
    token: str,
    nova_senha: str,
    confirmar_senha: str,
) -> bool:
    if nova_senha != confirmar_senha:
        raise ValueError("A confirmação da nova senha não corresponde.")
    validar_senha_nova(nova_senha)
    if not token:
        return False
    return (
        redefinir_senha_com_token(
            hash_token(token),
            hash_senha(nova_senha),
            _now(),
        )
        is not None
    )
