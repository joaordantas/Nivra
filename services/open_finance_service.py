import os

from sqlalchemy.exc import IntegrityError

from repositories.open_finance_connection_repo import (
    criar_ou_obter_conexao_bancaria,
    listar_conexoes_bancarias,
)
from repositories.open_finance_link_repo import (
    buscar_conta_externa_para_vinculo,
    buscar_conta_nivra_disponivel,
    criar_conta_nivra_e_vincular,
    vincular_conta_externa,
)
from repositories.open_finance_sync_repo import (
    buscar_conexao_para_sincronizacao,
    finalizar_evento_com_falha,
    iniciar_evento_sincronizacao,
    listar_contas_externas,
    persistir_snapshot_sincronizacao,
)
from services.open_finance_provider import (
    OpenFinanceConfigurationError,
    OpenFinanceProvider,
    OpenFinanceProviderError,
    get_open_finance_provider,
)
from utils.categorias_padrao import map_provider_category


PROVIDER_NAME = "pluggy"
VALID_ITEM_EXECUTION_STATUSES = {"SUCCESS", "PARTIAL_SUCCESS"}


class OpenFinanceOwnershipError(RuntimeError):
    pass


class OpenFinanceItemStateError(RuntimeError):
    pass


class OpenFinanceConnectionNotFoundError(RuntimeError):
    pass


class OpenFinanceAccountLinkError(RuntimeError):
    pass


class OpenFinanceAccountLinkConflictError(RuntimeError):
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
        "ultimo_evento_status": str(row[13]) if row[13] is not None else None,
        "ultimo_erro": str(row[14]) if row[14] is not None else None,
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


def _registrar_falha_segura(
    evento_id: int,
    usuario_id: int,
    codigo: str,
    mensagem: str,
) -> None:
    try:
        finalizar_evento_com_falha(evento_id, usuario_id, codigo, mensagem)
    except Exception:
        # A falha original deve continuar sendo a resposta da sincronização.
        pass


def sincronizar_conexao_service(
    usuario_id: int,
    conexao_id: int,
    provider: OpenFinanceProvider | None = None,
) -> dict:
    connection = buscar_conexao_para_sincronizacao(conexao_id, usuario_id)
    if connection is None:
        raise OpenFinanceConnectionNotFoundError("Conexao bancaria nao encontrada.")
    if str(connection[2]) != PROVIDER_NAME:
        raise OpenFinanceConfigurationError("Provider Open Finance nao suportado.")

    active_provider = provider or get_open_finance_provider()
    evento_id = iniciar_evento_sincronizacao(conexao_id, usuario_id)
    try:
        item = active_provider.get_item(str(connection[3]))
        if item.client_user_id != client_user_reference(usuario_id):
            raise OpenFinanceOwnershipError(
                "A conexao informada nao pertence ao usuario autenticado."
            )
        if item.execution_status.upper() not in VALID_ITEM_EXECUTION_STATUSES:
            raise OpenFinanceItemStateError(
                "A conexao bancaria ainda nao esta pronta para sincronizacao."
            )

        accounts = active_provider.list_accounts(item.id)
        snapshot: list[dict] = []
        for account in accounts:
            transactions = active_provider.list_transactions(account.id, account.type)
            snapshot.append(
                {
                    "external_account_id": account.id,
                    "nome": account.name,
                    "tipo": account.type,
                    "subtipo": account.subtype,
                    "moeda": account.currency_code,
                    "saldo": account.balance,
                    "transacoes": [
                        {
                            "external_transaction_id": transaction.id,
                            "descricao": transaction.description,
                            "valor": transaction.amount,
                            "data": transaction.date,
                            "direcao": transaction.direction,
                            "metadata_provider": {
                                "status": transaction.status,
                                "category_id": transaction.category_id,
                                "category_name": transaction.category_name,
                                "nivra_category_key": map_provider_category(
                                    PROVIDER_NAME,
                                    transaction.category_id,
                                    transaction.category_name,
                                ),
                            },
                        }
                        for transaction in transactions
                    ],
                }
            )

        result = persistir_snapshot_sincronizacao(
            conexao_id=conexao_id,
            usuario_id=usuario_id,
            evento_id=evento_id,
            instituicao_nome=item.institution_name,
            status_conexao="active",
            contas=snapshot,
        )
        return {"conexao_id": conexao_id, **result}
    except OpenFinanceProviderError as exc:
        _registrar_falha_segura(evento_id, usuario_id, "provider_error", str(exc))
        raise
    except OpenFinanceOwnershipError as exc:
        _registrar_falha_segura(
            evento_id,
            usuario_id,
            "ownership_error",
            "A conexao nao pertence ao usuario autenticado.",
        )
        raise
    except OpenFinanceItemStateError as exc:
        _registrar_falha_segura(evento_id, usuario_id, "item_not_ready", str(exc))
        raise
    except Exception:
        _registrar_falha_segura(
            evento_id,
            usuario_id,
            "persistence_error",
            "A sincronizacao nao pôde ser persistida.",
        )
        raise


def listar_contas_externas_service(usuario_id: int, conexao_id: int) -> list[dict]:
    connection = buscar_conexao_para_sincronizacao(conexao_id, usuario_id)
    if connection is None:
        raise OpenFinanceConnectionNotFoundError("Conexao bancaria nao encontrada.")
    return [
        {
            "id": int(row[0]),
            "nome": str(row[1]),
            "tipo": str(row[2]),
            "subtipo": str(row[3]) if row[3] is not None else None,
            "moeda": str(row[4]),
            "saldo": float(row[5]) if row[5] is not None else None,
            "quantidade_transacoes": int(row[6]),
            "conta_nivra_id": int(row[7]) if row[7] is not None else None,
            "conta_nivra_nome": str(row[8]) if row[8] is not None else None,
            "pode_vincular_conta_nivra": str(row[2]).upper() == "BANK" and str(row[4]).upper() == "BRL",
        }
        for row in listar_contas_externas(conexao_id, usuario_id)
    ]


def _obter_conta_externa_vinculavel(usuario_id: int, conta_externa_id: int) -> tuple:
    external_account = buscar_conta_externa_para_vinculo(conta_externa_id, usuario_id)
    if external_account is None:
        raise OpenFinanceConnectionNotFoundError("Conta externa nao encontrada.")
    if str(external_account[2]).upper() != "BANK":
        raise OpenFinanceAccountLinkError(
            "Somente contas bancarias podem ser vinculadas ao nucleo financeiro nesta etapa."
        )
    if str(external_account[4]).upper() != "BRL":
        raise OpenFinanceAccountLinkError(
            "Somente contas em reais podem ser vinculadas nesta etapa."
        )
    return external_account


def _tipo_conta_nivra(subtipo: str | None) -> str:
    normalized = (subtipo or "").upper()
    if normalized == "CHECKING_ACCOUNT":
        return "corrente"
    if normalized == "SAVINGS_ACCOUNT":
        return "poupanca"
    return "digital"


def vincular_conta_externa_service(
    usuario_id: int,
    conta_externa_id: int,
    conta_nivra_id: int,
) -> dict:
    external_account = _obter_conta_externa_vinculavel(usuario_id, conta_externa_id)
    nivra_account = buscar_conta_nivra_disponivel(conta_nivra_id, usuario_id)
    if nivra_account is None or not bool(nivra_account[2]):
        raise OpenFinanceConnectionNotFoundError("Conta Nivra ativa nao encontrada.")
    linked_external_id = nivra_account[3]
    if linked_external_id is not None and int(linked_external_id) != conta_externa_id:
        raise OpenFinanceAccountLinkConflictError(
            "Esta conta Nivra ja esta vinculada a outra conta bancaria."
        )
    try:
        if not vincular_conta_externa(conta_externa_id, conta_nivra_id, usuario_id):
            raise OpenFinanceConnectionNotFoundError(
                "Conta externa ou conta Nivra nao encontrada."
            )
    except IntegrityError as exc:
        raise OpenFinanceAccountLinkConflictError(
            "Esta conta Nivra ja esta vinculada a outra conta bancaria."
        ) from exc
    return {
        "conta_externa_id": int(external_account[0]),
        "conta_nivra_id": conta_nivra_id,
        "conta_nivra_nome": str(nivra_account[1]),
    }


def criar_conta_nivra_da_externa_service(
    usuario_id: int,
    conta_externa_id: int,
) -> dict:
    external_account = _obter_conta_externa_vinculavel(usuario_id, conta_externa_id)
    if external_account[6] is not None:
        raise OpenFinanceAccountLinkConflictError(
            "Esta conta bancaria ja esta vinculada a Nivra."
        )
    account_name = f"{external_account[7]} - {external_account[1]}"[:80].strip()
    try:
        conta_nivra_id = criar_conta_nivra_e_vincular(
            conta_externa_id=conta_externa_id,
            usuario_id=usuario_id,
            nome=account_name,
            tipo=_tipo_conta_nivra(
                str(external_account[3]) if external_account[3] is not None else None
            ),
        )
    except IntegrityError as exc:
        raise OpenFinanceAccountLinkConflictError(
            "Ja existe uma conta Nivra com esse nome ou vinculo bancario."
        ) from exc
    except ValueError as exc:
        raise OpenFinanceAccountLinkConflictError(str(exc)) from exc
    return {
        "conta_externa_id": conta_externa_id,
        "conta_nivra_id": conta_nivra_id,
        "conta_nivra_nome": account_name,
    }
