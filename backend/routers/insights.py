from fastapi import APIRouter, HTTPException, Query

from backend.dependencies.auth import CurrentUser
from backend.schemas.insights import FinancialInsights
from services.insight_service import obter_insights_financeiros_service


router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=FinancialInsights)
def get_financial_insights(
    current_user: CurrentUser,
    data_inicio: str = Query(...),
    data_fim: str = Query(...),
) -> FinancialInsights:
    try:
        return FinancialInsights(
            **obter_insights_financeiros_service(
                current_user.id, data_inicio, data_fim
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
