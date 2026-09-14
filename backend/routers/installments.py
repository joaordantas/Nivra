from fastapi import APIRouter, HTTPException, status

from backend.dependencies.auth import CurrentUser, CurrentUserCsrf
from backend.schemas.installments import (
    InstallmentPlanCreate,
    InstallmentPlanDetail,
    InstallmentPlanSummary,
    InstallmentPlanUpdate,
)
from services.parcelamento_service import (
    atualizar_parcelamento_service,
    criar_parcelamento_service,
    excluir_parcelamento_service,
    listar_parcelamentos_service,
    obter_parcelamento_service,
)


router = APIRouter(prefix="/installment-plans", tags=["installments"])


@router.post("", response_model=InstallmentPlanDetail, status_code=status.HTTP_201_CREATED)
def create_installment_plan(
    payload: InstallmentPlanCreate,
    current_user: CurrentUserCsrf,
) -> InstallmentPlanDetail:
    try:
        return InstallmentPlanDetail(
            **criar_parcelamento_service(
                current_user.id,
                payload.descricao,
                payload.valor_total,
                payload.quantidade_parcelas,
                payload.data_inicial,
                payload.tipo,
                payload.categoria_id,
                payload.conta_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[InstallmentPlanSummary])
def list_installment_plans(
    current_user: CurrentUser,
) -> list[InstallmentPlanSummary]:
    return [
        InstallmentPlanSummary(**item)
        for item in listar_parcelamentos_service(current_user.id)
    ]


@router.get("/{parcelamento_id}", response_model=InstallmentPlanDetail)
def get_installment_plan(
    parcelamento_id: int,
    current_user: CurrentUser,
) -> InstallmentPlanDetail:
    try:
        return InstallmentPlanDetail(
            **obter_parcelamento_service(parcelamento_id, current_user.id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{parcelamento_id}", response_model=InstallmentPlanDetail)
def update_installment_plan(
    parcelamento_id: int,
    payload: InstallmentPlanUpdate,
    current_user: CurrentUserCsrf,
) -> InstallmentPlanDetail:
    try:
        resultado = atualizar_parcelamento_service(
            parcelamento_id,
            current_user.id,
            payload.descricao,
            payload.categoria_id,
            payload.conta_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if resultado is None:
        raise HTTPException(status_code=404, detail="Parcelamento nao encontrado.")
    return InstallmentPlanDetail(**resultado)


@router.delete("/{parcelamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_installment_plan(
    parcelamento_id: int,
    current_user: CurrentUserCsrf,
) -> None:
    if not excluir_parcelamento_service(parcelamento_id, current_user.id):
        raise HTTPException(status_code=404, detail="Parcelamento nao encontrado.")
