from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from services.session_service import hash_token


class EmailDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmailMessage:
    recipient: str
    subject: str
    text: str
    idempotency_key: str


class MemoryEmailProvider:
    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)


class ResendEmailProvider:
    endpoint = "https://api.resend.com/emails"

    def __init__(self, api_key: str, sender: str) -> None:
        self.api_key = api_key
        self.sender = sender

    def send(self, message: EmailMessage) -> None:
        payload = json.dumps(
            {
                "from": self.sender,
                "to": [message.recipient],
                "subject": message.subject,
                "text": message.text,
            }
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": message.idempotency_key,
                "User-Agent": "Nivra/0.2",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                if response.status < 200 or response.status >= 300:
                    raise EmailDeliveryError("O provedor de e-mail recusou o envio.")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise EmailDeliveryError("Não foi possível enviar o e-mail agora.") from exc


_provider_override: MemoryEmailProvider | ResendEmailProvider | None = None
_memory_provider = MemoryEmailProvider()


def set_email_provider_for_tests(provider: MemoryEmailProvider | None) -> None:
    global _provider_override
    _provider_override = provider


def _is_production() -> bool:
    return (
        os.environ.get("APP_ENV", "development").strip().lower() == "production"
        or os.environ.get("VERCEL_ENV", "").strip().lower() == "production"
    )


def _get_provider():
    if _provider_override is not None:
        return _provider_override
    provider_name = os.environ.get(
        "EMAIL_PROVIDER", "resend" if _is_production() else "memory"
    ).strip().lower()
    if provider_name == "memory" and not _is_production():
        return _memory_provider
    if provider_name != "resend":
        raise EmailDeliveryError("Provedor de e-mail não configurado.")
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = os.environ.get("EMAIL_FROM", "").strip()
    if not api_key or not sender:
        raise EmailDeliveryError("Provedor de e-mail não configurado.")
    return ResendEmailProvider(api_key, sender)


def _public_url() -> str:
    configured = os.environ.get("APP_PUBLIC_URL", "").strip().rstrip("/")
    if configured:
        if not configured.startswith(("http://", "https://")):
            raise EmailDeliveryError("APP_PUBLIC_URL inválida.")
        return configured
    if _is_production():
        raise EmailDeliveryError("APP_PUBLIC_URL não configurada.")
    return "http://127.0.0.1:5173"


def enviar_verificacao_email(recipient: str, token: str) -> None:
    link = f"{_public_url()}/verify-email#token={quote(token, safe='')}"
    _get_provider().send(
        EmailMessage(
            recipient=recipient,
            subject="Confirme seu e-mail na Nivra",
            text=(
                "Confirme seu e-mail para concluir a proteção da sua conta Nivra.\n\n"
                f"{link}\n\n"
                "Este link expira em 24 horas e pode ser usado apenas uma vez."
            ),
            idempotency_key=f"verify-{hash_token(token)}",
        )
    )


def enviar_redefinicao_senha(recipient: str, token: str) -> None:
    link = f"{_public_url()}/reset-password#token={quote(token, safe='')}"
    _get_provider().send(
        EmailMessage(
            recipient=recipient,
            subject="Redefina sua senha da Nivra",
            text=(
                "Recebemos uma solicitação para redefinir sua senha da Nivra.\n\n"
                f"{link}\n\n"
                "Este link expira em 30 minutos e pode ser usado apenas uma vez. "
                "Se você não fez a solicitação, ignore esta mensagem."
            ),
            idempotency_key=f"reset-{hash_token(token)}",
        )
    )
