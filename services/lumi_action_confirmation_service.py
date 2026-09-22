from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

from repositories.lumi_action_confirmation_repo import (
    buscar_confirmacao,
    cancelar_confirmacao_pendente,
    confirmar_confirmacao_pendente,
    criar_confirmacao,
    expirar_confirmacao_pendente,
    finalizar_execucao,
    reivindicar_confirmacao_para_execucao,
)
from database.connection import get_connection
from services.session_service import gerar_token, hash_token
from services.transacao_service import criar_transacao_em_conexao
from services.open_finance_reconciliation_service import detectar_candidatos_conciliacao_service


logger = logging.getLogger("nivra.lumi.actions")
ActionType = Literal["create_expense", "create_income"]
ConfirmationStatus = Literal["pending", "confirmed", "cancelled", "expired", "executed"]
ALLOWED_ACTION_TYPES = frozenset({"create_expense", "create_income"})


class LumiActionConfirmationError(RuntimeError):
    pass


class LumiActionConfirmationNotFoundError(LumiActionConfirmationError):
    pass


class LumiActionConfirmationExpiredError(LumiActionConfirmationError):
    pass


class LumiActionConfirmationStateError(LumiActionConfirmationError):
    pass


@dataclass(frozen=True)
class ActionConfirmation:
    confirmation_id: str | None
    action_type: ActionType
    payload: dict[str, object]
    status: ConfirmationStatus
    expires_at: datetime
    transaction_id: int | None = None


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def action_proposals_enabled() -> bool:
    raw = os.environ.get("LUMI_ACTION_PROPOSALS_ENABLED", "false").strip().lower()
    if raw in {"1", "true", "yes"}:
        return True
    if raw in {"0", "false", "no", ""}:
        return False
    raise RuntimeError("LUMI_ACTION_PROPOSALS_ENABLED deve ser true ou false.")


def action_execution_enabled() -> bool:
    raw = os.environ.get("LUMI_ACTION_EXECUTION_ENABLED", "false").strip().lower()
    if raw in {"1", "true", "yes"}:
        return True
    if raw in {"0", "false", "no", ""}:
        return False
    raise RuntimeError("LUMI_ACTION_EXECUTION_ENABLED deve ser true ou false.")


def confirmation_ttl_seconds() -> int:
    raw = os.environ.get("LUMI_ACTION_CONFIRMATION_TTL_SECONDS", "600")
    try:
        seconds = int(raw)
    except ValueError as exc:
        raise RuntimeError("LUMI_ACTION_CONFIRMATION_TTL_SECONDS deve ser um número inteiro.") from exc
    if seconds < 60 or seconds > 900:
        raise RuntimeError("LUMI_ACTION_CONFIRMATION_TTL_SECONDS deve ficar entre 60 e 900.")
    return seconds


def action_rate_limit_settings(kind: Literal["proposal", "confirmation", "cancel"]) -> tuple[int, int]:
    prefix = "LUMI_ACTION_PROPOSAL" if kind == "proposal" else "LUMI_ACTION_CONFIRMATION"
    default_requests = "12" if kind == "proposal" else "30"
    raw_requests = os.environ.get(f"{prefix}_RATE_LIMIT_REQUESTS", default_requests)
    raw_window = os.environ.get(f"{prefix}_RATE_LIMIT_WINDOW_SECONDS", "3600")
    try:
        requests = int(raw_requests)
        window = int(raw_window)
    except ValueError as exc:
        raise RuntimeError("Os limites de ações da Lumi devem ser números inteiros.") from exc
    if requests < 1 or requests > 100 or window < 60 or window > 86_400:
        raise RuntimeError("Os limites de ações da Lumi estão fora da faixa permitida.")
    return requests, window


def _serialize_payload(payload: dict[str, object]) -> str:
    def default(value: object) -> str:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(f"Tipo de proposta não serializável: {type(value).__name__}")

    return json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, default=default)


def _deserialize_payload(payload_json: str) -> dict[str, object]:
    try:
        payload = json.loads(payload_json, parse_float=Decimal)
    except (ValueError, TypeError) as exc:
        raise LumiActionConfirmationStateError("A proposta armazenada está inválida.") from exc
    if not isinstance(payload, dict):
        raise LumiActionConfirmationStateError("A proposta armazenada está inválida.")
    return payload


def criar_confirmacao_pendente(
    usuario_id: int,
    action_type: ActionType,
    payload: dict[str, object],
    *,
    agora: datetime | None = None,
) -> ActionConfirmation:
    started = time.monotonic()
    if action_type not in ALLOWED_ACTION_TYPES:
        raise ValueError("Tipo de ação não permitido.")
    moment = agora or _agora()
    expires_at = moment + timedelta(seconds=confirmation_ttl_seconds())
    raw_token = gerar_token()
    criar_confirmacao(
        usuario_id,
        hash_token(raw_token),
        action_type,
        _serialize_payload(payload),
        expires_at,
        action_proposals_enabled() and action_execution_enabled(),
    )
    logger.info(
        "lumi_action_proposal_created action_type=%s duration_ms=%d",
        action_type,
        round((time.monotonic() - started) * 1000),
    )
    return ActionConfirmation(raw_token, action_type, payload, "pending", expires_at)


def _get_confirmation(confirmation_id: str, usuario_id: int) -> tuple[ActionConfirmation, str]:
    token_hash = hash_token(confirmation_id)
    row = buscar_confirmacao(token_hash, usuario_id)
    if row is None:
        raise LumiActionConfirmationNotFoundError("Proposta não encontrada.")
    action_type, payload_json, status, _created_at, expires_at, _confirmed_at, _cancelled_at, transaction_id, _executed_at, _eligible = row[1:]
    if str(action_type) not in ALLOWED_ACTION_TYPES:
        raise LumiActionConfirmationError("A proposta armazenada possui tipo inválido.")
    return (
        ActionConfirmation(
            None,
            str(action_type),  # type: ignore[arg-type]
            _deserialize_payload(str(payload_json)),
            str(status),  # type: ignore[arg-type]
            _parse_datetime(expires_at),
            int(transaction_id) if transaction_id is not None else None,
        ),
        token_hash,
    )


def consultar_confirmacao(confirmation_id: str, usuario_id: int, *, agora: datetime | None = None) -> ActionConfirmation:
    confirmation, token_hash = _get_confirmation(confirmation_id, usuario_id)
    moment = agora or _agora()
    if confirmation.status == "pending" and confirmation.expires_at <= moment:
        expirar_confirmacao_pendente(token_hash, usuario_id, moment)
        confirmation, _ = _get_confirmation(confirmation_id, usuario_id)
    return confirmation


def confirmar_acao_sem_execucao(
    confirmation_id: str,
    usuario_id: int,
    *,
    agora: datetime | None = None,
) -> ActionConfirmation:
    started = time.monotonic()
    moment = agora or _agora()
    confirmation = consultar_confirmacao(confirmation_id, usuario_id, agora=moment)
    if confirmation.status == "expired":
        raise LumiActionConfirmationExpiredError("Esta proposta expirou.")
    if confirmation.status != "pending":
        raise LumiActionConfirmationStateError("Esta proposta já não está pendente.")
    if not confirmar_confirmacao_pendente(hash_token(confirmation_id), usuario_id, moment):
        confirmation = consultar_confirmacao(confirmation_id, usuario_id, agora=moment)
        if confirmation.status == "expired":
            raise LumiActionConfirmationExpiredError("Esta proposta expirou.")
        raise LumiActionConfirmationStateError("Esta proposta já não está pendente.")
    logger.info(
        "lumi_action_proposal_confirmed action_type=%s execution_enabled=false duration_ms=%d",
        confirmation.action_type,
        round((time.monotonic() - started) * 1000),
    )
    return ActionConfirmation(None, confirmation.action_type, confirmation.payload, "confirmed", confirmation.expires_at)


def cancelar_acao_pendente(
    confirmation_id: str,
    usuario_id: int,
    *,
    agora: datetime | None = None,
) -> ActionConfirmation:
    started = time.monotonic()
    moment = agora or _agora()
    confirmation = consultar_confirmacao(confirmation_id, usuario_id, agora=moment)
    if confirmation.status == "cancelled":
        return confirmation
    if confirmation.status == "expired":
        raise LumiActionConfirmationExpiredError("Esta proposta expirou.")
    if confirmation.status != "pending":
        raise LumiActionConfirmationStateError("Esta proposta já não está pendente.")
    if not cancelar_confirmacao_pendente(hash_token(confirmation_id), usuario_id, moment):
        confirmation = consultar_confirmacao(confirmation_id, usuario_id, agora=moment)
        if confirmation.status == "cancelled":
            return confirmation
        if confirmation.status == "expired":
            raise LumiActionConfirmationExpiredError("Esta proposta expirou.")
        raise LumiActionConfirmationStateError("Esta proposta já não está pendente.")
    logger.info(
        "lumi_action_proposal_cancelled action_type=%s duration_ms=%d",
        confirmation.action_type,
        round((time.monotonic() - started) * 1000),
    )
    return ActionConfirmation(None, confirmation.action_type, confirmation.payload, "cancelled", confirmation.expires_at)


def _validated_execution_payload(payload: dict[str, object]) -> tuple[Decimal, str, str, int, str, int, str]:
    if set(payload) != {"amount", "description", "date", "account", "category"}:
        raise LumiActionConfirmationStateError("Os dados da proposta mudaram. Crie uma nova proposta.")
    amount_raw = payload["amount"]
    if not isinstance(amount_raw, str) or not re.fullmatch(r"\d+\.\d{2}", amount_raw):
        raise LumiActionConfirmationStateError("Valor inválido. Crie uma nova proposta.")
    try:
        amount = Decimal(amount_raw)
    except InvalidOperation as exc:
        raise LumiActionConfirmationStateError("Valor inválido. Crie uma nova proposta.") from exc
    if not amount.is_finite() or amount <= 0 or amount > Decimal("1000000000.00"):
        raise LumiActionConfirmationStateError("Valor inválido. Crie uma nova proposta.")
    description = payload["description"]
    if not isinstance(description, str) or not description.strip() or description != description.strip() or len(description) > 255:
        raise LumiActionConfirmationStateError("Descrição inválida. Crie uma nova proposta.")
    date_value = payload["date"]
    if not isinstance(date_value, str):
        raise LumiActionConfirmationStateError("Data inválida. Crie uma nova proposta.")
    try:
        if date.fromisoformat(date_value).isoformat() != date_value:
            raise ValueError()
    except ValueError as exc:
        raise LumiActionConfirmationStateError("Data inválida. Crie uma nova proposta.") from exc
    entities: list[tuple[int, str]] = []
    for key in ("account", "category"):
        entity = payload[key]
        if not isinstance(entity, dict) or set(entity) != {"id", "name"}:
            raise LumiActionConfirmationStateError("Conta ou categoria inválida. Crie uma nova proposta.")
        entity_id, name = entity["id"], entity["name"]
        if type(entity_id) is not int or entity_id < 1 or not isinstance(name, str) or not name.strip():
            raise LumiActionConfirmationStateError("Conta ou categoria inválida. Crie uma nova proposta.")
        entities.append((entity_id, name))
    return amount, description, date_value, entities[0][0], entities[0][1], entities[1][0], entities[1][1]


def executar_acao_confirmada(
    confirmation_id: str, usuario_id: int, *, agora: datetime | None = None
) -> ActionConfirmation:
    started = time.monotonic()
    if not action_proposals_enabled() or not action_execution_enabled():
        raise LumiActionConfirmationStateError("A execução de ações não está habilitada.")
    moment = agora or _agora()
    token_hash = hash_token(confirmation_id)
    conn = get_connection()
    try:
        claimed = reivindicar_confirmacao_para_execucao(conn, token_hash, usuario_id, moment)
        if claimed is None:
            conn.rollback()
            confirmation = consultar_confirmacao(confirmation_id, usuario_id, agora=moment)
            if confirmation.status == "executed":
                return confirmation
            if confirmation.status == "expired":
                raise LumiActionConfirmationExpiredError("Esta proposta expirou.")
            raise LumiActionConfirmationStateError("Esta proposta não está pendente.")
        confirmation_db_id, action_type, payload_json, expires_at = claimed
        if str(action_type) not in ALLOWED_ACTION_TYPES:
            raise LumiActionConfirmationStateError("Tipo de ação inválido.")
        payload = _deserialize_payload(str(payload_json))
        amount, description, action_date, account_id, account_name, category_id, category_name = _validated_execution_payload(payload)
        transaction_id = criar_transacao_em_conexao(
            conn, amount, "saida" if action_type == "create_expense" else "entrada",
            category_id, description, action_date, usuario_id, account_id,
            nome_conta_esperado=account_name, nome_categoria_esperado=category_name,
        )
        finalizar_execucao(conn, int(confirmation_db_id), transaction_id, moment)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning(
            "lumi_action_execution_failed outcome=rollback duration_ms=%d reason=%s",
            round((time.monotonic() - started) * 1000), type(exc).__name__,
        )
        raise
    finally:
        conn.close()
    logger.info(
        "lumi_action_executed action_type=%s outcome=success duration_ms=%d transaction_id=%d",
        action_type, round((time.monotonic() - started) * 1000), transaction_id,
    )
    try:
        detectar_candidatos_conciliacao_service(usuario_id)
    except Exception:
        logger.warning("lumi_action_reconciliation_refresh_failed")
    return ActionConfirmation(None, str(action_type), payload, "executed", _parse_datetime(expires_at), transaction_id)
