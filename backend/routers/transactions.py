from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from backend.dependencies.auth import CurrentUser, CurrentUserCsrf
from backend.schemas.transactions import (
    TransactionCreate,
    TransactionListItem,
    MovementPage,
    ReconciliationBatchResponse,
    ReconciliationSuggestion,
    ReconciliationResponse,
    TransactionSummary,
    TransactionUpdate,
)
from services.movement_history_service import list_movement_page
from services.open_finance_reconciliation_service import (
    ReconciliationConflictError,
    ReconciliationNotFoundError,
    confirmar_conciliacao_service,
    confirmar_lote_alta_confianca_service,
    listar_sugestoes_conciliacao_service,
    rejeitar_conciliacao_service,
)
from services.transacao_service import (
    atualizar_transacao_service,
    criar_transacao_service,
    deletar_transacao_service,
    listar_transacoes_formatadas,
    obter_resumo_financeiro,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/page", response_model=MovementPage)
def list_movement_history_page(
    current_user: CurrentUser,
    q: str | None = Query(default=None, max_length=120),
    movement_type: Literal["entrada", "saida", "transferencia"] | None = None,
    account_id: int | None = Query(default=None, ge=1),
    category_id: int | None = Query(default=None, ge=1),
    origin: Literal["manual", "open_finance", "conciliada"] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
) -> MovementPage:
    try:
        return MovementPage(**list_movement_page(
            current_user.id,
            search=q,
            movement_type=movement_type,
            account_id=account_id,
            category_id=category_id,
            origin=origin,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[TransactionListItem])
def list_transactions(current_user: CurrentUser) -> list[TransactionListItem]:
    dados = listar_transacoes_formatadas(current_user.id)
    return [TransactionListItem(**item) for item in dados]


@router.post("", response_model=TransactionListItem, status_code=status.HTTP_201_CREATED)
def create_transaction(payload: TransactionCreate, current_user: CurrentUserCsrf) -> TransactionListItem:
    try:
        transacao = criar_transacao_service(
            payload.valor,
            payload.tipo,
            payload.categoria_id,
            payload.comentario,
            payload.data,
            current_user.id,
            payload.conta_id,
        )
        return TransactionListItem(**transacao)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{transacao_id}", response_model=TransactionListItem)
def update_transaction(
    transacao_id: int,
    payload: TransactionUpdate,
    current_user: CurrentUserCsrf,
) -> TransactionListItem:
    try:
        transacao = atualizar_transacao_service(
            transacao_id,
            payload.valor,
            payload.tipo,
            payload.categoria_id,
            payload.comentario,
            payload.data,
            current_user.id,
            payload.conta_id,
        )
        return TransactionListItem(**transacao)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{transacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transacao_id: int,
    current_user: CurrentUserCsrf,
) -> None:
    try:
        if not deletar_transacao_service(transacao_id, current_user.id):
            raise HTTPException(status_code=404, detail="Transacao nao encontrada.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/summary", response_model=TransactionSummary)
def get_summary(current_user: CurrentUser) -> TransactionSummary:
    return TransactionSummary(**obter_resumo_financeiro(current_user.id))


def _reconciliation_response(operation) -> ReconciliationResponse:
    try:
        return ReconciliationResponse(**operation())
    except ReconciliationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReconciliationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/reconciliation/suggestions",
    response_model=list[ReconciliationSuggestion],
)
def list_reconciliation_suggestions(
    current_user: CurrentUser,
) -> list[ReconciliationSuggestion]:
    return [
        ReconciliationSuggestion(**item)
        for item in listar_sugestoes_conciliacao_service(current_user.id)
    ]


@router.post(
    "/reconciliation/confirm-high-confidence",
    response_model=ReconciliationBatchResponse,
)
def confirm_high_confidence_reconciliations(
    current_user: CurrentUserCsrf,
) -> ReconciliationBatchResponse:
    return ReconciliationBatchResponse(
        **confirmar_lote_alta_confianca_service(current_user.id)
    )


@router.post(
    "/bank/{transacao_bancaria_id}/reconciliation/{transacao_nivra_id}/confirm",
    response_model=ReconciliationResponse,
)
def confirm_selected_bank_reconciliation(
    transacao_bancaria_id: int,
    transacao_nivra_id: int,
    current_user: CurrentUserCsrf,
) -> ReconciliationResponse:
    return _reconciliation_response(
        lambda: confirmar_conciliacao_service(
            current_user.id, transacao_bancaria_id, transacao_nivra_id
        )
    )


@router.post(
    "/bank/{transacao_bancaria_id}/reconciliation/{transacao_nivra_id}/reject",
    response_model=ReconciliationResponse,
)
def reject_selected_bank_reconciliation(
    transacao_bancaria_id: int,
    transacao_nivra_id: int,
    current_user: CurrentUserCsrf,
) -> ReconciliationResponse:
    return _reconciliation_response(
        lambda: rejeitar_conciliacao_service(
            current_user.id, transacao_bancaria_id, transacao_nivra_id
        )
    )


@router.post(
    "/bank/{transacao_bancaria_id}/reconciliation/confirm",
    response_model=ReconciliationResponse,
)
def confirm_bank_reconciliation(
    transacao_bancaria_id: int,
    current_user: CurrentUserCsrf,
) -> ReconciliationResponse:
    return _reconciliation_response(
        lambda: confirmar_conciliacao_service(
            current_user.id,
            transacao_bancaria_id,
        )
    )


@router.post(
    "/bank/{transacao_bancaria_id}/reconciliation/reject",
    response_model=ReconciliationResponse,
)
def reject_bank_reconciliation(
    transacao_bancaria_id: int,
    current_user: CurrentUserCsrf,
) -> ReconciliationResponse:
    return _reconciliation_response(
        lambda: rejeitar_conciliacao_service(
            current_user.id,
            transacao_bancaria_id,
        )
    )
