"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration – reads from .env or environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM provider keys ────────────────────────────────────────────
    together_api_key: str = ""
    groq_api_key: str = ""
    fireworks_api_key: str = ""
    openrouter_api_key: str = ""

    # ── Per-agent provider routing ───────────────────────────────────
    quant_researcher_provider: str = "groq"
    portfolio_analyst_provider: str = "groq"
    project_manager_provider: str = "groq"
    research_intelligence_provider: str = "groq"

    # ── External data keys ───────────────────────────────────────────
    alpha_vantage_api_key: str = ""
    fred_api_key: str = ""
    news_api_key: str = ""
    finnhub_api_key: str = ""
    fmp_api_key: str = ""  # Financial Modeling Prep

    # ── Runtime ──────────────────────────────────────────────────────
    log_level: str = "INFO"
    max_agent_iterations: int = Field(default=15, ge=1, le=50)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
