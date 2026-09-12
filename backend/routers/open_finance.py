from fastapi import APIRouter, HTTPException, status

from backend.dependencies.auth import CurrentUserCsrf
from backend.schemas.open_finance import ConnectTokenResponse
from services.open_finance_provider import (
    OpenFinanceConfigurationError,
    OpenFinanceProviderError,
)
from services.open_finance_service import criar_connect_token_service


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

