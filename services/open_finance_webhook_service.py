import hashlib
import hmac
import json
import logging
import os

from backend.schemas.open_finance import PluggyWebhookPayload
from repositories.open_finance_webhook_repo import (
    buscar_conexao_por_item,
    buscar_conta_externa_por_identificador,
    excluir_transacoes_webhook,
    finalizar_evento_webhook,
    marcar_conexao_externa_excluida,
    persistir_transacoes_webhook,
    reivindicar_evento_webhook,
    registrar_erro_conexao_webhook,
    registrar_evento_webhook,
)
from services.open_finance_provider import (
    OpenFinanceConfigurationError,
    OpenFinanceProvider,
    OpenFinanceProviderError,
    get_open_finance_provider,
)
from services.open_finance_reconciliation_service import (
    detectar_candidatos_conciliacao_service,
)
from services.open_finance_service import sincronizar_conexao_service
from utils.categorias_padrao import map_provider_category


PROVIDER_NAME = "pluggy"
SUPPORTED_EVENTS = {
    "item/updated",
    "item/error",
    "item/deleted",
    "transactions/created",
    "transactions/updated",
    "transactions/deleted",
}
WEBHOOK_HEADER_NAME = "X-Nivra-Webhook-Secret"
logger = logging.getLogger("nivra.open_finance.webhook")


class WebhookAuthenticationError(RuntimeError):
    pass


class WebhookConfigurationError(RuntimeError):
    pass


class WebhookPayloadConflictError(RuntimeError):
    pass


class WebhookPermanentError(RuntimeError):
    pass


class WebhookTemporaryError(RuntimeError):
    pass


def validar_segredo_webhook(received_secret: str | None) -> None:
    configured = os.environ.get("PLUGGY_WEBHOOK_SECRET", "").strip()
    if len(configured) < 32:
        raise WebhookConfigurationError(
            "PLUGGY_WEBHOOK_SECRET nao foi configurado com seguranca."
        )
    candidate = received_secret or ""
    if not hmac.compare_digest(candidate.encode(), configured.encode()):
        raise WebhookAuthenticationError("Webhook nao autenticado.")


def _payload_hash(payload: PluggyWebhookPayload) -> str:
    canonical = json.dumps(
        payload.model_dump(by_alias=True, exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _log(event_id: str, event_type: str, status: str, **details: object) -> None:
    logger.info(
        json.dumps(
            {
                "log_type": "open_finance_webhook",
                "provider": PROVIDER_NAME,
                "provider_event_id": event_id,
                "event_type": event_type,
                "status": status,
                **details,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _transaction_dict(transaction) -> dict:
    return {
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


def _validar_item_do_usuario(
    provider: OpenFinanceProvider,
    item_id: str,
    client_user_ref: str,
) -> None:
    item = provider.get_item(item_id)
    if item.client_user_id != client_user_ref:
        raise WebhookPermanentError(
            "O Item informado nao pertence ao usuario registrado na Nivra."
        )


def _processar_transacoes(
    payload: PluggyWebhookPayload,
    provider: OpenFinanceProvider,
    conexao_id: int,
    usuario_id: int,
    client_user_ref: str,
) -> int:
    assert payload.item_id is not None
    assert payload.account_id is not None
    _validar_item_do_usuario(provider, payload.item_id, client_user_ref)
    account = buscar_conta_externa_por_identificador(conexao_id, payload.account_id)
    if account is None:
        sincronizar_conexao_service(usuario_id, conexao_id, provider)
        account = buscar_conta_externa_por_identificador(conexao_id, payload.account_id)
    if account is None:
        raise WebhookPermanentError(
            "A conta externa do evento nao pertence ao Item informado."
        )
    conta_externa_id = int(account[0])

    if payload.event == "transactions/deleted":
        return excluir_transacoes_webhook(
            conexao_id,
            conta_externa_id,
            payload.transaction_ids,
        )

    if payload.event != "transactions/deleted" and len(payload.transaction_ids) > 500:
        raise WebhookPermanentError(
            "O evento excede o limite de 500 transacoes por consulta."
        )
    transactions = provider.list_transactions(
        payload.account_id,
        str(account[1]),
        transaction_ids=payload.transaction_ids or None,
        created_at_from=(
            payload.transactions_created_at_from
            if not payload.transaction_ids
            else None
        ),
    )
    result = persistir_transacoes_webhook(
        conexao_id,
        conta_externa_id,
        [_transaction_dict(transaction) for transaction in transactions],
    )
    detectar_candidatos_conciliacao_service(usuario_id, conexao_id)
    return result["criadas"] + result["atualizadas"]


def _processar_evento(
    payload: PluggyWebhookPayload,
    provider: OpenFinanceProvider,
    connection: tuple,
) -> int:
    conexao_id = int(connection[0])
    usuario_id = int(connection[1])
    client_user_ref = str(connection[2])
    if payload.event == "item/updated":
        result = sincronizar_conexao_service(usuario_id, conexao_id, provider)
        return int(result["transacoes_processadas"])
    if payload.event == "item/error":
        error = payload.error or {}
        code = str(error.get("code") or "provider_item_error")
        message = str(error.get("message") or "A conexao bancaria apresentou um erro.")
        registrar_erro_conexao_webhook(conexao_id, code, message)
        return 0
    if payload.event == "item/deleted":
        marcar_conexao_externa_excluida(conexao_id)
        return 0
    return _processar_transacoes(
        payload,
        provider,
        conexao_id,
        usuario_id,
        client_user_ref,
    )


def processar_webhook_pluggy_service(
    payload: PluggyWebhookPayload,
    received_secret: str | None,
    provider: OpenFinanceProvider | None = None,
) -> dict:
    validar_segredo_webhook(received_secret)
    connection = (
        buscar_conexao_por_item(PROVIDER_NAME, payload.item_id)
        if payload.item_id
        else None
    )
    event_hash = _payload_hash(payload)
    row = registrar_evento_webhook(
        provider=PROVIDER_NAME,
        provider_event_id=payload.event_id,
        tipo=payload.event,
        external_item_id=payload.item_id,
        conexao_id=int(connection[0]) if connection else None,
        payload_hash=event_hash,
    )
    event_db_id, existing_status, existing_hash, _, _, inserted = row
    if str(existing_hash) != event_hash:
        _log(payload.event_id, payload.event, "payload_conflict")
        raise WebhookPayloadConflictError(
            "O eventId ja foi recebido com outro conteudo."
        )
    if not inserted and str(existing_status) in {"sucesso", "ignorado"}:
        _log(payload.event_id, payload.event, "duplicate")
        return {
            "event_id": payload.event_id,
            "status": "duplicate",
            "processed_count": 0,
        }
    claimed = reivindicar_evento_webhook(
        int(event_db_id),
        int(connection[0]) if connection else None,
    )
    if not claimed:
        _log(payload.event_id, payload.event, "already_processing")
        raise WebhookTemporaryError(
            "O evento ja esta sendo processado e deve ser tentado novamente."
        )

    if payload.event not in SUPPORTED_EVENTS or connection is None:
        finalizar_evento_webhook(int(event_db_id), "ignorado")
        _log(
            payload.event_id,
            payload.event,
            "ignored",
            reason="unsupported_event" if payload.event not in SUPPORTED_EVENTS else "unknown_item",
        )
        return {
            "event_id": payload.event_id,
            "status": "ignored",
            "processed_count": 0,
        }

    if connection[4] is not None and payload.event != "item/deleted":
        finalizar_evento_webhook(int(event_db_id), "ignorado")
        _log(payload.event_id, payload.event, "ignored", reason="disconnected_item")
        return {
            "event_id": payload.event_id,
            "status": "ignored",
            "processed_count": 0,
        }

    try:
        active_provider = provider or get_open_finance_provider()
        processed = _processar_evento(payload, active_provider, connection)
        finalizar_evento_webhook(
            int(event_db_id),
            "sucesso",
            quantidade_processada=processed,
        )
        _log(payload.event_id, payload.event, "processed", processed_count=processed)
        return {
            "event_id": payload.event_id,
            "status": "processed",
            "processed_count": processed,
        }
    except WebhookPermanentError as exc:
        finalizar_evento_webhook(
            int(event_db_id),
            "erro",
            codigo_erro="permanent_payload_error",
            mensagem_erro=str(exc),
        )
        _log(payload.event_id, payload.event, "permanent_error")
        raise
    except (OpenFinanceConfigurationError, OpenFinanceProviderError) as exc:
        finalizar_evento_webhook(
            int(event_db_id),
            "erro",
            codigo_erro="provider_unavailable",
            mensagem_erro=str(exc),
        )
        _log(payload.event_id, payload.event, "temporary_error")
        raise WebhookTemporaryError(
            "O evento foi registrado, mas o provider esta temporariamente indisponivel."
        ) from exc
    except Exception as exc:
        finalizar_evento_webhook(
            int(event_db_id),
            "erro",
            codigo_erro="processing_error",
            mensagem_erro="Falha temporaria ao processar o evento.",
        )
        _log(payload.event_id, payload.event, "temporary_error")
        raise WebhookTemporaryError(
            "O evento foi registrado e podera ser processado novamente."
        ) from exc
