import json
import os
import threading
import time
from collections.abc import Callable
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PLUGGY_API_URL = "https://api.pluggy.ai"
HTTP_TIMEOUT_SECONDS = 15
API_KEY_CACHE_SECONDS = 110 * 60


class OpenFinanceConfigurationError(RuntimeError):
    pass


class OpenFinanceProviderError(RuntimeError):
    pass


class OpenFinanceProvider(Protocol):
    def create_connect_token(self, client_user_id: str) -> str:
        ...


JsonRequester = Callable[[str, str, dict[str, str], dict], dict]


def _request_json(method: str, url: str, headers: dict[str, str], payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method=method,
    )
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise OpenFinanceProviderError(
                "A Pluggy recusou as credenciais configuradas no backend."
            ) from exc
        if exc.code == 429:
            raise OpenFinanceProviderError(
                "A Pluggy limitou temporariamente as solicitacoes. Tente novamente em instantes."
            ) from exc
        raise OpenFinanceProviderError(
            "A Pluggy nao conseguiu concluir a solicitacao."
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OpenFinanceProviderError(
            "A Pluggy esta temporariamente indisponivel."
        ) from exc

    if not isinstance(body, dict):
        raise OpenFinanceProviderError("A Pluggy retornou uma resposta inesperada.")
    return body


class PluggyOpenFinanceProvider:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        requester: JsonRequester = _request_json,
    ) -> None:
        if not client_id or not client_secret:
            raise OpenFinanceConfigurationError(
                "Credenciais Pluggy nao configuradas no backend."
            )
        self._client_id = client_id
        self._client_secret = client_secret
        self._requester = requester
        self._api_key: str | None = None
        self._api_key_expires_at = 0.0
        self._lock = threading.Lock()

    def _get_api_key(self) -> str:
        with self._lock:
            if self._api_key and time.monotonic() < self._api_key_expires_at:
                return self._api_key

            response = self._requester(
                "POST",
                f"{PLUGGY_API_URL}/auth",
                {},
                {"clientId": self._client_id, "clientSecret": self._client_secret},
            )
            access_token = response.get("apiKey") or response.get("accessToken")
            if not isinstance(access_token, str) or not access_token:
                raise OpenFinanceProviderError(
                    "A Pluggy nao retornou uma chave de API valida."
                )
            self._api_key = access_token
            self._api_key_expires_at = time.monotonic() + API_KEY_CACHE_SECONDS
            return access_token

    def create_connect_token(self, client_user_id: str) -> str:
        response = self._requester(
            "POST",
            f"{PLUGGY_API_URL}/connect_token",
            {"X-API-KEY": self._get_api_key()},
            {
                "options": {
                    "clientUserId": client_user_id,
                    "avoidDuplicates": True,
                }
            },
        )
        connect_token = response.get("accessToken")
        if not isinstance(connect_token, str) or not connect_token:
            raise OpenFinanceProviderError(
                "A Pluggy nao retornou um Connect Token valido."
            )
        return connect_token


_provider: PluggyOpenFinanceProvider | None = None
_provider_credentials: tuple[str, str] | None = None
_provider_lock = threading.Lock()


def get_open_finance_provider() -> PluggyOpenFinanceProvider:
    global _provider, _provider_credentials
    client_id = os.environ.get("PLUGGY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("PLUGGY_CLIENT_SECRET", "").strip()
    credentials = (client_id, client_secret)
    with _provider_lock:
        if _provider is None or _provider_credentials != credentials:
            _provider = PluggyOpenFinanceProvider(client_id, client_secret)
            _provider_credentials = credentials
        return _provider


def reset_open_finance_provider() -> None:
    global _provider, _provider_credentials
    with _provider_lock:
        _provider = None
        _provider_credentials = None

