import time

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status

from backend.dependencies.auth import CurrentUser, CurrentUserCsrf
from backend.schemas.lumi import (
    LumiActionConfirmation,
    LumiActionDecisionRequest,
    LumiActionTokenRequest,
    LumiActionConfirmationResponse,
    LumiActionProposalResponse,
    LumiMessageRequest,
    LumiMessageResponse,
    LumiResponse,
    LumiConversationCreateRequest,
    LumiMemoryCreateRequest,
)
from database.connection import get_connection
from services.lumi_persistence_service import (
    LumiPersistenceError,
    append_message,
    clear_history,
    clear_memories,
    context_memories,
    create_conversation,
    create_memory,
    delete_conversation,
    delete_memory,
    get_conversation,
    list_conversations,
    list_memories,
    load_context,
)
from services.lumi_action_confirmation_service import (
    LumiActionConfirmationExpiredError,
    LumiActionConfirmationNotFoundError,
    LumiActionConfirmationStateError,
    action_execution_enabled,
    action_proposals_enabled,
    action_rate_limit_settings,
    cancelar_acao_pendente,
    confirmar_acao_sem_execucao,
    consultar_confirmacao,
    executar_acao_confirmada,
)
from services.lumi_action_proposal_service import (
    criar_proposta_da_mensagem,
    reconhecer_intencao_acao,
)
from services.lumi_orchestrator import (
    LumiOrchestrationError,
    LumiOrchestrator,
    LumiToolExecutionError,
    LumiToolLimitError,
    criar_safety_identifier,
    lumi_rate_limit_settings,
)
from services.lumi_provider import (
    LumiProviderAuthenticationError,
    LumiProviderError,
    LumiProviderInvalidResponseError,
    LumiProviderNotConfiguredError,
    LumiProviderRateLimitError,
    LumiProviderTimeoutError,
)
from services.lumi_provider_factory import EnvironmentLumiProvider
from services.lumi_observability import log_lumi_event
from services.lumi_rollout_service import lumi_access_allowed
from services.rate_limit_service import RateLimitExceeded, consumir_limite, hash_rate_subject


router = APIRouter(prefix="/lumi", tags=["lumi"])


def _require_lumi_access(current_user: CurrentUser) -> None:
    if not lumi_access_allowed(current_user.id):
        log_lumi_event("access_denied", outcome="refused")
        raise HTTPException(status_code=503, detail="A Lumi está em desenvolvimento.")


@router.get("/capabilities")
def get_lumi_capabilities(current_user: CurrentUser) -> dict[str, bool]:
    return {"public_enabled": lumi_access_allowed(current_user.id)}


@router.get("/conversations")
def get_lumi_conversations(current_user: CurrentUser) -> list[dict]:
    _require_lumi_access(current_user)
    return list_conversations(current_user.id)


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def post_lumi_conversation(payload: LumiConversationCreateRequest, current_user: CurrentUserCsrf) -> dict:
    _require_lumi_access(current_user)
    return create_conversation(current_user.id, payload.title)


@router.get("/conversations/{conversation_id}")
def get_lumi_conversation(conversation_id: str, current_user: CurrentUser) -> dict:
    _require_lumi_access(current_user)
    try:
        return get_conversation(current_user.id, conversation_id)
    except LumiPersistenceError as exc:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.") from exc


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_lumi_conversation(conversation_id: str, current_user: CurrentUserCsrf) -> Response:
    _require_lumi_access(current_user)
    try:
        delete_conversation(current_user.id, conversation_id)
    except LumiPersistenceError as exc:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/conversations", status_code=status.HTTP_204_NO_CONTENT)
def remove_lumi_history(current_user: CurrentUserCsrf) -> Response:
    _require_lumi_access(current_user)
    clear_history(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/memories")
def get_lumi_memories(current_user: CurrentUser) -> list[dict]:
    _require_lumi_access(current_user)
    return list_memories(current_user.id)


@router.post("/memories", status_code=status.HTTP_201_CREATED)
def post_lumi_memory(payload: LumiMemoryCreateRequest, current_user: CurrentUserCsrf) -> dict:
    _require_lumi_access(current_user)
    try:
        return create_memory(current_user.id, payload.category, payload.content)
    except LumiPersistenceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_lumi_memory(memory_id: str, current_user: CurrentUserCsrf) -> Response:
    _require_lumi_access(current_user)
    delete_memory(current_user.id, memory_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/memories", status_code=status.HTTP_204_NO_CONTENT)
def remove_lumi_memories(current_user: CurrentUserCsrf) -> Response:
    _require_lumi_access(current_user)
    clear_memories(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def get_lumi_orchestrator() -> LumiOrchestrator:
    return LumiOrchestrator(EnvironmentLumiProvider())


def _proposal_response(proposal) -> LumiActionProposalResponse:
    confirmation = proposal.confirmation
    execution_enabled = action_proposals_enabled() and action_execution_enabled()
    missing_questions = {
        "valor": "Qual é o valor?",
        "descrição": "Qual descrição você quer usar?",
        "conta": "Em qual conta devo registrar?",
        "categoria": "Qual categoria devo usar?",
        "data": "Em qual data devo registrar?",
        "alteração": "O que você quer alterar nessa transação?",
        "transação inequívoca": "Qual transação você quer alterar?",
    }
    message = (
            ("Revise os dados. Ao confirmar, a movimentação será criada."
             if execution_enabled else
             "Revise a proposta abaixo. A confirmação é explícita e a execução financeira continua desativada nesta versão.")
            if confirmation is not None
            else missing_questions.get(
                proposal.missing_fields[0] if proposal.missing_fields else "",
                proposal.warnings[0] if proposal.warnings else "Preciso de mais uma informação para preparar a proposta.",
            )
        ).replace("a movimentação", "a alteração" if proposal.action_type == "update_transaction" else "a movimentação")
    return LumiActionProposalResponse(
        message=message,
        action_type=proposal.action_type,
        summary=proposal.summary,
        payload=proposal.payload,
        missing_fields=list(proposal.missing_fields),
        warnings=list(proposal.warnings),
        confirmation=(
            LumiActionConfirmation(
                confirmation_id=confirmation.confirmation_id,
                status="pending",
                expires_at=confirmation.expires_at,
            )
            if confirmation is not None and confirmation.confirmation_id is not None
            else None
        ),
        execution_enabled=execution_enabled,
    )


def _consume_action_limit(kind: str, current_user: CurrentUserCsrf) -> None:
    requests, window = action_rate_limit_settings(kind)  # type: ignore[arg-type]
    consumir_limite(
        f"lumi_action_{kind}",
        hash_rate_subject("lumi-action", kind, str(current_user.id)),
        requests,
        window,
    )


@router.post("/message", response_model=LumiResponse)
def send_lumi_message(
    payload: LumiMessageRequest,
    current_user: CurrentUserCsrf,
    orchestrator: LumiOrchestrator = Depends(get_lumi_orchestrator),
) -> LumiMessageResponse:
    _require_lumi_access(current_user)
    started = time.monotonic()
    persistent_context: list[dict[str, str]] = []
    persistent_memories: tuple[str, ...] = ()
    if payload.conversation_id:
        conn = None
        try:
            conn = get_connection()
            conversation_id, persistent_context = load_context(conn, current_user.id, payload.conversation_id)
            append_message(conn, conversation_id, "user", payload.message)
            persistent_memories = tuple(context_memories(conn, current_user.id))
            conn.commit()
        except LumiPersistenceError as exc:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.") from exc
        except Exception as exc:
            log_lumi_event(
                "persistence",
                outcome="error",
                error_code=type(exc).__name__,
                operation="load_context",
            )
            raise HTTPException(
                status_code=503,
                detail="Não foi possível carregar esta conversa agora. Tente novamente.",
            ) from exc
        finally:
            if conn is not None:
                conn.close()
    requests, window = lumi_rate_limit_settings()
    try:
        consumir_limite(
            "lumi_message",
            hash_rate_subject("lumi", str(current_user.id)),
            requests,
            window,
        )
        if action_proposals_enabled():
            if reconhecer_intencao_acao(payload.message) is not None:
                _consume_action_limit("proposal", current_user)
                proposal = criar_proposta_da_mensagem(payload.message, current_user.id)
                if proposal is None:
                    raise RuntimeError("A intenção de ação não pôde ser preparada.")
                response = _proposal_response(proposal)
                log_lumi_event(
                    "action_proposed",
                    outcome="success",
                    duration_ms=round((time.monotonic() - started) * 1000),
                    action_type=proposal.action_type,
                    complete=proposal.confirmation is not None,
                )
                if payload.conversation_id:
                    _persist_assistant_message(current_user.id, payload.conversation_id, response.message)
                return response
        result = orchestrator.respond(
            payload.message,
            usuario_id=current_user.id,
            safety_identifier=criar_safety_identifier(current_user.token_hash),
            history=tuple(persistent_context or [item.model_dump() for item in payload.history]),
            memories=persistent_memories,
        )
        response = LumiMessageResponse(
            message=result.message,
            tools_used=list(result.tools_used),
        )
        if payload.conversation_id:
            _persist_assistant_message(current_user.id, payload.conversation_id, response.message)
        return response
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="Limite de mensagens da Lumi atingido. Tente novamente mais tarde.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except LumiProviderNotConfiguredError as exc:
        raise HTTPException(
            status_code=503,
            detail="A Lumi ainda não está configurada neste ambiente.",
        ) from exc
    except LumiProviderTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="A Lumi demorou mais que o esperado. Tente novamente.",
        ) from exc
    except LumiProviderRateLimitError as exc:
        headers = {"Retry-After": exc.retry_after} if exc.retry_after else None
        raise HTTPException(
            status_code=429,
            detail="A Lumi está temporariamente com muitas solicitações. Tente novamente em instantes.",
            headers=headers,
        ) from exc
    except LumiProviderAuthenticationError as exc:
        raise HTTPException(
            status_code=503,
            detail="A Lumi ainda não está configurada neste ambiente.",
        ) from exc
    except (LumiProviderInvalidResponseError, LumiToolLimitError) as exc:
        raise HTTPException(
            status_code=502,
            detail="A Lumi não conseguiu concluir esta resposta com segurança.",
        ) from exc
    except (LumiToolExecutionError, LumiProviderError, LumiOrchestrationError) as exc:
        raise HTTPException(
            status_code=503,
            detail="A Lumi está temporariamente indisponível.",
        ) from exc
    except Exception as exc:
        log_lumi_event(
            "request_failed",
            outcome="error",
            duration_ms=round((time.monotonic() - started) * 1000),
            error_code=type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="A Lumi está temporariamente indisponível. Tente novamente.",
        ) from exc


def _persist_assistant_message(usuario_id: int, public_id: str, content: str) -> None:
    conn = get_connection()
    try:
        conversation_id, _ = load_context(conn, usuario_id, public_id)
        append_message(conn, conversation_id, "assistant", content)
        conn.commit()
    finally:
        conn.close()


def _confirmation_response(confirmation, *, operation: str) -> LumiActionConfirmationResponse:
    if operation == "confirm":
        message = (
            ("Despesa criada com sucesso." if confirmation.action_type == "create_expense"
             else "Receita criada com sucesso." if confirmation.action_type == "create_income"
             else "Transação atualizada com sucesso.")
            if confirmation.status == "executed" else
            "A proposta foi confirmada. A execução financeira ainda não está habilitada nesta versão."
        )
    else:
        message = "A proposta foi cancelada e não poderá ser confirmada depois."
    return LumiActionConfirmationResponse(
        action_type=confirmation.action_type,
        status=confirmation.status,
        expires_at=confirmation.expires_at,
        message=message,
        execution_enabled=confirmation.status == "executed",
        transaction_id=confirmation.transaction_id,
    )


def _confirmation_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LumiActionConfirmationNotFoundError):
        return HTTPException(status_code=404, detail="Proposta não encontrada.")
    if isinstance(exc, LumiActionConfirmationExpiredError):
        return HTTPException(status_code=410, detail="Esta proposta expirou. Crie uma nova proposta.")
    if isinstance(exc, LumiActionConfirmationStateError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=409, detail="Esta proposta já não está disponível para esta operação.")


@router.post("/actions/{confirmation_id}/confirm", response_model=LumiActionConfirmationResponse)
def confirm_lumi_action(
    confirmation_id: str, current_user: CurrentUserCsrf,
    _body: LumiActionDecisionRequest | None = Body(default=None),
) -> LumiActionConfirmationResponse:
    _require_lumi_access(current_user)
    if action_execution_enabled():
        raise HTTPException(status_code=409, detail="Atualize a página para confirmar esta proposta com segurança.")
    return _confirm_action(confirmation_id, current_user)


@router.post("/actions/confirm", response_model=LumiActionConfirmationResponse)
def confirm_lumi_action_by_body(
    payload: LumiActionTokenRequest, current_user: CurrentUserCsrf,
) -> LumiActionConfirmationResponse:
    _require_lumi_access(current_user)
    return _confirm_action(payload.confirmation_id, current_user)


def _confirm_action(confirmation_id: str, current_user: CurrentUserCsrf) -> LumiActionConfirmationResponse:
    started = time.monotonic()
    try:
        if not action_proposals_enabled():
            raise LumiActionConfirmationStateError("As propostas estão desativadas.")
        if action_execution_enabled() and action_proposals_enabled():
            existing = consultar_confirmacao(confirmation_id, current_user.id)
            if existing.status == "executed":
                return _confirmation_response(existing, operation="confirm")
        _consume_action_limit("confirmation", current_user)
        response = _confirmation_response(
            (executar_acao_confirmada(confirmation_id, current_user.id)
             if action_execution_enabled() and action_proposals_enabled()
             else confirmar_acao_sem_execucao(confirmation_id, current_user.id)),
            operation="confirm",
        )
        log_lumi_event(
            "action_executed" if response.status == "executed" else "action_confirmed",
            outcome="success",
            duration_ms=round((time.monotonic() - started) * 1000),
            action_type=response.action_type,
        )
        return response
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="Limite temporário de confirmações atingido. Tente novamente mais tarde.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except (LumiActionConfirmationNotFoundError, LumiActionConfirmationExpiredError, LumiActionConfirmationStateError) as exc:
        log_lumi_event(
            "action_confirmation",
            outcome="refused",
            duration_ms=round((time.monotonic() - started) * 1000),
            error_code=type(exc).__name__,
        )
        raise _confirmation_error(exc) from exc
    except ValueError as exc:
        log_lumi_event(
            "action_confirmation",
            outcome="refused",
            duration_ms=round((time.monotonic() - started) * 1000),
            error_code="ProposalSnapshotChanged",
        )
        raise HTTPException(status_code=409, detail="Os dados da proposta mudaram. Crie uma nova proposta.") from exc
    except Exception as exc:
        log_lumi_event(
            "action_execution",
            outcome="error",
            duration_ms=round((time.monotonic() - started) * 1000),
            error_code=type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Não foi possível concluir a ação agora. Consulte o estado da proposta antes de tentar novamente.",
        ) from exc


@router.post("/actions/{confirmation_id}/cancel", response_model=LumiActionConfirmationResponse)
def cancel_lumi_action(
    confirmation_id: str, current_user: CurrentUserCsrf,
    _body: LumiActionDecisionRequest | None = Body(default=None),
) -> LumiActionConfirmationResponse:
    _require_lumi_access(current_user)
    return _cancel_action(confirmation_id, current_user)


@router.post("/actions/cancel", response_model=LumiActionConfirmationResponse)
def cancel_lumi_action_by_body(
    payload: LumiActionTokenRequest, current_user: CurrentUserCsrf,
) -> LumiActionConfirmationResponse:
    _require_lumi_access(current_user)
    return _cancel_action(payload.confirmation_id, current_user)


def _cancel_action(confirmation_id: str, current_user: CurrentUserCsrf) -> LumiActionConfirmationResponse:
    started = time.monotonic()
    try:
        _consume_action_limit("cancel", current_user)
        response = _confirmation_response(
            cancelar_acao_pendente(confirmation_id, current_user.id),
            operation="cancel",
        )
        log_lumi_event(
            "action_cancelled",
            outcome="success",
            duration_ms=round((time.monotonic() - started) * 1000),
            action_type=response.action_type,
        )
        return response
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="Limite temporário de cancelamentos atingido. Tente novamente mais tarde.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except (LumiActionConfirmationNotFoundError, LumiActionConfirmationExpiredError, LumiActionConfirmationStateError) as exc:
        log_lumi_event(
            "action_cancelled",
            outcome="refused",
            duration_ms=round((time.monotonic() - started) * 1000),
            error_code=type(exc).__name__,
        )
        raise _confirmation_error(exc) from exc
    except Exception as exc:
        log_lumi_event(
            "action_cancelled",
            outcome="error",
            duration_ms=round((time.monotonic() - started) * 1000),
            error_code=type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Não foi possível cancelar a proposta agora. Consulte o estado antes de tentar novamente.",
        ) from exc
