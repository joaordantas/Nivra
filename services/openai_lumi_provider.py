from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from services.lumi_provider import (
    LumiModelResponse,
    LumiProviderError,
    LumiProviderInvalidResponseError,
    LumiProviderNotConfiguredError,
    LumiProviderTimeoutError,
    LumiToolCall,
    LumiUsage,
)
from services.lumi_provider_factory import float_setting, int_setting


DEFAULT_LUMI_MODEL = "gpt-5.6-luna"
DEFAULT_LUMI_TIMEOUT_SECONDS = 20.0
DEFAULT_LUMI_MAX_OUTPUT_TOKENS = 600


class OpenAIProvider:
    provider_name = "openai"
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        client: Any | None = None,
    ) -> None:
        if not api_key.strip() and client is None:
            raise LumiProviderNotConfiguredError("Provider da Lumi não configurado.")
        self._model = model.strip() or DEFAULT_LUMI_MODEL
        self._max_output_tokens = max_output_tokens
        if client is None:
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                timeout=timeout_seconds,
                max_retries=1,
            )
        self._client = client

    @property
    def model_name(self) -> str:
        return self._model

    @classmethod
    def from_environment(cls) -> "OpenAIProvider":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise LumiProviderNotConfiguredError("Provider da Lumi não configurado.")
        return cls(
            api_key=api_key,
            model=os.environ.get("LUMI_MODEL", DEFAULT_LUMI_MODEL),
            timeout_seconds=float_setting(
                "LUMI_TIMEOUT_SECONDS", DEFAULT_LUMI_TIMEOUT_SECONDS, 1, 60
            ),
            max_output_tokens=int_setting(
                "LUMI_MAX_OUTPUT_TOKENS", DEFAULT_LUMI_MAX_OUTPUT_TOKENS, 64, 4096
            ),
        )

    def create_response(
        self,
        *,
        input_items: list[dict],
        instructions: str,
        tools: list[dict],
        safety_identifier: str,
        require_tool: bool,
    ) -> LumiModelResponse:
        try:
            response = self._client.responses.create(
                model=self._model,
                input=input_items,
                instructions=instructions,
                tools=tools,
                tool_choice="required" if require_tool else "auto",
                parallel_tool_calls=False,
                store=False,
                max_output_tokens=self._max_output_tokens,
                safety_identifier=safety_identifier,
            )
        except Exception as exc:
            try:
                from openai import APITimeoutError, OpenAIError
            except ImportError:
                APITimeoutError = ()
                OpenAIError = ()
            if APITimeoutError and isinstance(exc, APITimeoutError):
                raise LumiProviderTimeoutError("O provider excedeu o tempo limite.") from exc
            if OpenAIError and isinstance(exc, OpenAIError):
                raise LumiProviderError("O provider não conseguiu responder.") from exc
            if isinstance(exc, TimeoutError):
                raise LumiProviderTimeoutError("O provider excedeu o tempo limite.") from exc
            raise LumiProviderError("O provider não conseguiu responder.") from exc

        if getattr(response, "status", None) in {"failed", "incomplete", "cancelled"}:
            raise LumiProviderInvalidResponseError("O provider retornou uma resposta incompleta.")
        if getattr(response, "error", None) is not None:
            raise LumiProviderInvalidResponseError("O provider retornou uma resposta inválida.")

        continuation: list[dict] = []
        tool_calls: list[LumiToolCall] = []
        for item in getattr(response, "output", ()):
            if hasattr(item, "model_dump"):
                continuation.append(item.model_dump(mode="json", exclude_none=True))
            elif isinstance(item, dict):
                continuation.append(dict(item))
            if getattr(item, "type", None) == "function_call":
                tool_calls.append(LumiToolCall(
                    call_id=str(getattr(item, "call_id", "")),
                    name=str(getattr(item, "name", "")),
                    arguments=str(getattr(item, "arguments", "")),
                ))

        usage = getattr(response, "usage", None)
        return LumiModelResponse(
            text=str(getattr(response, "output_text", "") or "").strip(),
            tool_calls=tuple(tool_calls),
            continuation_items=tuple(continuation),
            usage=LumiUsage(
                input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
                total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
            ),
        )


@lru_cache(maxsize=1)
def get_openai_provider() -> OpenAIProvider:
    return OpenAIProvider.from_environment()


class EnvironmentOpenAIProvider:
    """Proxy lazy para que configuração ausente afete apenas o endpoint Lumi."""

    @property
    def model_name(self) -> str:
        return os.environ.get("LUMI_MODEL", DEFAULT_LUMI_MODEL).strip() or DEFAULT_LUMI_MODEL

    def create_response(
        self,
        *,
        input_items: list[dict],
        instructions: str,
        tools: list[dict],
        safety_identifier: str,
        require_tool: bool,
    ) -> LumiModelResponse:
        return get_openai_provider().create_response(
            input_items=input_items,
            instructions=instructions,
            tools=tools,
            safety_identifier=safety_identifier,
            require_tool=require_tool,
        )
