from pydantic import BaseModel


class PeriodicSummaryJobResultResponse(BaseModel):
    job_type: str
    period_start: str
    period_end: str
    status: str
    reason: str
    attempt: int | None
    processed: int
    success: int
    suppressed: int
    skipped: int
    failed: int
    retries: int
    duration_ms: int


class PeriodicSummaryTriggerResponse(BaseModel):
    status: str
    results: list[PeriodicSummaryJobResultResponse]
