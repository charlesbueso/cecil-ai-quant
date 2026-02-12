"""Provider definitions for open-source LLM API endpoints.

Every provider uses the OpenAI-compatible chat completions format so we
can swap backends with a single config change.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
        default_model="accounts/fireworks/models/deepseek-v3-0324",
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
    },
    "portfolio_analyst": {
        "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "groq": "llama-3.3-70b-versatile",
    },
    "software_developer": {
        "together": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "groq": "qwen-2.5-coder-32b",
        "fireworks": "accounts/fireworks/models/deepseek-v3-0324",
        "openrouter": "qwen/qwen-2.5-coder-32b-instruct",
    },
    "project_manager": {
        "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "groq": "llama-3.3-70b-versatile",
    },
    "research_intelligence": {
        "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "groq": "llama-3.3-70b-versatile",
    },
}


def get_model_for_role(role: str, provider_name: str) -> str:
    """Return the best model id given an agent role and provider."""
    overrides = ROLE_MODEL_OVERRIDES.get(role, {})
    if provider_name in overrides:
        return overrides[provider_name]
    return PROVIDERS[provider_name].default_model
