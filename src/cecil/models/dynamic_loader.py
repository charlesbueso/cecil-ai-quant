"""Dynamic model loader for Fireworks AI.

Fetches available models at runtime and caches them to avoid API calls.
Provides fallback model selection when the primary model is unavailable.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Fallback models if API fails
FALLBACK_MODELS = {
    "general": "accounts/fireworks/models/glm-5",
    "coder": "accounts/fireworks/models/deepseek-v3p1",
}

# Preferred models (in priority order) - must reliably emit structured tool_calls
# NOTE: kimi-k2 models are deprioritized because they emit malformed tool_call
# section markers (<|tool_calls_section_begin|>) with complex arguments,
# causing Fireworks to reject with HTTP 400.
# NOTE: mixtral-8x22b-instruct generates text about tools instead of actual
# tool_calls, causing agents to complete without real data.
PREFERRED_GENERAL_MODELS = [
    "glm-5",
    "glm-4p7",
    "gpt-oss-120b",
    "minimax-m2p5",
    "minimax-m2p1",
    "kimi-k2-instruct-0905",  # malformed tool_calls with large args
    "kimi-k2p5",              # same issue
    "mixtral-8x22b-instruct", # poor tool calling
]

PREFERRED_CODER_MODELS = [
    "deepseek-v3p2",
    "deepseek-v3p1",
    "qwen",
]

# Track models that failed during this session so we don't retry them
_failed_models: set[str] = set()


@lru_cache(maxsize=1)
def _fetch_available_models() -> dict[str, list[str]]:
    """Fetch all available Fireworks models with serverless + function calling support.
    
    Returns:
        Dict with 'general' and 'coder' lists of full model names, ordered by preference.
    """
    api_key = os.getenv("FIREWORKS_API_KEY")
    
    if not api_key:
        logger.warning("FIREWORKS_API_KEY not set, using fallback models")
        return {
            "general": [FALLBACK_MODELS["general"]],
            "coder": [FALLBACK_MODELS["coder"]],
        }
    
    account_id = "fireworks"
    url = f"https://api.fireworks.ai/v1/accounts/{account_id}/models"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    params = {"pageSize": 200}
    
    try:
        logger.debug("Fetching available Fireworks models...")
        response = httpx.get(url, headers=headers, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        models = data.get("models", [])
        
        # Filter for serverless + tools support
        general_models: list[tuple[str, str]] = []
        coder_models: list[tuple[str, str]] = []
        
        for model in models:
            if not model.get("supportsServerless") or not model.get("supportsTools"):
                continue
                
            name = model.get("name", "").replace(f"accounts/{account_id}/models/", "")
            full_name = f"accounts/{account_id}/models/{name}"
            
            # Categorize models
            if any(keyword in name.lower() for keyword in ["coder", "deepseek", "qwen"]):
                coder_models.append((name, full_name))
            else:
                general_models.append((name, full_name))
        
        def sort_by_preference(models_list: list[tuple[str, str]], preferences: list[str]) -> list[str]:
            """Sort models by preference order, putting preferred ones first."""
            ordered: list[str] = []
            remaining = list(models_list)
            
            for pref in preferences:
                for name, full_name in remaining[:]:
                    if pref.lower() in name.lower():
                        ordered.append(full_name)
                        remaining.remove((name, full_name))
                        break
            
            # Append any remaining models not in preference list
            for _, full_name in remaining:
                ordered.append(full_name)
            
            return ordered
        
        result = {
            "general": sort_by_preference(general_models, PREFERRED_GENERAL_MODELS) or [FALLBACK_MODELS["general"]],
            "coder": sort_by_preference(coder_models, PREFERRED_CODER_MODELS) or [FALLBACK_MODELS["coder"]],
        }
        
        logger.info(
            "Loaded Fireworks models: general=[%s], coder=[%s]",
            ", ".join(m.split("/")[-1] for m in result["general"][:3]),
            ", ".join(m.split("/")[-1] for m in result["coder"][:3]),
        )
        
        return result
        
    except Exception as e:
        logger.warning(
            "Failed to fetch Fireworks models (using fallbacks): %s",
            str(e)
        )
        return {
            "general": [FALLBACK_MODELS["general"]],
            "coder": [FALLBACK_MODELS["coder"]],
        }


def fetch_fireworks_models() -> dict[str, str]:
    """Backward-compatible: return the top-pick general and coder model.
    
    Returns:
        Dict with 'general' and 'coder' keys pointing to best available model.
    """
    all_models = _fetch_available_models()
    return {
        "general": _best_available(all_models["general"]),
        "coder": _best_available(all_models["coder"]),
    }


def _best_available(candidates: list[str]) -> str:
    """Return the first model in the list that hasn't failed."""
    for model in candidates:
        if model not in _failed_models:
            return model
    # Everything failed — clear the set and try again from the top
    logger.warning("All models have been marked as failed, resetting failure list")
    _failed_models.clear()
    return candidates[0] if candidates else FALLBACK_MODELS["general"]


def mark_model_failed(model_id: str) -> None:
    """Mark a model as unavailable so it won't be selected again this session."""
    _failed_models.add(model_id)
    logger.warning("Marked model as failed: %s", model_id.split("/")[-1])


def get_next_model(category: str, current_model: str) -> str | None:
    """Get the next available model after the current one fails.
    
    Args:
        category: 'general' or 'coder'
        current_model: The model that just failed
        
    Returns:
        Next model to try, or None if no more options
    """
    mark_model_failed(current_model)
    all_models = _fetch_available_models()
    candidates = all_models.get(category, [])
    
    next_model = _best_available(candidates)
    if next_model == current_model:
        return None  # No alternatives left
    
    logger.info(
        "Switching from %s → %s",
        current_model.split("/")[-1],
        next_model.split("/")[-1],
    )
    return next_model


def get_fireworks_model(role: str = "general") -> str:
    """Get the appropriate Fireworks model for a given role.
    
    Args:
        role: Either 'general' or 'coder'
        
    Returns:
        Full model name for Fireworks API
    """
    models = fetch_fireworks_models()
    
    return models["general"]
