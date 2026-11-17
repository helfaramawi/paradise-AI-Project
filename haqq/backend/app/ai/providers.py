"""LLM provider abstraction. Products code against :class:`LLMProvider`; the provider is chosen by
configuration (HAQQ_LLM_PROVIDER). Credentials come only from the environment / secrets manager."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from ..config import get_settings


class ProviderNotConfigured(RuntimeError):
    pass


class ProviderRefusal(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


@dataclass
class LLMResult:
    parsed: BaseModel
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model: str
    attempts: int = 1


class LLMProvider(Protocol):
    name: str
    model: str

    def structured(self, system: str, user: str, schema: type[BaseModel], max_tokens: int) -> LLMResult: ...


class DisabledProvider:
    name = "none"
    model = "-"

    def structured(self, system: str, user: str, schema: type[BaseModel], max_tokens: int) -> LLMResult:
        raise ProviderNotConfigured("No LLM provider is configured (HAQQ_LLM_PROVIDER=none).")


class AnthropicProvider:
    """Claude via the official Anthropic SDK with structured (Pydantic-validated) outputs."""

    name = "anthropic"

    def __init__(self) -> None:
        import anthropic

        s = get_settings()
        if not s.anthropic_api_key:
            raise ProviderNotConfigured("HAQQ_ANTHROPIC_API_KEY is not set.")
        self.model = s.llm_model
        self.effort = s.llm_effort
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=s.anthropic_api_key, timeout=s.llm_timeout_seconds,
                                          max_retries=s.llm_max_retries)

    def structured(self, system: str, user: str, schema: type[BaseModel], max_tokens: int) -> LLMResult:
        a = self._anthropic
        t0 = time.monotonic()
        try:
            resp = self.client.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                output_config={"effort": self.effort},
                # Server-side refusal fallback (routes by refusal category).
                extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
                extra_body={"fallbacks": "default"},
            )
        except a.RateLimitError as exc:
            raise ProviderError(f"Rate limited by provider: {exc}") from exc
        except a.APIStatusError as exc:
            raise ProviderError(f"Provider error {exc.status_code}: {exc.message}") from exc
        except a.APIConnectionError as exc:
            raise ProviderError(f"Provider unreachable: {exc}") from exc
        latency = int((time.monotonic() - t0) * 1000)
        if resp.stop_reason == "refusal":
            raise ProviderRefusal("The model declined this request.")
        if resp.parsed_output is None:
            raise ProviderError(f"No structured output (stop_reason={resp.stop_reason}).")
        return LLMResult(resp.parsed_output, resp.usage.input_tokens, resp.usage.output_tokens, latency, resp.model)


_override: LLMProvider | None = None


def set_provider_override(p: LLMProvider | None) -> None:
    """Testing hook: install a provider double."""
    global _override
    _override = p


def get_provider() -> LLMProvider:
    if _override is not None:
        return _override
    name = get_settings().llm_provider
    if name == "anthropic":
        return AnthropicProvider()
    return DisabledProvider()
