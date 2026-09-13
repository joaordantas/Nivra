import os

from repositories.open_finance_connection_repo import (
    criar_ou_obter_conexao_bancaria,
    listar_conexoes_bancarias,
)
from services.open_finance_provider import (
    OpenFinanceConfigurationError,
    OpenFinanceProvider,
    get_open_finance_provider,
)


PROVIDER_NAME = "pluggy"
VALID_ITEM_EXECUTION_STATUSES = {"SUCCESS", "PARTIAL_SUCCESS"}


class OpenFinanceOwnershipError(RuntimeError):
    pass


class OpenFinanceItemStateError(RuntimeError):
    pass


def client_user_reference(usuario_id: int) -> str:
    return f"nivra-user-{usuario_id}"


def open_finance_environment() -> str:
    environment = os.environ.get("OPEN_FINANCE_ENVIRONMENT", "sandbox").strip().lower()
    if environment != "sandbox":
        raise OpenFinanceConfigurationError(
            "Somente o ambiente Sandbox esta habilitado nesta versao."
        )
    return environment


def _formatar_conexao(row: tuple) -> dict:
    return {
        "id": int(row[0]),
        "provider": str(row[2]),
        "instituicao_nome": str(row[6]),
        "status": str(row[7]),
        "ambiente": str(row[8]),
        "criada_em": str(row[9]),
        "atualizada_em": str(row[10]),
        "ultima_sincronizacao_em": str(row[11]) if row[11] is not None else None,
        "desconectada_em": str(row[12]) if row[12] is not None else None,
    }


def criar_connect_token_service(
    usuario_id: int,
    provider: OpenFinanceProvider | None = None,
) -> dict[str, str]:
    active_provider = provider or get_open_finance_provider()
    connect_token = active_provider.create_connect_token(client_user_reference(usuario_id))
    return {
        "connect_token": connect_token,
        "provider": PROVIDER_NAME,
        "environment": open_finance_environment(),
    }


def concluir_conexao_service(
    usuario_id: int,
    item_id: str,
    provider: OpenFinanceProvider | None = None,
) -> dict:
    active_provider = provider or get_open_finance_provider()
    item = active_provider.get_item(item_id)
    expected_reference = client_user_reference(usuario_id)
    if item.client_user_id != expected_reference:
        raise OpenFinanceOwnershipError(
            "A conexao informada nao pertence ao usuario autenticado."
        )
    if item.execution_status.upper() not in VALID_ITEM_EXECUTION_STATUSES:
        raise OpenFinanceItemStateError(
            "A conexao bancaria ainda nao foi concluida na Pluggy."
        )

    row = criar_ou_obter_conexao_bancaria(
        usuario_id=usuario_id,
        provider=PROVIDER_NAME,
        external_item_id=item.id,
        client_user_ref=expected_reference,
        external_connector_id=item.connector_id,
        instituicao_nome=item.institution_name,
        status="active",
        ambiente=open_finance_environment(),
    )
    if int(row[1]) != usuario_id:
        raise OpenFinanceOwnershipError(
            "A conexao informada ja esta vinculada a outro usuario."
        )
    return _formatar_conexao(row)


def listar_conexoes_service(usuario_id: int) -> list[dict]:
    return [
        _formatar_conexao(row)
        for row in listar_conexoes_bancarias(usuario_id)
    ]
