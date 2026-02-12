"""Base agent class providing common scaffolding.

All specialised agents inherit from ``BaseAgent`` and override
``system_prompt`` and ``tools``.  The ``invoke`` method runs the
LLM-with-tools loop and returns an updated ``AgentState``.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from cecil.models.client import get_model_client
from cecil.state.schema import AgentRole, AgentState

logger = logging.getLogger(__name__)

# Maximum tool-call round-trips per single agent invocation
_MAX_TOOL_ROUNDS = 6

# If the agent returns empty on its first try, retry with a nudge
_MAX_EMPTY_RETRIES = 2


class BaseAgent(ABC):
    """Abstract base for every specialised agent."""

    role: AgentRole

    def __init__(self) -> None:
        self._client = get_model_client()

    # ── subclass interface ───────────────────────────────────────────

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""

    @property
    @abstractmethod
    def tools(self) -> list[Any]:
        """Return the LangChain tools this agent may call."""

    # ── public API ───────────────────────────────────────────────────

    def invoke(self, state: AgentState, *, sub_task: str = "") -> AgentState:
        """Run the agent and return the updated state dict.

        This executes an LLM → tool-call → LLM loop for up to
        ``_MAX_TOOL_ROUNDS`` rounds, then returns the deltas that
        LangGraph should merge into the shared state.

        Parameters
        ----------
        sub_task:
            Specific instruction from the PM for this agent.  Injected
            as a ``HumanMessage`` so the LLM sees it as a direct request.
        """
        llm = self._get_llm()
        sys_msg = SystemMessage(content=self.system_prompt)

        # Build the task prompt — use sub_task if provided, else fall back
        task_text = sub_task or state.get("task", "")
        task_prompt = (
            f"Task: {task_text}\n\n"
            f"You MUST use your tools to gather real data before responding. "
            f"Do NOT make up numbers or data. Call the appropriate tools now."
        )

        # Start with system prompt + task as HumanMessage (clean context)
        working: list[Any] = [sys_msg, HumanMessage(content=task_prompt)]

        new_messages: list[Any] = []
        tool_calls_made = 0

        for _round in range(_MAX_TOOL_ROUNDS):
            response: AIMessage = llm.invoke(working)  # type: ignore[assignment]

            # Detect empty responses (no content AND no tool calls)
            if not response.tool_calls and not _has_content(response):
                logger.warning(
                    "[%s] empty response on round %d – nudging",
                    self.role,
                    _round,
                )
                # Nudge the model to call tools
                nudge = HumanMessage(
                    content=(
                        "Your response was empty. You MUST call at least one tool "
                        "to get real data. Here are your available tools: "
                        + ", ".join(t.name for t in self.tools)
                        + ". Call one now."
                    )
                )
                working.append(nudge)
                continue

            # Check for text-based tool calls (fallback for models that don't
            # use the native tool_calls mechanism)
            actual_tool_calls = response.tool_calls
            if not actual_tool_calls and _has_content(response):
                content_str = response.content if isinstance(response.content, str) else str(response.content)
                text_calls = _parse_text_tool_calls(content_str)
                if text_calls:
                    logger.info(
                        "[%s] detected %d text-based tool call(s) – executing",
                        self.role,
                        len(text_calls),
                    )
                    actual_tool_calls = text_calls

            new_messages.append(response)
            working.append(response)

            # If no tool calls, we're done
            if not actual_tool_calls:
                break

            # Execute tool calls
            tool_map = {t.name: t for t in self.tools}
            for tc in actual_tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                logger.info(
                    "[%s] calling tool %s(%s)",
                    self.role,
                    tool_name,
                    ", ".join(f"{k}={v!r}" for k, v in tool_args.items()),
                )
                tool_calls_made += 1
                tool_fn = tool_map.get(tool_name)
                if tool_fn is None:
                    result = json.dumps({"error": f"Unknown tool: {tool_name}"})
                else:
                    try:
                        result = tool_fn.invoke(tool_args)
                    except Exception as exc:
                        logger.exception("[%s] tool %s failed", self.role, tool_name)
                        result = json.dumps({"error": str(exc)})

                tool_msg = ToolMessage(
                    content=str(result),
                    tool_call_id=tc["id"],
                )
                new_messages.append(tool_msg)
                working.append(tool_msg)

        # If we went through all rounds without any tool calls and this agent
        # has tools, that's a problem — log it clearly
        if tool_calls_made == 0 and self.tools:
            logger.warning(
                "[%s] completed WITHOUT calling any tools! Response may be hallucinated.",
                self.role,
            )

        # Extract final text from the last AI message
        final_text = ""
        if new_messages:
            for msg in reversed(new_messages):
                if isinstance(msg, AIMessage) and _has_content(msg):
                    final_text = msg.content if isinstance(msg.content, str) else str(msg.content)
                    break

        result_entry = {
            "agent": self.role,
            "summary": final_text[:3000],
            "tool_calls_made": tool_calls_made,
        }

        return {
            "messages": new_messages,
            "current_agent": self.role,
            "results": [result_entry],
            "agent_outputs": {self.role: final_text[:3000]},
        }  # type: ignore[return-value]

    # ── internals ────────────────────────────────────────────────────

    def _get_llm(self) -> ChatOpenAI:
        tools = self.tools
        return self._client.get_chat_model(
            role=self.role,
            bind_tools=tools if tools else None,
        )


def _has_content(msg: AIMessage) -> bool:
    """Check if an AIMessage has non-empty content."""
    if not msg.content:
        return False
    if isinstance(msg.content, str):
        return bool(msg.content.strip())
    return bool(msg.content)


def _parse_text_tool_calls(text: str) -> list[dict]:
    """Parse text-based tool calls from models that don't use the tool_calls mechanism.

    Some models (e.g. Llama on Fireworks) output JSON like:
        {"type": "function", "name": "get_stock_price", "parameters": {"ticker": "AAPL"}}

    This function extracts those and converts them to tool_call dicts.
    """
    import re
    import uuid

    calls = []
    # Match JSON objects that look like function calls
    patterns = [
        r'\{"type"\s*:\s*"function"\s*,\s*"name"\s*:\s*"([^"]+)"\s*,\s*"parameters"\s*:\s*(\{[^}]*\})\s*\}',
        r'\{"name"\s*:\s*"([^"]+)"\s*,\s*"parameters"\s*:\s*(\{[^}]*\})\s*\}',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.DOTALL):
            try:
                name = match.group(1)
                args = json.loads(match.group(2))
                calls.append({
                    "name": name,
                    "args": args,
                    "id": f"text_call_{uuid.uuid4().hex[:8]}",
                })
            except (json.JSONDecodeError, IndexError):
                continue
        if calls:
            break
    return calls
