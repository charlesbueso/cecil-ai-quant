"""Graph node functions.

Each function receives the full ``AgentState``, instantiates the
appropriate agent, runs it, and returns the state delta that LangGraph
should merge.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from cecil.agents.portfolio_analyst import PortfolioAnalystAgent
from cecil.agents.project_manager import ProjectManagerAgent
from cecil.agents.quant_researcher import QuantResearcherAgent
from cecil.agents.research_intelligence import ResearchIntelligenceAgent
from cecil.agents.software_developer import SoftwareDeveloperAgent
from cecil.state.schema import AgentState

logger = logging.getLogger(__name__)

# ── Lazy singletons ──────────────────────────────────────────────────

_agents: dict[str, Any] = {}


def _get_agent(role: str) -> Any:
    if role not in _agents:
        _agents[role] = {
            "project_manager": ProjectManagerAgent,
            "quant_researcher": QuantResearcherAgent,
            "portfolio_analyst": PortfolioAnalystAgent,
            "software_developer": SoftwareDeveloperAgent,
            "research_intelligence": ResearchIntelligenceAgent,
        }[role]()
    return _agents[role]


# ── Node: Project Manager ───────────────────────────────────────────


def project_manager_node(state: AgentState) -> dict[str, Any]:
    """Run the Project Manager to decide routing.

    The PM gets the full state including agent_outputs so it can see
    what specialists have reported and decide what to do next.
    """
    logger.info("──── Project Manager node  (iteration %d) ────", state.get("iteration", 0))
    agent = _get_agent("project_manager")
    delta = agent.invoke(state)
    delta["iteration"] = state.get("iteration", 0) + 1
    return delta


# ── Generic specialist node ─────────────────────────────────────────


def _specialist_node(role: str, state: AgentState) -> dict[str, Any]:
    """Run a specialist agent, passing it the sub_task from the PM.
    
    If the agent crashes (e.g. model unavailable), return an error result
    so the PM can route to a different agent instead of crashing the run.
    """
    sub_task = state.get("sub_task", "")
    logger.info("──── %s node ────  sub_task: %s", role, sub_task[:100] if sub_task else "(none)")
    agent = _get_agent(role)
    try:
        return agent.invoke(state, sub_task=sub_task)
    except Exception as exc:
        logger.error("[%s] agent CRASHED: %s", role, exc, exc_info=True)
        error_msg = f"Agent {role} encountered an error and could not complete: {exc}"
        return {
            "messages": [AIMessage(content=error_msg)],
            "current_agent": role,
            "results": [{
                "agent": role,
                "summary": error_msg,
                "tool_calls_made": 0,
            }],
            "agent_outputs": {role: error_msg},
        }


# ── Node: Quant Researcher ──────────────────────────────────────────


def quant_researcher_node(state: AgentState) -> dict[str, Any]:
    """Run the Quantitative Researcher agent."""
    return _specialist_node("quant_researcher", state)


# ── Node: Portfolio Analyst ─────────────────────────────────────────


def portfolio_analyst_node(state: AgentState) -> dict[str, Any]:
    """Run the Portfolio Analyst agent."""
    return _specialist_node("portfolio_analyst", state)


# ── Node: Software Developer ────────────────────────────────────────


def software_developer_node(state: AgentState) -> dict[str, Any]:
    """Run the Software Developer agent."""
    return _specialist_node("software_developer", state)


# ── Node: Research Intelligence ─────────────────────────────────────


def research_intelligence_node(state: AgentState) -> dict[str, Any]:
    """Run the Research Intelligence agent."""
    return _specialist_node("research_intelligence", state)
