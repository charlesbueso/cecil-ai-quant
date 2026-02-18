"""Provider definitions for open-source LLM API endpoints.

Every provider uses the OpenAI-compatible chat completions format so we
can swap backends with a single config change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """Connection details for one LLM provider."""

    name: str
    base_url: str
    env_key_name: str  # name of the env-var holding the API key
    default_model: str
    supports_tool_use: bool = True
    extra_headers: dict[str, str] = field(default_factory=dict)


# ── Supported providers ──────────────────────────────────────────────

PROVIDERS: dict[str, ProviderConfig] = {
    "together": ProviderConfig(
        name="Together AI",
        base_url="https://api.together.xyz/v1",
        env_key_name="together_api_key",
        default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
    ),
    "groq": ProviderConfig(
        name="Groq",
        base_url="https://api.groq.com/openai/v1",
        env_key_name="groq_api_key",
        default_model="llama-3.3-70b-versatile",
    ),
    "fireworks": ProviderConfig(
        name="Fireworks AI",
        base_url="https://api.fireworks.ai/inference/v1",
        env_key_name="fireworks_api_key",
        default_model="accounts/fireworks/models/gpt-oss-120b",
    ),
    "openrouter": ProviderConfig(
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        env_key_name="openrouter_api_key",
        default_model="meta-llama/llama-3.3-70b-instruct",
        extra_headers={"HTTP-Referer": "https://cecil-ai.local"},
    ),
}


# ── Role → recommended model overrides ───────────────────────────────

ROLE_MODEL_OVERRIDES: dict[str, dict[str, str]] = {
    "quant_researcher": {
        "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "groq": "llama-3.3-70b-versatile",
        "fireworks": "accounts/fireworks/models/gpt-oss-120b",
    },
    "portfolio_analyst": {
        "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "groq": "llama-3.3-70b-versatile",
        "fireworks": "accounts/fireworks/models/gpt-oss-120b",
    },
    "project_manager": {
        "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "groq": "llama-3.3-70b-versatile",
        "fireworks": "accounts/fireworks/models/gpt-oss-120b",
    },
    "research_intelligence": {
        "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "groq": "llama-3.3-70b-versatile",
        "fireworks": "accounts/fireworks/models/gpt-oss-120b",
    },
}


def get_model_for_role(role: str, provider_name: str) -> str:
    """Return the best model id given an agent role and provider.
    
    For Fireworks, dynamically fetches available models at runtime.
    """
    # For Fireworks, use dynamic model loading
    if provider_name == "fireworks":
        try:
            from cecil.models.dynamic_loader import get_fireworks_model
            
            model = get_fireworks_model("general")
            
            logger.debug("Dynamic Fireworks model for %s: %s", role, model.split("/")[-1])
            return model
            
        except Exception as e:
            logger.warning("Dynamic model loading failed, using static config: %s", e)
            # Fall through to static config
    
    # Static configuration for other providers
    overrides = ROLE_MODEL_OVERRIDES.get(role, {})
    if provider_name in overrides:
        return overrides[provider_name]
    return PROVIDERS[provider_name].default_model
