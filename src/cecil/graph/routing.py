"""Routing logic for the LangGraph edges.

The ``route_from_pm`` function inspects the Project Manager's last message
to determine which agent should run next (or whether to end).  It also
extracts the ``sub_task`` and stores it in state so the specialist knows
exactly what to do.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from langchain_core.messages import AIMessage

from cecil.state.schema import ALL_ROLES, AgentRole, AgentState, SPECIALIST_ROLES

logger = logging.getLogger(__name__)

# Type for conditional edge destinations
RouteTarget = Literal[
    "project_manager",
    "quant_researcher",
    "portfolio_analyst",
    "software_developer",
    "research_intelligence",
    "__end__",
]

_VALID_TARGETS: set[str] = {*ALL_ROLES, "__end__"}


def route_from_pm(state: AgentState) -> RouteTarget:
    """Parse the PM's response to decide the next graph node.

    The PM is instructed to include a JSON block with ``"next_agent"``
    and ``"sub_task"``.  This function extracts both.
    Falls back to ``"__end__"`` if parsing fails or the iteration cap
    is reached.
    """
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 10)

    if iteration >= max_iter:
        logger.warning("Max iterations (%d) reached – ending.", max_iter)
        return "__end__"

    # Find the PM's last AI message
    messages = state.get("messages", [])
    pm_text = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            pm_text = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    if not pm_text:
        logger.warning("No PM message found – ending.")
        return "__end__"

    next_agent, sub_task = _extract_routing(pm_text)

    logger.info(
        "PM routed → %s  (iteration %d/%d)  sub_task: %s",
        next_agent,
        iteration,
        max_iter,
        sub_task[:80] if sub_task else "(none)",
    )
    return next_agent  # type: ignore[return-value]


def route_back_to_pm(state: AgentState) -> RouteTarget:
    """After any specialist agent finishes, always return to the PM."""
    return "project_manager"


# ── Helpers ──────────────────────────────────────────────────────────


def _extract_routing(text: str) -> tuple[str, str]:
    """Extract ``next_agent`` and ``sub_task`` from the PM's response.

    Returns (next_agent, sub_task) tuple.
    """
    # Try JSON block first
    json_patterns = [
        r"```json\s*(\{.*?\})\s*```",
        r"```\s*(\{.*?\})\s*```",
        r"(\{[^{}]*\"next_agent\"[^{}]*\})",
    ]
    for pattern in json_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                candidate = data.get("next_agent", "").strip().lower()
                sub_task = data.get("sub_task", "")
                if candidate in _VALID_TARGETS:
                    return candidate, sub_task
            except (json.JSONDecodeError, AttributeError):
                continue

    # Try to parse the entire text as JSON (PM might return pure JSON)
    try:
        data = json.loads(text.strip())
        candidate = data.get("next_agent", "").strip().lower()
        sub_task = data.get("sub_task", "")
        if candidate in _VALID_TARGETS:
            return candidate, sub_task
    except (json.JSONDecodeError, AttributeError):
        pass

    # Fallback: look for agent name mentions
    text_lower = text.lower()
    for target in SPECIALIST_ROLES:
        if target in text_lower:
            return target, ""

    # If PM says "complete", "done", "final", etc., end
    end_keywords = ["__end__", "complete", "all done", "final answer", "task complete"]
    if any(kw in text_lower for kw in end_keywords):
        return "__end__", ""

    return "__end__", ""
