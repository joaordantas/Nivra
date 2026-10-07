from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Header, HTTPException, Request, status

from backend.schemas.jobs import PeriodicSummaryTriggerResponse
from services.periodic_summary_job_service import (
    current_civil_date,
    periodic_summary_job_runner,
    periodic_summary_jobs_enabled,
)


router = APIRouter(tags=["internal-jobs"])


def _authenticate_scheduler(authorization: str | None) -> None:
    configured = os.environ.get("CRON_SECRET", "").strip()
    if len(configured) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trigger periódico não configurado.",
        )
    provided = authorization or ""
    expected = f"Bearer {configured}"
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Trigger periódico não autenticado.",
        )


@router.get(
    "/internal/jobs/periodic-summaries",
    response_model=PeriodicSummaryTriggerResponse,
    include_in_schema=False,
)
def trigger_periodic_summaries(
    request: Request,
    authorization: str | None = Header(default=None),
) -> PeriodicSummaryTriggerResponse:
    _authenticate_scheduler(authorization)
    raw_content_length = request.headers.get("content-length", "0") or "0"
    try:
        has_payload = int(raw_content_length) > 0
    except ValueError:
        has_payload = True
    if request.query_params or has_payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O trigger não aceita parâmetros ou payload.",
        )
    if not periodic_summary_jobs_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Jobs periódicos desativados.",
        )
    results = periodic_summary_job_runner.run_all(reference=current_civil_date())
    public_results = [result.public_dict() for result in results]
    statuses = {result.status for result in results}
    aggregate = (
        "failed"
        if statuses == {"failed"}
        else "partial_success"
        if "failed" in statuses or "partial_success" in statuses
        else "success"
    )
    if aggregate == "failed":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Execução periódica falhou; consulte o tracking operacional.",
        )
    return PeriodicSummaryTriggerResponse(status=aggregate, results=public_results)
