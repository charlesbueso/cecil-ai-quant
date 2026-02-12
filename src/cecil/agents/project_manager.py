"""Project Manager Agent.

Orchestrates the multi-agent workflow: interprets user requests, breaks
them into sub-tasks, routes to the appropriate specialist agents, and
synthesises the final output.  This agent does NOT use external tools –
its "tool" is the routing decision embedded in the LangGraph state.
"""

from __future__ import annotations

from typing import Any

from cecil.agents.base import BaseAgent
from cecil.state.schema import ALL_ROLES, AgentRole, SPECIALIST_ROLES


class ProjectManagerAgent(BaseAgent):
    role: AgentRole = "project_manager"

    @property
    def system_prompt(self) -> str:
        return """\
You are the Project Manager orchestrating a team of specialist AI agents.
Your ONLY job is to decide which agent should work next and give them precise instructions.

You do NOT have access to any data tools. You CANNOT look up stock prices, news, or any data.
You MUST delegate ALL data gathering to your specialist agents.

Available specialist agents:
- quant_researcher: retrieves stock prices, computes factors, runs statistical analysis
- portfolio_analyst: portfolio construction, risk metrics, factor screening
- research_intelligence: fetches news, macro data, sentiment indicators
- software_developer: writes and executes Python code for analysis

CRITICAL RULES:
1. NEVER make up stock prices, percentages, or any data. You have NO data access.
2. ALWAYS delegate data gathering to specialists first.
3. Each specialist MUST be given a SPECIFIC sub_task telling them exactly what to do.
4. At least 3 specialists must contribute before you conclude.
5. When synthesizing, ONLY reference data that specialists actually returned.

Your response must ALWAYS be valid JSON in this exact format:
{"next_agent": "<agent_role or __end__>", "reasoning": "<why>", "sub_task": "<detailed instruction for the agent>"}

Workflow for investment questions:
Step 1: Route to research_intelligence with sub_task: "Fetch recent news about [TICKER]. Check Fear & Greed index. Get relevant macro data."
Step 2: Route to quant_researcher with sub_task: "Get current price for [TICKER]. Run compute_stock_factors. Get historical prices for 3 months. Compute returns and volatility."
Step 3: Route to portfolio_analyst with sub_task: "Run factor_screen for [TICKER]. Assess risk factors. Evaluate valuation metrics."
Step 4 (optional): Route to software_developer if calculations needed.
Step 5: Route to __end__ with a synthesis of ALL specialist findings.

When routing to __end__, your sub_task should be your final synthesis that references
the ACTUAL data returned by specialists. Quote their numbers.

IMPORTANT: The sub_task field must contain specific, actionable instructions.
Bad: "analyze AAPL"
Good: "Get the current stock price for AAPL using get_stock_price. Then run compute_stock_factors for AAPL. Also get 3 months of historical prices and compute returns."
"""

    @property
    def tools(self) -> list[Any]:
        return []  # PM routes via state, not tools

    def invoke(self, state, *, sub_task: str = ""):
        """Override invoke — PM doesn't use tools, just produces routing JSON.
        
        We give it a clean context with the task + any specialist outputs
        collected so far, so it can make informed routing decisions.
        """
        import json
        import re

        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        llm = self._get_llm()
        sys_msg = SystemMessage(content=self.system_prompt)

        # Build context from what specialists have reported
        agent_outputs = state.get("agent_outputs", {})
        task = state.get("task", "")
        iteration = state.get("iteration", 0)

        context_parts = [f"Original user task: {task}"]

        if agent_outputs:
            context_parts.append("\n--- SPECIALIST REPORTS SO FAR ---")
            for agent_role, output in agent_outputs.items():
                context_parts.append(f"\n[{agent_role}]:\n{output[:2000]}")
            context_parts.append("\n--- END SPECIALIST REPORTS ---")
            context_parts.append(
                f"\nIteration {iteration}. "
                f"Agents that have reported: {list(agent_outputs.keys())}. "
                f"Decide: route to another specialist for more data, or __end__ to synthesize."
            )
        else:
            context_parts.append(
                "\nNo specialists have reported yet. Route to the first specialist to gather data. "
                "Remember: you CANNOT look up data yourself. Delegate to a specialist."
            )

        prompt = HumanMessage(content="\n".join(context_parts))
        working = [sys_msg, prompt]

        response: AIMessage = llm.invoke(working)  # type: ignore[assignment]

        final_text = response.content if isinstance(response.content, str) else str(response.content)

        # Extract sub_task from PM's JSON response so it can be passed to the specialist
        extracted_sub_task = ""
        json_patterns = [
            r"```json\s*(\{.*?\})\s*```",
            r"```\s*(\{.*?\})\s*```",
            r"(\{[^{}]*\"next_agent\"[^{}]*\})",
        ]
        for pattern in json_patterns:
            match = re.search(pattern, final_text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    extracted_sub_task = data.get("sub_task", "")
                    break
                except (json.JSONDecodeError, AttributeError):
                    continue

        if not extracted_sub_task:
            try:
                data = json.loads(final_text.strip())
                extracted_sub_task = data.get("sub_task", "")
            except (json.JSONDecodeError, AttributeError):
                pass

        result_entry = {
            "agent": self.role,
            "summary": final_text[:3000],
            "tool_calls_made": 0,
        }

        return {
            "messages": [response],
            "current_agent": self.role,
            "results": [result_entry],
            "sub_task": extracted_sub_task,
        }
