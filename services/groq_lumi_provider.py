from __future__ import annotations

import os
from typing import Any

from services.lumi_provider import (
    LumiModelResponse,
    LumiProviderAuthenticationError,
    LumiProviderError,
    LumiProviderInvalidResponseError,
    LumiProviderNotConfiguredError,
    LumiProviderRateLimitError,
    LumiProviderTimeoutError,
    LumiToolCall,
    LumiUsage,
)
from services.lumi_provider_factory import float_setting, int_setting


DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_LUMI_TIMEOUT_SECONDS = 20.0
DEFAULT_LUMI_MAX_OUTPUT_TOKENS = 600


def _groq_tools(tools: list[dict]) -> list[dict]:
    """Converte a allowlist da Responses API para local function calling da Groq."""
    return [
        {
            "type": "function",
            "function": {
                "name": str(tool["name"]),
                "description": str(tool["description"]),
                "parameters": dict(tool["parameters"]),
            },
        }
        for tool in tools
    ]


def _groq_messages(input_items: list[dict], instructions: str) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": instructions}]
    pending_calls: list[dict] = []

    def flush_calls() -> None:
        nonlocal pending_calls
        if pending_calls:
            messages.append({"role": "assistant", "content": None, "tool_calls": pending_calls})
            pending_calls = []

    for item in input_items:
        item_type = item.get("type")
        if item_type == "function_call":
            pending_calls.append({
                "id": str(item["call_id"]),
                "type": "function",
                "function": {
                    "name": str(item["name"]),
                    "arguments": str(item["arguments"]),
                },
            })
            continue
        if item_type == "function_call_output":
            flush_calls()
            messages.append({
                "role": "tool",
                "tool_call_id": str(item["call_id"]),
                "content": str(item["output"]),
            })
            continue
        flush_calls()
        role = item.get("role")
        if role in {"user", "assistant"}:
            messages.append({"role": role, "content": str(item["content"])})
    flush_calls()
    return messages


class GroqProvider:
    provider_name = "groq"

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
        self._model = model.strip() or DEFAULT_GROQ_MODEL
        self._max_output_tokens = max_output_tokens
        if client is None:
            from groq import Groq

            client = Groq(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self._client = client

    @property
    def model_name(self) -> str:
        return self._model

    @classmethod
    def from_environment(cls) -> "GroqProvider":
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            raise LumiProviderNotConfiguredError("Provider da Lumi não configurado.")
        timeout_default = float_setting(
            "LUMI_TIMEOUT_SECONDS", DEFAULT_LUMI_TIMEOUT_SECONDS, 1, 60
        )
        return cls(
            api_key=api_key,
            model=os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL),
            timeout_seconds=float_setting("GROQ_TIMEOUT_SECONDS", timeout_default, 1, 60),
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
        del safety_identifier  # A Chat Completions API da Groq não aceita esse campo.
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=_groq_messages(input_items, instructions),
                tools=_groq_tools(tools),
                tool_choice="required" if require_tool else "auto",
                parallel_tool_calls=False,
                max_completion_tokens=self._max_output_tokens,
                temperature=0,
            )
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            headers = getattr(getattr(exc, "response", None), "headers", {}) or {}
            if status_code == 429:
                raise LumiProviderRateLimitError(
                    "O provider atingiu o limite de solicitações.", headers.get("retry-after")
                ) from exc
            if status_code in {401, 403}:
                raise LumiProviderAuthenticationError("O provider não foi autenticado.") from exc
            try:
                from groq import (
                    APIConnectionError,
                    APIStatusError,
                    APITimeoutError,
                    AuthenticationError,
                    RateLimitError,
                )
            except ImportError:
                APIConnectionError = APIStatusError = APITimeoutError = AuthenticationError = RateLimitError = ()
            if APITimeoutError and isinstance(exc, APITimeoutError):
                raise LumiProviderTimeoutError("O provider excedeu o tempo limite.") from exc
            if RateLimitError and isinstance(exc, RateLimitError):
                raise LumiProviderRateLimitError("O provider atingiu o limite de solicitações.") from exc
            if AuthenticationError and isinstance(exc, AuthenticationError):
                raise LumiProviderAuthenticationError("O provider não foi autenticado.") from exc
            if (APIConnectionError and isinstance(exc, APIConnectionError)) or (
                APIStatusError and isinstance(exc, APIStatusError)
            ):
                raise LumiProviderError("O provider não conseguiu responder.") from exc
            if isinstance(exc, TimeoutError):
                raise LumiProviderTimeoutError("O provider excedeu o tempo limite.") from exc
            raise LumiProviderError("O provider não conseguiu responder.") from exc

        choices = getattr(response, "choices", ())
        if not choices:
            raise LumiProviderInvalidResponseError("O provider retornou uma resposta inválida.")
        choice = choices[0]
        if getattr(choice, "finish_reason", None) in {"length", "content_filter"}:
            raise LumiProviderInvalidResponseError("O provider retornou uma resposta incompleta.")
        message = getattr(choice, "message", None)
        if message is None:
            raise LumiProviderInvalidResponseError("O provider retornou uma resposta inválida.")

        tool_calls: list[LumiToolCall] = []
        continuation_calls: list[dict] = []
        for call in getattr(message, "tool_calls", ()) or ():
            function = getattr(call, "function", None)
            call_id = str(getattr(call, "id", ""))
            name = str(getattr(function, "name", ""))
            arguments = str(getattr(function, "arguments", ""))
            tool_calls.append(LumiToolCall(call_id, name, arguments))
            continuation_calls.append({
                "type": "function_call",
                "call_id": call_id,
                "name": name,
                "arguments": arguments,
            })

        continuation: tuple[dict, ...] = tuple(continuation_calls)
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
        return LumiModelResponse(
            text=str(getattr(message, "content", "") or "").strip(),
            tool_calls=tuple(tool_calls),
            continuation_items=continuation,
            usage=LumiUsage(input_tokens, output_tokens, total_tokens),
        )
