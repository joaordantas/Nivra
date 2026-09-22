from __future__ import annotations

import os
from functools import lru_cache

from services.lumi_provider import LLMProvider, LumiProviderNotConfiguredError


DEFAULT_LUMI_PROVIDER = "openai"
SUPPORTED_LUMI_PROVIDERS = {"openai", "groq"}


def float_setting(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} deve ser numérico.") from exc
    if value < minimum or value > maximum:
        raise RuntimeError(f"{name} deve ficar entre {minimum:g} e {maximum:g}.")
    return value


def int_setting(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} deve ser um número inteiro.") from exc
    if value < minimum or value > maximum:
        raise RuntimeError(f"{name} deve ficar entre {minimum} e {maximum}.")
    return value


def configured_lumi_provider_name() -> str:
    return os.environ.get("LUMI_PROVIDER", DEFAULT_LUMI_PROVIDER).strip().lower()


def configured_lumi_model_name() -> str:
    provider = configured_lumi_provider_name()
    if provider == "groq":
        return os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b").strip() or "openai/gpt-oss-20b"
    return os.environ.get("LUMI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"


def create_lumi_provider() -> LLMProvider:
    provider = configured_lumi_provider_name()
    if provider == "openai":
        from services.openai_lumi_provider import OpenAIProvider

        return OpenAIProvider.from_environment()
    if provider == "groq":
        from services.groq_lumi_provider import GroqProvider

        return GroqProvider.from_environment()
    raise LumiProviderNotConfiguredError("Provider da Lumi não configurado.")


@lru_cache(maxsize=1)
def get_lumi_provider() -> LLMProvider:
    return create_lumi_provider()


def clear_lumi_provider_cache() -> None:
    get_lumi_provider.cache_clear()


class EnvironmentLumiProvider:
    """Proxy lazy: falhas de configuração afetam apenas o endpoint da Lumi."""

    @property
    def provider_name(self) -> str:
        return configured_lumi_provider_name()

    @property
    def model_name(self) -> str:
        return configured_lumi_model_name()

    def create_response(self, **kwargs) -> object:
        return get_lumi_provider().create_response(**kwargs)
