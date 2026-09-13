"""Register or update the Nivra webhook in the configured Pluggy application."""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


PLUGGY_API_URL = "https://api.pluggy.ai"
HEADER_NAME = "X-Nivra-Webhook-Secret"


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} nao configurada.")
    return value


def request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict | None = None,
) -> object:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json", **headers},
        method=method,
    )
    try:
        with urlopen(request, timeout=15) as response:
            content = response.read().decode("utf-8")
            return json.loads(content) if content else {}
    except HTTPError as exc:
        raise RuntimeError(
            f"A Pluggy recusou o cadastro do webhook (HTTP {exc.code})."
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Nao foi possivel comunicar com a Pluggy.") from exc


def webhook_results(response: object) -> list[dict]:
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        values = response.get("results") or response.get("webhooks") or []
        if isinstance(values, list):
            return [item for item in values if isinstance(item, dict)]
    return []


def main() -> int:
    try:
        client_id = required_env("PLUGGY_CLIENT_ID")
        client_secret = required_env("PLUGGY_CLIENT_SECRET")
        webhook_secret = required_env("PLUGGY_WEBHOOK_SECRET")
        webhook_url = required_env("PLUGGY_WEBHOOK_URL")
        parsed_url = urlparse(webhook_url)
        if parsed_url.scheme != "https" or not parsed_url.hostname:
            raise RuntimeError("PLUGGY_WEBHOOK_URL deve ser uma URL HTTPS publica.")
        if len(webhook_secret) < 32:
            raise RuntimeError("PLUGGY_WEBHOOK_SECRET deve possuir ao menos 32 caracteres.")

        auth = request_json(
            "POST",
            f"{PLUGGY_API_URL}/auth",
            {},
            {"clientId": client_id, "clientSecret": client_secret},
        )
        if not isinstance(auth, dict):
            raise RuntimeError("A Pluggy retornou uma autenticacao invalida.")
        api_key = auth.get("apiKey") or auth.get("accessToken")
        if not isinstance(api_key, str) or not api_key:
            raise RuntimeError("A Pluggy nao retornou uma chave de API valida.")
        headers = {"X-API-KEY": api_key}
        registration = {
            "event": "all",
            "url": webhook_url,
            "headers": {HEADER_NAME: webhook_secret},
        }
        existing = request_json("GET", f"{PLUGGY_API_URL}/webhooks", headers)
        current = next(
            (
                webhook
                for webhook in webhook_results(existing)
                if webhook.get("url") == webhook_url and webhook.get("event") == "all"
            ),
            None,
        )
        if current is not None and current.get("id"):
            request_json(
                "PATCH",
                f"{PLUGGY_API_URL}/webhooks/{current['id']}",
                headers,
                {**registration, "enabled": True},
            )
            print("Webhook Pluggy atualizado com seguranca.")
        else:
            request_json(
                "POST",
                f"{PLUGGY_API_URL}/webhooks",
                headers,
                registration,
            )
            print("Webhook Pluggy criado com seguranca.")
        print(f"Destino: {webhook_url}")
        print("Evento: all")
        return 0
    except RuntimeError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
