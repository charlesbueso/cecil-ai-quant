"""Unified LLM client factory.

Creates LangChain ``ChatOpenAI`` instances configured for any supported
open-source model provider.  The interface is identical regardless of
backend, so agent code never deals with provider specifics.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from langchain_openai import ChatOpenAI

from cecil.config import get_settings
from cecil.models.providers import PROVIDERS, ProviderConfig, get_model_for_role

logger = logging.getLogger(__name__)


class ModelClient:
    """Thin factory that builds and caches ``ChatOpenAI`` instances."""

    def __init__(self) -> None:
        self._settings = get_settings()

    # ── public API ───────────────────────────────────────────────────

    def get_chat_model(
        self,
        role: str,
        *,
        provider_name: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        bind_tools: list[Any] | None = None,
        **kwargs: Any,
    ) -> ChatOpenAI:
        """Return a configured ``ChatOpenAI`` for *role*.

        Parameters
        ----------
        role:
            Agent role key (e.g. ``"quant_researcher"``).
        provider_name:
            Override the provider set in config.
        model:
            Override the model id.
        temperature:
            Sampling temperature.
        max_tokens:
            Max completion tokens.
        bind_tools:
            If given, call ``llm.bind_tools(...)`` before returning.
        """
        prov_name = provider_name or self._provider_for_role(role)
        provider = PROVIDERS.get(prov_name)
        if provider is None:
            raise ValueError(
                f"Unknown provider '{prov_name}'. "
                f"Available: {list(PROVIDERS.keys())}"
            )

        api_key = self._resolve_key(provider)
        model_id = model or get_model_for_role(role, prov_name)

        llm = ChatOpenAI(
            model=model_id,
            openai_api_key=api_key,
            openai_api_base=provider.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            default_headers=provider.extra_headers or None,
            **kwargs,
        )

        logger.info(
            "LLM ready  role=%s  provider=%s  model=%s",
            role,
            prov_name,
            model_id,
        )

        if bind_tools:
            llm = llm.bind_tools(bind_tools)  # type: ignore[assignment]

        return llm

    # ── internals ────────────────────────────────────────────────────

    def _provider_for_role(self, role: str) -> str:
        """Read the configured provider name for a given agent role."""
        attr = f"{role}_provider"
        return getattr(self._settings, attr, "groq")

    def _resolve_key(self, provider: ProviderConfig) -> str:
        key: str = getattr(self._settings, provider.env_key_name, "")
        if not key:
            raise EnvironmentError(
                f"API key not set for {provider.name}. "
                f"Set the {provider.env_key_name.upper()} environment variable."
            )
        return key


@lru_cache
def get_model_client() -> ModelClient:
    return ModelClient()
