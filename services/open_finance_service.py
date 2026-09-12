from services.open_finance_provider import (
    OpenFinanceProvider,
    get_open_finance_provider,
)


def criar_connect_token_service(
    usuario_id: int,
    provider: OpenFinanceProvider | None = None,
) -> dict[str, str]:
    active_provider = provider or get_open_finance_provider()
    connect_token = active_provider.create_connect_token(f"nivra-user-{usuario_id}")
    return {
        "connect_token": connect_token,
        "provider": "pluggy",
        "environment": "sandbox",
    }

