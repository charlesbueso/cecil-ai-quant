"""LangGraph graph builder.

Constructs the compiled ``StateGraph`` that orchestrates the multi-agent
system.  The graph topology:

    ┌──────────────┐
    │   __start__  │
    └──────┬───────┘
           ▼
    ┌──────────────┐      ┌─────────────────────┐
    │  project_mgr │─────►│  route_from_pm()     │
    └──────────────┘      └──┬──┬──┬──┬──┬───────┘
                             │  │  │  │  │
              ┌──────────────┘  │  │  │  └──────────────┐
              ▼                 ▼  │  ▼                  ▼
      ┌────────────┐  ┌──────────┐│┌───────────┐ ┌────────────┐
      │quant_rsrch │  │portfolio ││ │sw_dev     │ │research_int│
      └─────┬──────┘  └────┬─────┘│└─────┬─────┘ └──────┬─────┘
            │               │      │      │              │
            └───────┬───────┘      │      └──────┬───────┘
                    ▼              ▼              ▼
              ┌──────────────┐  ┌──────┐
              │  project_mgr │  │ END  │
              └──────────────┘  └──────┘

Every specialist routes back to the PM; the PM decides the next step.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from cecil.graph.nodes import (
    portfolio_analyst_node,
    project_manager_node,
    quant_researcher_node,
    research_intelligence_node,
    software_developer_node,
)
from cecil.graph.routing import route_back_to_pm, route_from_pm
from cecil.state.schema import AgentState

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Construct and return the compiled LangGraph ``StateGraph``."""

    graph = StateGraph(AgentState)

    # ── Add nodes ────────────────────────────────────────────────────
    graph.add_node("project_manager", project_manager_node)
    graph.add_node("quant_researcher", quant_researcher_node)
    graph.add_node("portfolio_analyst", portfolio_analyst_node)
    graph.add_node("software_developer", software_developer_node)
    graph.add_node("research_intelligence", research_intelligence_node)

    # ── Entry point ──────────────────────────────────────────────────
    graph.set_entry_point("project_manager")

    # ── PM → conditional routing ─────────────────────────────────────
    graph.add_conditional_edges(
        "project_manager",
        route_from_pm,
        {
            "quant_researcher": "quant_researcher",
            "portfolio_analyst": "portfolio_analyst",
            "software_developer": "software_developer",
            "research_intelligence": "research_intelligence",
            "__end__": END,
        },
    )

    # ── Specialists → always back to PM ──────────────────────────────
    for specialist in [
        "quant_researcher",
        "portfolio_analyst",
        "software_developer",
        "research_intelligence",
    ]:
        graph.add_edge(specialist, "project_manager")

    logger.info("LangGraph built with %d nodes", 5)
    return graph


def compile_graph():
    """Build and compile the graph, ready for invocation."""
    graph = build_graph()
    return graph.compile()
