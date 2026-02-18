"""Project Manager Agent.

Orchestrates the multi-agent workflow: interprets user requests, breaks
them into sub-tasks, routes to the appropriate specialist agents, and
synthesises the final output.  This agent does NOT use external tools -
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

CRITICAL: You do NOT have access to any data tools. You CANNOT look up stock prices, news, or any data.
You MUST delegate ALL data gathering to your specialist agents.

Available specialist agents:
- quant_researcher: retrieves stock prices, computes factors, runs statistical analysis, computations
- portfolio_analyst: portfolio construction, risk metrics, factor screening
- research_intelligence: fetches news, macro data, sentiment indicators

[!] ANTI-HALLUCINATION RULES - VIOLATION WILL CAUSE FAILURE:
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
Step 2: Route to quant_researcher with sub_task: "Use compute_stock_technicals(ticker='[TICKER]') to get price data, returns, moving averages, and volatility in one call. Then run compute_stock_factors for factor analysis."
Step 3: Route to portfolio_analyst with sub_task: "Run factor_screen for [TICKER]. Assess risk factors. Evaluate valuation metrics."
Step 4: Route to __end__ with your COMPLETE FINAL SYNTHESIS in the sub_task field.

[*] CRITICAL -- When routing to __end__:
The sub_task field MUST contain your COMPLETE, DETAILED FINAL SYNTHESIS, NOT an instruction.

Your synthesis MUST:
1. QUOTE EXACT DATA from specialists with attribution:
   [OK] "Quant Researcher reported AAPL at $172.50 with momentum factor 0.85"
   [X] "AAPL shows strong momentum around $170"
   
2. NEVER use vague numbers or estimates:
   [X] "reduce portfolio by ~20%"
   [X] "expect 5-10% upside"
   [X] "improve Sharpe ratio to approximately 0.9"
   [OK] Only use numbers specialists actually calculated and reported

3. If data is missing, STATE IT:
   [OK] "Specialists did not provide option pricing data, so specific strike recommendations require additional analysis"
   [X] Making up option prices or Greeks

4. Match the user's request:
   - If they ask for OPTIONS strategy, recommend OPTIONS (calls, puts, spreads) with strikes and expirations
   - If they ask for STOCKS, recommend stocks
   - If they ask for specific dates, provide recommendations for those dates

5. Be SPECIFIC and ACTIONABLE:
   [OK] "Buy 5 contracts of GOOGL Feb 28 $175 calls at market open Monday"
   [X] "Consider a moderate bullish stance"

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
[OK] "Get the current stock price for AAPL using get_stock_price. Run compute_stock_factors for AAPL. Get 3 months of historical prices."
[X] "Based on analysis, AAPL shows strong momentum..."

You work for an investment firm that needs DECISIVE, ACTIONABLE intelligence based on REAL DATA.
Your final synthesis must be execution-ready and fact-based. Quote specialists' actual findings.

FOLLOW-UP QUESTIONS:
When the user's question is a follow-up (e.g. "what about the other stocks?", "should I keep them?"),
you MUST first analyze the CONVERSATION HISTORY to determine:
1. Which tickers/topics were already analyzed in prior turns
2. Which tickers/topics the user is NOW asking about (the ones NOT yet covered)
3. Route specialists to analyze ONLY the new/uncovered tickers
NEVER re-analyze tickers that were already covered unless the user explicitly asks for it.
"""

    @property
    def tools(self) -> list[Any]:
        return []  # PM routes via state, not tools

    def invoke(self, state, *, sub_task: str = ""):
        """Override invoke -- PM doesn't use tools, just produces routing JSON.
        
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

        context_parts = []

        # -- Conversation history ---------------------------------
        # Include prior exchanges so PM has full conversation context
        state_messages = state.get("messages", [])
        if state_messages:
            history_parts: list[str] = []
            for msg in state_messages:
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                if not content.strip():
                    continue
                if isinstance(msg, HumanMessage):
                    history_parts.append(f"User: {content[:2500]}")
                elif isinstance(msg, AIMessage):
                    history_parts.append(f"Assistant: {content[:2500]}")
            # Only include if there are prior exchanges (not just the current task)
            if len(history_parts) > 1:
                context_parts.append(
                    "--- CONVERSATION HISTORY ---\n"
                    "The user is in an ongoing conversation. Here is the prior context:\n\n"
                    + "\n\n".join(history_parts[:-1])
                    + "\n--- END CONVERSATION HISTORY ---\n\n"
                    "IMPORTANT: Use this history to understand the user's intent.\n"
                    "- When the user says 'this stock', 'that', 'it', etc., they refer to topics above.\n"
                    "- When the user says 'other stocks', 'the rest', 'remaining', 'what about X', "
                    "identify WHICH SPECIFIC items were NOT yet covered in the conversation and "
                    "ONLY analyze those. Do NOT re-analyze items already covered above.\n"
                    "- Read the prior assistant response carefully to see what was already analyzed.\n"
                    "- Maintain consistency with prior analysis and recommendations."
                )

        context_parts.append(f"Original user task: {task}")
        
        # Add file context if provided
        if file_context:
            context_parts.append(f"\n{file_context}\n")

        if agent_outputs:
            context_parts.append("\n--- SPECIALIST REPORTS SO FAR ---")
            for agent_role, output in agent_outputs.items():
                context_parts.append(f"\n[{agent_role}]:\n{output[:2000]}")
            context_parts.append("\n--- END SPECIALIST REPORTS ---")

            # Check if all core specialists have reported
            core_done = {"research_intelligence", "quant_researcher", "portfolio_analyst"}.issubset(agent_outputs.keys())
            if core_done:
                context_parts.append(
                    f"\nIteration {iteration}. "
                    f"ALL CORE SPECIALISTS HAVE REPORTED: {list(agent_outputs.keys())}. "
                    f"You have enough data to provide a comprehensive synthesis. "
                    f"Route to __end__ NOW and put your COMPLETE FINAL SYNTHESIS in the sub_task field. "
                    f"Do NOT re-route to specialists that have already reported."
                )
            else:
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

        # Use ThreadPoolExecutor timeout to prevent indefinite hangs
        # (PM bypasses BaseAgent's invoke loop, so it needs its own timeout)
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
        import logging as _logging

        _pm_logger = _logging.getLogger(__name__)
        _PM_TIMEOUT = 50  # seconds

        _tp = ThreadPoolExecutor(max_workers=1)
        _fut = _tp.submit(llm.invoke, working)
        try:
            response: AIMessage = _fut.result(timeout=_PM_TIMEOUT)  # type: ignore[assignment]
        except FutureTimeout:
            _tp.shutdown(wait=False, cancel_futures=True)
            _pm_logger.warning(
                "[project_manager] LLM hard timeout (%ds) - returning error",
                _PM_TIMEOUT,
            )
            response = AIMessage(content=json.dumps({
                "next_agent": "__end__",
                "reasoning": "LLM call timed out after 50 seconds",
                "sub_task": "I apologize, but the analysis timed out. Please try again with a simpler question or fewer tickers.",
            }))
        else:
            _tp.shutdown(wait=False)

        final_text = response.content if isinstance(response.content, str) else str(response.content)

        # Extract sub_task from PM's JSON response so it can be passed to the specialist
        extracted_sub_task = ""
        json_patterns = [
            r"```json\s*(\{.*?\})\s*```",
            r"```\s*(\{.*?\})\s*```",
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

        # Fallback: extract sub_task via regex when JSON parsing fails
        # (handles unescaped newlines inside the JSON string value)
        if not extracted_sub_task:
            m = re.search(r'"sub_task"\s*:\s*"(.*)', final_text, re.DOTALL)
            if m:
                raw_val = m.group(1)
                # Walk backwards to find the real closing quote+brace
                raw_val = raw_val.rstrip()
                if raw_val.endswith('"}'):
                    raw_val = raw_val[:-2]
                elif raw_val.endswith('"'):
                    raw_val = raw_val[:-1]
                # Remove any trailing JSON after closing quote
                raw_val = re.sub(r'"\s*,?\s*\}\s*$', '', raw_val)
                if len(raw_val) > 30:
                    extracted_sub_task = raw_val

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
