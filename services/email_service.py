from __future__ import annotations

import json
import os
from dataclasses import dataclass
from email.utils import parseaddr
from html import escape
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from email_validator import EmailNotValidError, validate_email

from services.session_service import hash_token


class EmailDeliveryError(RuntimeError):
    pass


class EmailProvider(Protocol):
    def send(self, message: "EmailMessage") -> None: ...


@dataclass(frozen=True)
class EmailMessage:
    recipient: str
    subject: str
    text: str
    html: str
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
                "html": message.html,
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
        except HTTPError as exc:
            raise EmailDeliveryError(
                f"O provedor de e-mail recusou o envio (HTTP {exc.code})."
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise EmailDeliveryError("Não foi possível enviar o e-mail agora.") from exc


_provider_override: EmailProvider | None = None
_memory_provider = MemoryEmailProvider()


def set_email_provider_for_tests(provider: EmailProvider | None) -> None:
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
    configured_provider = os.environ.get("EMAIL_PROVIDER", "").strip()
    if _is_production() and not configured_provider:
        raise EmailDeliveryError("EMAIL_PROVIDER não configurado em produção.")
    provider_name = (configured_provider or "memory").lower()
    if provider_name == "memory" and not _is_production():
        return _memory_provider
    if provider_name != "resend":
        raise EmailDeliveryError("Provedor de e-mail não configurado.")
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = os.environ.get("EMAIL_FROM", "").strip()
    if not api_key or not sender:
        raise EmailDeliveryError("Provedor de e-mail não configurado.")
    _, sender_address = parseaddr(sender)
    try:
        validate_email(sender_address, check_deliverability=False)
    except EmailNotValidError as exc:
        raise EmailDeliveryError("EMAIL_FROM inválido.") from exc
    if "\r" in sender or "\n" in sender:
        raise EmailDeliveryError("EMAIL_FROM inválido.")
    return ResendEmailProvider(api_key, sender)


def _public_url() -> str:
    configured = os.environ.get("APP_PUBLIC_URL", "").strip().rstrip("/")
    if configured:
        try:
            parsed = urlsplit(configured)
            port = parsed.port
        except ValueError as exc:
            raise EmailDeliveryError("APP_PUBLIC_URL inválida.") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or any(character.isspace() for character in configured)
            or (port is not None and not 1 <= port <= 65535)
            or (_is_production() and parsed.scheme != "https")
        ):
            raise EmailDeliveryError("APP_PUBLIC_URL inválida.")
        return f"{parsed.scheme}://{parsed.netloc}"
    if _is_production():
        raise EmailDeliveryError("APP_PUBLIC_URL não configurada.")
    return "http://127.0.0.1:5173"


def _transactional_html(
    *,
    title: str,
    introduction: str,
    action_label: str,
    link: str,
    expiration_notice: str,
    security_notice: str | None = None,
) -> str:
    safe_title = escape(title)
    safe_introduction = escape(introduction)
    safe_action_label = escape(action_label)
    safe_link = escape(link, quote=True)
    safe_expiration_notice = escape(expiration_notice)
    security_block = ""
    if security_notice:
        security_block = (
            '<p style="margin:12px 0 0;color:#71717a;font-size:14px;line-height:1.6;">'
            f"{escape(security_notice)}</p>"
        )
    return f"""<!doctype html>
<html lang="pt-BR">
  <body style="margin:0;padding:0;background:#f7f8fa;color:#171717;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="width:100%;background:#f7f8fa;">
      <tr>
        <td align="center" style="padding:40px 16px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;width:100%;">
            <tr>
              <td style="padding:0 0 18px;color:#3730a3;font-size:24px;font-weight:700;letter-spacing:-0.4px;">Nivra</td>
            </tr>
            <tr>
              <td style="background:#ffffff;border:1px solid #e4e4e7;border-radius:16px;padding:36px 32px;">
                <h1 style="margin:0 0 16px;color:#171717;font-size:26px;line-height:1.25;">{safe_title}</h1>
                <p style="margin:0;color:#71717a;font-size:16px;line-height:1.65;">{safe_introduction}</p>
                <table role="presentation" cellspacing="0" cellpadding="0" style="margin:28px 0;">
                  <tr>
                    <td style="border-radius:9px;background:#4f46e5;">
                      <a href="{safe_link}" style="display:inline-block;padding:14px 22px;color:#ffffff;text-decoration:none;font-size:15px;font-weight:700;">{safe_action_label}</a>
                    </td>
                  </tr>
                </table>
                <p style="margin:0;color:#71717a;font-size:14px;line-height:1.6;">{safe_expiration_notice}</p>
                {security_block}
                <div style="margin-top:24px;padding-top:20px;border-top:1px solid #e4e4e7;">
                  <p style="margin:0 0 8px;color:#71717a;font-size:12px;line-height:1.5;">Se o botão não funcionar, copie e cole este link no navegador:</p>
                  <p style="margin:0;word-break:break-all;color:#3730a3;font-size:12px;line-height:1.5;"><a href="{safe_link}" style="color:#3730a3;text-decoration:underline;">{safe_link}</a></p>
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 8px 0;text-align:center;color:#71717a;font-size:12px;">Nivra · Seu dinheiro, mais claro</td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def enviar_verificacao_email(recipient: str, token: str) -> None:
    link = f"{_public_url()}/verify-email#token={quote(token, safe='')}"
    _get_provider().send(
        EmailMessage(
            recipient=recipient,
            subject="Confirme seu e-mail na Nivra",
            text=(
                "Confirme seu e-mail\n\n"
                "Falta só uma etapa para proteger sua conta e começar a usar a Nivra.\n\n"
                f"{link}\n\n"
                "Este link expira em 24 horas e pode ser usado apenas uma vez."
            ),
            html=_transactional_html(
                title="Confirme seu e-mail",
                introduction="Falta só uma etapa para proteger sua conta e começar a usar a Nivra.",
                action_label="Verificar meu e-mail",
                link=link,
                expiration_notice="Este link expira em 24 horas e pode ser usado apenas uma vez.",
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
                "Redefina sua senha\n\n"
                "Recebemos uma solicitação para alterar a senha da sua conta Nivra.\n\n"
                f"{link}\n\n"
                "Este link expira em 30 minutos e pode ser usado apenas uma vez.\n\n"
                "Se você não solicitou a alteração, pode ignorar este e-mail. "
                "Sua senha continuará a mesma."
            ),
            html=_transactional_html(
                title="Redefina sua senha",
                introduction="Recebemos uma solicitação para alterar a senha da sua conta Nivra.",
                action_label="Criar nova senha",
                link=link,
                expiration_notice="Este link expira em 30 minutos e pode ser usado apenas uma vez.",
                security_notice=(
                    "Se você não solicitou a alteração, pode ignorar este e-mail. "
                    "Sua senha continuará a mesma."
                ),
            ),
            idempotency_key=f"reset-{hash_token(token)}",
        )
    )
