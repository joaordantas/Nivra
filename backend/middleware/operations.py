from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from services.rate_limit_service import RateLimitExceeded, consumir_limite, hash_rate_subject


logger = logging.getLogger("nivra.http")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_NUMERIC_SEGMENT = re.compile(r"/(?P<value>\d+)(?=/|$)")
_EXEMPT_PATHS = {"/api/health"}
_EXEMPT_PREFIXES = ("/api/internal/jobs/",)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().casefold() in {"1", "true", "yes", "on"}


def general_api_rate_limit_enabled() -> bool:
    configured = os.environ.get("API_RATE_LIMIT_ENABLED")
    if configured is not None:
        return _truthy(configured)
    return os.environ.get("APP_ENV", "").strip().casefold() != "test"


def _bounded_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if minimum <= value <= maximum else default


def _rate_settings(method: str) -> tuple[int, int]:
    unsafe = method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
    default_limit = 120 if unsafe else 600
    name = "API_WRITE_RATE_LIMIT" if unsafe else "API_READ_RATE_LIMIT"
    return (
        _bounded_env(name, default_limit, minimum=1, maximum=10000),
        _bounded_env("API_RATE_LIMIT_WINDOW_SECONDS", 60, minimum=1, maximum=3600),
    )


def _normalized_path(path: str) -> str:
    return _NUMERIC_SEGMENT.sub("/{id}", path)[:160]


def _client_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client is not None else "unknown"


def _request_id(request: Request) -> str:
    supplied = request.headers.get("x-request-id", "").strip()
    return supplied if _REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex


def _is_rate_limited_path(path: str) -> bool:
    return (
        path.startswith("/api/")
        and path not in _EXEMPT_PATHS
        and not path.startswith(_EXEMPT_PREFIXES)
    )


def _apply_security_headers(response: Response, request: Request, request_id: str) -> None:
    response.headers["X-Request-ID"] = request_id
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


class OperationsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        request_id = _request_id(request)
        path = _normalized_path(request.url.path)
        response: Response

        if (
            request.method.upper() != "OPTIONS"
            and general_api_rate_limit_enabled()
            and _is_rate_limited_path(request.url.path)
        ):
            limit, window = _rate_settings(request.method)
            subject = hash_rate_subject(
                _client_address(request), request.method.upper(), path
            )
            try:
                consumir_limite("api_general", subject, limit, window)
            except RateLimitExceeded as exc:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Muitas solicitações. Tente novamente em instantes."},
                    headers={"Retry-After": str(exc.retry_after)},
                )
                _apply_security_headers(response, request, request_id)
                self._log(request, response, path, request_id, started, "limited")
                return response
            except Exception:
                logger.warning(json.dumps({
                    "event": "api_rate_limit_unavailable",
                    "method": request.method.upper(),
                    "path": path,
                    "request_id": request_id,
                }, separators=(",", ":"), sort_keys=True))

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(json.dumps({
                "event": "http_request_failed",
                "method": request.method.upper(),
                "path": path,
                "request_id": request_id,
            }, separators=(",", ":"), sort_keys=True))
            raise

        _apply_security_headers(response, request, request_id)
        self._log(request, response, path, request_id, started, "completed")
        return response

    @staticmethod
    def _log(
        request: Request,
        response: Response,
        path: str,
        request_id: str,
        started: float,
        outcome: str,
    ) -> None:
        logger.info(json.dumps({
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "event": "http_request",
            "method": request.method.upper(),
            "outcome": outcome,
            "path": path,
            "request_id": request_id,
            "status": response.status_code,
        }, separators=(",", ":"), sort_keys=True))
