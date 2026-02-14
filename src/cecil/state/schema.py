"""LangGraph shared state schema.

All agents read from / write to this single ``AgentState`` that flows
through the graph.  Using ``Annotated[..., operator.add]`` for list
fields lets LangGraph automatically merge updates from parallel branches.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

# ── Agent role literals ──────────────────────────────────────────────

AgentRole = Literal[
    "project_manager",
    "quant_researcher",
    "portfolio_analyst",
    "software_developer",
    "research_intelligence",
]

ALL_ROLES: list[AgentRole] = [
    "project_manager",
    "quant_researcher",
    "portfolio_analyst",
    "software_developer",
    "research_intelligence",
]

SPECIALIST_ROLES: list[AgentRole] = [
    "quant_researcher",
    "portfolio_analyst",
    "software_developer",
    "research_intelligence",
]

# ── Task status ──────────────────────────────────────────────────────

TaskStatus = Literal["pending", "in_progress", "completed", "failed"]


# ── Structured sub-results ───────────────────────────────────────────

@dataclass
class TaskResult:
    """One agent's contribution to the overall task."""

    agent: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = "completed"


def _merge_agent_outputs(
    existing: dict[str, str], new: dict[str, str]
) -> dict[str, str]:
    """Merge agent_outputs dicts, appending new results."""
    merged = dict(existing)
    for k, v in new.items():
        if k in merged:
            merged[k] = merged[k] + "\n\n" + v
        else:
            merged[k] = v
    return merged


# ── LangGraph state ─────────────────────────────────────────────────

class AgentState(TypedDict, total=False):
    """Shared state flowing through the LangGraph graph.

    Fields
    ------
    messages:
        Full conversation history; auto-merged via ``add_messages``.
    task:
        Human-readable description of the current objective.
    current_agent:
        Which agent is currently executing.
    next_agent:
        Where the project manager wants to route next.
    sub_task:
        Specific instruction from the PM for the next specialist.
    context:
        Arbitrary key/value context any agent can enrich.
    results:
        Accumulated per-agent results (list, append-merged).
    agent_outputs:
        Map of agent_role → their latest text output. Used by PM
        to see what specialists have actually produced.
    iteration:
        How many agent hops have been executed so far.
    max_iterations:
        Safety cap to avoid infinite loops.
    status:
        Overall task status.
    error:
        Last error message, if any.
    file_context:
        Parsed file content provided by the user (optional).
    """

    messages: Annotated[list[AnyMessage], add_messages]
    task: str
    current_agent: AgentRole
    next_agent: AgentRole | Literal["__end__"]
    sub_task: str
    context: dict[str, Any]
    results: Annotated[list[dict[str, Any]], operator.add]
    agent_outputs: Annotated[dict[str, str], _merge_agent_outputs]
    iteration: int
    max_iterations: int
    status: TaskStatus
    error: str
    file_context: str
