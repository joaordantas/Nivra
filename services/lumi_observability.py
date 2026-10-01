from __future__ import annotations

import json
import logging


logger = logging.getLogger("nivra.lumi")
logger.setLevel(logging.INFO)

ALLOWED_DIMENSIONS = {
    "action_type",
    "complete",
    "input_tokens",
    "model",
    "operation",
    "output_tokens",
    "provider",
    "tool",
    "tool_calls",
    "total_tokens",
}


def log_lumi_event(
    event: str,
    *,
    outcome: str,
    duration_ms: int | None = None,
    error_code: str | None = None,
    **dimensions: str | int | bool,
) -> None:
    """Emit operational telemetry without prompts, financial data, or identity."""
    payload: dict[str, str | int | bool] = {
        "event": event,
        "outcome": outcome,
    }
    if duration_ms is not None:
        payload["duration_ms"] = max(0, duration_ms)
    if error_code:
        payload["error_code"] = error_code
    payload.update({
        key: value
        for key, value in dimensions.items()
        if key in ALLOWED_DIMENSIONS
    })
    logger.info("lumi_event %s", json.dumps(payload, separators=(",", ":"), sort_keys=True))
