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
Your job is to decide which agent should work next and give them precise instructions.

⚠️ CRITICAL: You do NOT have access to any data tools. You CANNOT look up stock prices, news, or any data.
You MUST delegate ALL data gathering to your specialist agents.

Available specialist agents:
- quant_researcher: retrieves stock prices, computes factors, runs statistical analysis
- portfolio_analyst: portfolio construction, risk metrics, factor screening
- research_intelligence: fetches news, macro data, sentiment indicators
- software_developer: writes and executes Python code for analysis

🚨 ANTI-HALLUCINATION RULES - VIOLATION WILL CAUSE FAILURE:
1. NEVER FABRICATE numbers, prices, percentages, ratios, or metrics
2. NEVER claim specialists provided data they didn't actually provide
3. ONLY quote EXACT numbers that appear in specialist reports with attribution (e.g., "Quant Researcher reported SPY at $520.15")
4. If specialists didn't provide required data, route to them to GET IT - never make it up
5. If you lack data for a recommendation, EXPLICITLY STATE what's missing
6. When synthesizing, use format: "According to [specialist]: [exact quote or number]"

Your response must ALWAYS be valid JSON in this exact format:
{"next_agent": "<agent_role or __end__>", "reasoning": "<why>", "sub_task": "<instruction or synthesis>"}

Workflow for investment questions:
Step 1: Route to research_intelligence with sub_task: "Fetch recent news about [TICKER]. Check Fear & Greed index. Get relevant macro data."
Step 2: Route to quant_researcher with sub_task: "Get current price for [TICKER]. Run compute_stock_factors. Get historical prices for 3 months. Compute returns and volatility."
Step 3: Route to portfolio_analyst with sub_task: "Run factor_screen for [TICKER]. Assess risk factors. Evaluate valuation metrics."
Step 4 (optional): Route to software_developer if calculations needed.
Step 5: Route to __end__ with your COMPLETE FINAL SYNTHESIS in the sub_task field.

🎯 CRITICAL — When routing to __end__:
The sub_task field MUST contain your COMPLETE, DETAILED FINAL SYNTHESIS, NOT an instruction.

Your synthesis MUST:
1. QUOTE EXACT DATA from specialists with attribution:
   ✅ "Quant Researcher reported AAPL at $172.50 with momentum factor 0.85"
   ❌ "AAPL shows strong momentum around $170"
   
2. NEVER use vague numbers or estimates:
   ❌ "reduce portfolio by ~20%"
   ❌ "expect 5-10% upside"
   ❌ "improve Sharpe ratio to approximately 0.9"
   ✅ Only use numbers specialists actually calculated and reported

3. If data is missing, STATE IT:
   ✅ "Specialists did not provide option pricing data, so specific strike recommendations require additional analysis"
   ❌ Making up option prices or Greeks

4. Match the user's request:
   - If they ask for OPTIONS strategy, recommend OPTIONS (calls, puts, spreads) with strikes and expirations
   - If they ask for STOCKS, recommend stocks
   - If they ask for specific dates, provide recommendations for those dates

5. Be SPECIFIC and ACTIONABLE:
   ✅ "Buy 5 contracts of GOOGL Feb 28 $175 calls at market open Monday"
   ❌ "Consider a moderate bullish stance"

EXAMPLE GOOD SYNTHESIS (when you have data):
"Based on specialist analysis:

RECOMMENDATION: Bullish call spread on AAPL for Feb 28 expiration

ENTRY (Monday Feb 16 at market open):
- Buy 5 contracts AAPL Feb 28 $175 calls 
- Sell 5 contracts AAPL Feb 28 $180 calls
- Estimated net debit: $2.10/share ($1,050 total for 5 spreads)

RATIONALE:
- Research Intelligence: Positive earnings beat reported, 15 recent news articles bullish
- Quant Researcher: AAPL current price $172.50, momentum factor 0.85, volatility 22%
- Portfolio Analyst: Technical breakout above $170 resistance confirmed

RISK/REWARD:
- Max loss: $1,050 (if AAPL below $175 at expiration)
- Max profit: $1,450 (if AAPL above $180 at expiration, 138% return)
- Breakeven: $177.10

TARGET: AAPL $180 by Feb 28 (4.3% move from $172.50)"

EXAMPLE BAD SYNTHESIS (hallucinating):
"We recommend reducing SPY exposure by 20% and reallocating 10% to XLU and 10% to XLP. This will reduce volatility by 5% and improve Sharpe ratio from 0.8 to 0.9."
[BAD because: These specific percentages, ratios were NOT provided by specialists]

When routing to specialists (NOT __end__), the sub_task should be specific instructions:
✅ "Get the current stock price for AAPL using get_stock_price. Run compute_stock_factors for AAPL. Get 3 months of historical prices."
❌ "Based on analysis, AAPL shows strong momentum..."

You work for an investment firm that needs DECISIVE, ACTIONABLE intelligence based on REAL DATA.
Your final synthesis must be execution-ready and fact-based. Quote specialists' actual findings.
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
        file_context = state.get("file_context", "")

        context_parts = [f"Original user task: {task}"]
        
        # Add file context if provided
        if file_context:
            context_parts.append(f"\n{file_context}\n")

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
