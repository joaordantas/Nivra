from fastapi import APIRouter, HTTPException, status

from backend.dependencies.auth import CurrentUser, CurrentUserCsrf
from backend.schemas.transactions import (
    TransactionCreate,
    TransactionListItem,
    ReconciliationResponse,
    TransactionSummary,
    TransactionUpdate,
)
from services.open_finance_reconciliation_service import (
    ReconciliationConflictError,
    ReconciliationNotFoundError,
    confirmar_conciliacao_service,
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
    if not deletar_transacao_service(transacao_id, current_user.id):
        raise HTTPException(status_code=404, detail="Transacao nao encontrada.")


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
