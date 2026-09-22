from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class LumiProviderError(RuntimeError):
    pass


class LumiProviderNotConfiguredError(LumiProviderError):
    pass


class LumiProviderTimeoutError(LumiProviderError):
    pass


class LumiProviderAuthenticationError(LumiProviderError):
    pass


class LumiProviderRateLimitError(LumiProviderError):
    def __init__(self, message: str, retry_after: str | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LumiProviderInvalidResponseError(LumiProviderError):
    pass


@dataclass(frozen=True)
class LumiToolCall:
    call_id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class LumiUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "LumiUsage") -> "LumiUsage":
        return LumiUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass(frozen=True)
class LumiModelResponse:
    text: str = ""
    tool_calls: tuple[LumiToolCall, ...] = ()
    continuation_items: tuple[dict, ...] = ()
    usage: LumiUsage = field(default_factory=LumiUsage)


class LLMProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def create_response(
        self,
        *,
        input_items: list[dict],
        instructions: str,
        tools: list[dict],
        safety_identifier: str,
        require_tool: bool,
    ) -> LumiModelResponse: ...
