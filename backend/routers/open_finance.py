from fastapi import APIRouter, HTTPException, status

from backend.dependencies.auth import CurrentUser, CurrentUserCsrf
from backend.schemas.open_finance import (
    ConnectTokenResponse,
    OpenFinanceConnectionComplete,
    OpenFinanceConnectionResponse,
    OpenFinanceAccountLink,
    OpenFinanceAccountLinkResponse,
    OpenFinanceExternalAccountResponse,
    OpenFinanceSyncResponse,
)
from services.open_finance_provider import (
    OpenFinanceConfigurationError,
    OpenFinanceItemNotFoundError,
    OpenFinanceProviderError,
)
from services.open_finance_service import (
    OpenFinanceAccountLinkConflictError,
    OpenFinanceAccountLinkError,
    OpenFinanceItemStateError,
    OpenFinanceConnectionNotFoundError,
    OpenFinanceOwnershipError,
    concluir_conexao_service,
    criar_connect_token_service,
    criar_conta_nivra_da_externa_service,
    listar_conexoes_service,
    listar_contas_externas_service,
    sincronizar_conexao_service,
    vincular_conta_externa_service,
)


router = APIRouter(tags=["open-finance"])


@router.post("/open-finance/connect-token", response_model=ConnectTokenResponse)
def create_connect_token(current_user: CurrentUserCsrf) -> ConnectTokenResponse:
    try:
        return ConnectTokenResponse(**criar_connect_token_service(current_user.id))
    except OpenFinanceConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Open Finance ainda nao foi configurado neste ambiente.",
        ) from exc
    except OpenFinanceProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/open-finance/connections/complete",
    response_model=OpenFinanceConnectionResponse,
)
def complete_connection(
    payload: OpenFinanceConnectionComplete,
    current_user: CurrentUserCsrf,
) -> OpenFinanceConnectionResponse:
    try:
        connection = concluir_conexao_service(current_user.id, str(payload.item_id))
        return OpenFinanceConnectionResponse(**connection)
    except OpenFinanceConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Open Finance ainda nao foi configurado neste ambiente.",
        ) from exc
    except OpenFinanceItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conexao bancaria nao encontrada.",
        ) from exc
    except OpenFinanceOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta conexao bancaria nao pode ser vinculada a esta conta.",
        ) from exc
    except OpenFinanceItemStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OpenFinanceProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get(
    "/open-finance/connections",
    response_model=list[OpenFinanceConnectionResponse],
)
def list_connections(current_user: CurrentUser) -> list[OpenFinanceConnectionResponse]:
    return [
        OpenFinanceConnectionResponse(**connection)
        for connection in listar_conexoes_service(current_user.id)
    ]


@router.post(
    "/open-finance/connections/{connection_id}/sync",
    response_model=OpenFinanceSyncResponse,
)
def sync_connection(
    connection_id: int,
    current_user: CurrentUserCsrf,
) -> OpenFinanceSyncResponse:
    try:
        return OpenFinanceSyncResponse(
            **sincronizar_conexao_service(current_user.id, connection_id)
        )
    except OpenFinanceConnectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except OpenFinanceConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Open Finance ainda nao foi configurado neste ambiente.",
        ) from exc
    except OpenFinanceOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta conexao bancaria nao pertence a esta conta.",
        ) from exc
    except OpenFinanceItemStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OpenFinanceProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get(
    "/open-finance/connections/{connection_id}/accounts",
    response_model=list[OpenFinanceExternalAccountResponse],
)
def list_external_accounts(
    connection_id: int,
    current_user: CurrentUser,
) -> list[OpenFinanceExternalAccountResponse]:
    try:
        return [
            OpenFinanceExternalAccountResponse(**account)
            for account in listar_contas_externas_service(current_user.id, connection_id)
        ]
    except OpenFinanceConnectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _raise_account_link_http_error(exc: Exception) -> None:
    if isinstance(exc, OpenFinanceConnectionNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, OpenFinanceAccountLinkConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, OpenFinanceAccountLinkError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    raise exc


@router.patch(
    "/open-finance/external-accounts/{external_account_id}/link",
    response_model=OpenFinanceAccountLinkResponse,
)
def link_external_account(
    external_account_id: int,
    payload: OpenFinanceAccountLink,
    current_user: CurrentUserCsrf,
) -> OpenFinanceAccountLinkResponse:
    try:
        return OpenFinanceAccountLinkResponse(
            **vincular_conta_externa_service(
                current_user.id,
                external_account_id,
                payload.conta_nivra_id,
            )
        )
    except (
        OpenFinanceConnectionNotFoundError,
        OpenFinanceAccountLinkConflictError,
        OpenFinanceAccountLinkError,
    ) as exc:
        _raise_account_link_http_error(exc)
        raise AssertionError("unreachable")


@router.post(
    "/open-finance/external-accounts/{external_account_id}/nivra-account",
    response_model=OpenFinanceAccountLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_nivra_account_from_external(
    external_account_id: int,
    current_user: CurrentUserCsrf,
) -> OpenFinanceAccountLinkResponse:
    try:
        return OpenFinanceAccountLinkResponse(
            **criar_conta_nivra_da_externa_service(current_user.id, external_account_id)
        )
    except (
        OpenFinanceConnectionNotFoundError,
        OpenFinanceAccountLinkConflictError,
        OpenFinanceAccountLinkError,
    ) as exc:
        _raise_account_link_http_error(exc)
        raise AssertionError("unreachable")
