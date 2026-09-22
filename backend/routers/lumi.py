from fastapi import APIRouter, Body, Depends, HTTPException

from backend.dependencies.auth import CurrentUserCsrf
from backend.schemas.lumi import (
    LumiActionConfirmation,
    LumiActionDecisionRequest,
    LumiActionTokenRequest,
    LumiActionConfirmationResponse,
    LumiActionProposalResponse,
    LumiMessageRequest,
    LumiMessageResponse,
    LumiResponse,
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
from services.rate_limit_service import RateLimitExceeded, consumir_limite, hash_rate_subject


router = APIRouter(prefix="/lumi", tags=["lumi"])


def get_lumi_orchestrator() -> LumiOrchestrator:
    return LumiOrchestrator(EnvironmentLumiProvider())


def _proposal_response(proposal) -> LumiActionProposalResponse:
    confirmation = proposal.confirmation
    execution_enabled = action_proposals_enabled() and action_execution_enabled()
    return LumiActionProposalResponse(
        message=(
            ("Revise os dados. Ao confirmar, a movimentação será criada."
             if execution_enabled else
             "Revise a proposta abaixo. A confirmação é explícita e a execução financeira continua desativada nesta versão.")
            if confirmation is not None
            else "Para preparar uma proposta segura, informe os campos faltantes."
        ),
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
                return _proposal_response(proposal)
        result = orchestrator.respond(
            payload.message,
            usuario_id=current_user.id,
            safety_identifier=criar_safety_identifier(current_user.token_hash),
            history=tuple(item.model_dump() for item in payload.history),
        )
        return LumiMessageResponse(
            message=result.message,
            tools_used=list(result.tools_used),
        )
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


def _confirmation_response(confirmation, *, operation: str) -> LumiActionConfirmationResponse:
    if operation == "confirm":
        message = (
            ("Despesa criada com sucesso." if confirmation.action_type == "create_expense"
             else "Receita criada com sucesso.")
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
    if action_execution_enabled():
        raise HTTPException(status_code=409, detail="Atualize a página para confirmar esta proposta com segurança.")
    return _confirm_action(confirmation_id, current_user)


@router.post("/actions/confirm", response_model=LumiActionConfirmationResponse)
def confirm_lumi_action_by_body(
    payload: LumiActionTokenRequest, current_user: CurrentUserCsrf,
) -> LumiActionConfirmationResponse:
    return _confirm_action(payload.confirmation_id, current_user)


def _confirm_action(confirmation_id: str, current_user: CurrentUserCsrf) -> LumiActionConfirmationResponse:
    try:
        if not action_proposals_enabled():
            raise LumiActionConfirmationStateError("As propostas estão desativadas.")
        if action_execution_enabled() and action_proposals_enabled():
            existing = consultar_confirmacao(confirmation_id, current_user.id)
            if existing.status == "executed":
                return _confirmation_response(existing, operation="confirm")
        _consume_action_limit("confirmation", current_user)
        return _confirmation_response(
            (executar_acao_confirmada(confirmation_id, current_user.id)
             if action_execution_enabled() and action_proposals_enabled()
             else confirmar_acao_sem_execucao(confirmation_id, current_user.id)),
            operation="confirm",
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="Limite temporário de confirmações atingido. Tente novamente mais tarde.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except (LumiActionConfirmationNotFoundError, LumiActionConfirmationExpiredError, LumiActionConfirmationStateError) as exc:
        raise _confirmation_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Os dados da proposta mudaram. Crie uma nova proposta.") from exc


@router.post("/actions/{confirmation_id}/cancel", response_model=LumiActionConfirmationResponse)
def cancel_lumi_action(
    confirmation_id: str, current_user: CurrentUserCsrf,
    _body: LumiActionDecisionRequest | None = Body(default=None),
) -> LumiActionConfirmationResponse:
    return _cancel_action(confirmation_id, current_user)


@router.post("/actions/cancel", response_model=LumiActionConfirmationResponse)
def cancel_lumi_action_by_body(
    payload: LumiActionTokenRequest, current_user: CurrentUserCsrf,
) -> LumiActionConfirmationResponse:
    return _cancel_action(payload.confirmation_id, current_user)


def _cancel_action(confirmation_id: str, current_user: CurrentUserCsrf) -> LumiActionConfirmationResponse:
    try:
        _consume_action_limit("cancel", current_user)
        return _confirmation_response(
            cancelar_acao_pendente(confirmation_id, current_user.id),
            operation="cancel",
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="Limite temporário de cancelamentos atingido. Tente novamente mais tarde.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except (LumiActionConfirmationNotFoundError, LumiActionConfirmationExpiredError, LumiActionConfirmationStateError) as exc:
        raise _confirmation_error(exc) from exc
