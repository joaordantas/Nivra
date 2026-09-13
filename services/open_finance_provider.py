import json
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


PLUGGY_API_URL = "https://api.pluggy.ai"
HTTP_TIMEOUT_SECONDS = 15
API_KEY_CACHE_SECONDS = 110 * 60
MAX_TRANSACTION_PAGES = 1000
BRAZIL_TIMEZONE = ZoneInfo("America/Sao_Paulo")


class OpenFinanceConfigurationError(RuntimeError):
    pass


class OpenFinanceProviderError(RuntimeError):
    pass


class OpenFinanceItemNotFoundError(OpenFinanceProviderError):
    pass


@dataclass(frozen=True)
class OpenFinanceItem:
    id: str
    client_user_id: str
    connector_id: int | None
    institution_name: str
    status: str
    execution_status: str


@dataclass(frozen=True)
class OpenFinanceAccount:
    id: str
    name: str
    type: str
    subtype: str | None
    currency_code: str
    balance: Decimal | None


@dataclass(frozen=True)
class OpenFinanceTransaction:
    id: str
    description: str
    amount: Decimal
    date: date
    direction: str
    status: str
    category_id: str | None
    category_name: str | None


class OpenFinanceProvider(Protocol):
    def create_connect_token(self, client_user_id: str) -> str:
        ...

    def get_item(self, item_id: str) -> OpenFinanceItem:
        ...

    def list_accounts(self, item_id: str) -> list[OpenFinanceAccount]:
        ...

    def list_transactions(
        self,
        account_id: str,
        account_type: str,
    ) -> list[OpenFinanceTransaction]:
        ...


JsonRequester = Callable[[str, str, dict[str, str], dict | None], dict]


def _request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict | None,
) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json", **headers},
        method=method,
    )
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise OpenFinanceItemNotFoundError(
                "A conexao informada nao foi encontrada na Pluggy."
            ) from exc
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


def _required_text(value: object, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OpenFinanceProviderError(message)
    return value.strip()


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _decimal(value: object, *, required: bool) -> Decimal | None:
    if value is None and not required:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise OpenFinanceProviderError("A Pluggy retornou um valor financeiro invalido.") from exc
    if not parsed.is_finite():
        raise OpenFinanceProviderError("A Pluggy retornou um valor financeiro invalido.")
    return parsed


def _financial_date(value: object) -> date:
    text_value = _required_text(value, "A Pluggy retornou uma data de transacao invalida.")
    try:
        if len(text_value) == 10:
            return date.fromisoformat(text_value)
        parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(BRAZIL_TIMEZONE)
        return parsed.date()
    except ValueError as exc:
        raise OpenFinanceProviderError("A Pluggy retornou uma data de transacao invalida.") from exc


def _results(response: dict, resource: str) -> list[dict]:
    results = response.get("results")
    if not isinstance(results, list) or any(not isinstance(item, dict) for item in results):
        raise OpenFinanceProviderError(f"A Pluggy retornou uma lista de {resource} invalida.")
    return results


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

    def get_item(self, item_id: str) -> OpenFinanceItem:
        response = self._requester(
            "GET",
            f"{PLUGGY_API_URL}/items/{item_id}",
            {"X-API-KEY": self._get_api_key()},
            None,
        )
        connector = response.get("connector")
        connector_id = connector.get("id") if isinstance(connector, dict) else None
        institution_name = connector.get("name") if isinstance(connector, dict) else None
        client_user_id = response.get("clientUserId")
        status = response.get("status")
        execution_status = response.get("executionStatus")
        returned_id = response.get("id")

        if (
            not isinstance(returned_id, str)
            or returned_id != item_id
            or not isinstance(client_user_id, str)
            or not isinstance(institution_name, str)
            or not institution_name.strip()
            or not isinstance(status, str)
            or not isinstance(execution_status, str)
        ):
            raise OpenFinanceProviderError(
                "A Pluggy retornou dados incompletos para a conexao."
            )
        if connector_id is not None and not isinstance(connector_id, int):
            raise OpenFinanceProviderError(
                "A Pluggy retornou um identificador de instituicao invalido."
            )

        return OpenFinanceItem(
            id=returned_id,
            client_user_id=client_user_id,
            connector_id=connector_id,
            institution_name=institution_name.strip(),
            status=status,
            execution_status=execution_status,
        )

    def list_accounts(self, item_id: str) -> list[OpenFinanceAccount]:
        response = self._requester(
            "GET",
            f"{PLUGGY_API_URL}/accounts?itemId={quote(item_id, safe='')}",
            {"X-API-KEY": self._get_api_key()},
            None,
        )
        accounts: list[OpenFinanceAccount] = []
        for raw in _results(response, "contas"):
            account_id = _required_text(
                raw.get("id"), "A Pluggy retornou uma conta sem identificador."
            )
            account_type = _required_text(
                raw.get("type"), "A Pluggy retornou uma conta sem tipo."
            ).upper()
            accounts.append(
                OpenFinanceAccount(
                    id=account_id,
                    name=_required_text(
                        raw.get("name") or raw.get("marketingName"),
                        "A Pluggy retornou uma conta sem nome.",
                    ),
                    type=account_type,
                    subtype=_optional_text(raw.get("subtype")),
                    currency_code=(_optional_text(raw.get("currencyCode")) or "BRL").upper(),
                    balance=_decimal(raw.get("balance"), required=False),
                )
            )
        return accounts

    def list_transactions(
        self,
        account_id: str,
        account_type: str,
    ) -> list[OpenFinanceTransaction]:
        transactions: list[OpenFinanceTransaction] = []
        next_cursor: str | None = None
        seen_cursors: set[str] = set()

        for _ in range(MAX_TRANSACTION_PAGES):
            url = f"{PLUGGY_API_URL}/v2/transactions?accountId={quote(account_id, safe='')}"
            if next_cursor is not None:
                url += f"&after={quote(next_cursor, safe='')}"
            response = self._requester(
                "GET",
                url,
                {"X-API-KEY": self._get_api_key()},
                None,
            )
            for raw in _results(response, "transacoes"):
                amount = _decimal(raw.get("amount"), required=True)
                assert amount is not None
                raw_type = (_optional_text(raw.get("type")) or "").upper()
                if raw_type in {"DEBIT", "CREDIT"}:
                    direction = "saida" if raw_type == "DEBIT" else "entrada"
                elif account_type.upper() == "CREDIT":
                    direction = "saida" if amount >= 0 else "entrada"
                else:
                    direction = "entrada" if amount >= 0 else "saida"
                transactions.append(
                    OpenFinanceTransaction(
                        id=_required_text(
                            raw.get("id"),
                            "A Pluggy retornou uma transacao sem identificador.",
                        ),
                        description=_required_text(
                            raw.get("description"),
                            "A Pluggy retornou uma transacao sem descricao.",
                        ),
                        amount=abs(amount),
                        date=_financial_date(raw.get("date")),
                        direction=direction,
                        status=(_optional_text(raw.get("status")) or "POSTED").upper(),
                        category_id=_optional_text(raw.get("categoryId")),
                        category_name=_optional_text(raw.get("category")),
                    )
                )

            next_value = response.get("next")
            if not next_value:
                return transactions
            next_text = _required_text(
                next_value, "A Pluggy retornou um cursor de transacoes invalido."
            )
            query = parse_qs(urlparse(next_text).query)
            cursor_values = query.get("after")
            if not cursor_values or not cursor_values[0]:
                raise OpenFinanceProviderError(
                    "A Pluggy retornou um cursor de transacoes invalido."
                )
            next_cursor = cursor_values[0]
            if next_cursor in seen_cursors:
                raise OpenFinanceProviderError(
                    "A Pluggy repetiu um cursor durante a sincronizacao."
                )
            seen_cursors.add(next_cursor)

        raise OpenFinanceProviderError(
            "A sincronizacao excedeu o limite seguro de paginas da Pluggy."
        )


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
