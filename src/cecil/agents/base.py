"""Base agent class providing common scaffolding.

All specialised agents inherit from ``BaseAgent`` and override
``system_prompt`` and ``tools``.  The ``invoke`` method runs the
LLM-with-tools loop and returns an updated ``AgentState``.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from cecil.models.client import get_model_client
from cecil.state.schema import AgentRole, AgentState

logger = logging.getLogger(__name__)

# Maximum tool-call round-trips per single agent invocation
_MAX_TOOL_ROUNDS = 3

# If the agent returns empty on its first try, retry with a nudge
_MAX_EMPTY_RETRIES = 2

# Cap tool result size to prevent context bloat (characters)
_MAX_TOOL_RESULT_CHARS = 2000

# After this many rounds, compact older tool results to save context
_COMPACT_AFTER_ROUND = 1

# Max chars to keep per old tool result during compaction
_COMPACT_TOOL_CHARS = 500

# Hard cap on total working context chars — if exceeded, aggressively trim
_MAX_TOTAL_CONTEXT_CHARS = 12000

# Hard wall-clock timeout for a single llm.invoke() call (seconds).
# The HTTP-level request_timeout can be fooled by slow-drip streaming;
# this ThreadPoolExecutor timeout guarantees we regain control.
_LLM_HARD_TIMEOUT = 50


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
        
        # Add file context if provided
        file_context = state.get("file_context", "")
        file_section = f"\n\n{file_context}\n" if file_context else ""
        
        # Build conversation history context from prior exchanges
        # This gives agents memory of what was discussed in the conversation
        conversation_context = ""
        state_messages = state.get("messages", [])
        if state_messages:
            history_parts: list[str] = []
            for msg in state_messages:
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                if not content.strip():
                    continue
                if isinstance(msg, HumanMessage):
                    history_parts.append(f"User: {content[:500]}")
                elif isinstance(msg, AIMessage):
                    history_parts.append(f"Assistant: {content[:500]}")
            # Only include history if there are prior exchanges (not just the latest message)
            if len(history_parts) > 1:
                conversation_context = (
                    "\n\n--- CONVERSATION HISTORY ---\n"
                    "The user is in an ongoing conversation. Here is the prior context:\n\n"
                    + "\n\n".join(history_parts[:-1])  # Exclude the last msg (it's the current task)
                    + "\n--- END CONVERSATION HISTORY ---\n\n"
                    "Use this history to understand the user's intent and maintain consistency "
                    "with prior analysis and recommendations.\n"
                )
        
        # Check for images — if present, use vision model with multimodal content
        image_contents = state.get("image_contents", [])
        
        task_prompt = (
            f"{conversation_context}"
            f"Task: {task_text}\n\n"
            f"CRITICAL: You have access to tools. You MUST use them to gather data BEFORE providing analysis.\n"
            f"Do NOT write about calling tools - ACTUALLY call them using the function calling mechanism.\n"
            f"Do NOT say 'Tool Call: function_name()' in text - use the structured tool calling API.\n\n"
            f"Available tools: {', '.join(t.name for t in self.tools)}\n\n"
            f"After gathering REAL data from tools, provide DECISIVE, ACTION-ORIENTED analysis with specific recommendations. "
            f"You work for an investment firm that needs execution-ready intelligence, not academic disclaimers. "
            f"No hedging like 'this would be speculation' - provide your best professional assessment based on the data."
            f"{file_section}"
        )

        if image_contents:
            # Build multimodal HumanMessage with text + image content blocks
            content_blocks: list[dict] = [{"type": "text", "text": task_prompt}]
            for img in image_contents:
                if img.get("data_url"):
                    content_blocks.append({
                        "type": "image_url",
                        "image_url": {"url": img["data_url"]},
                    })
            
            # Add image extraction instruction
            content_blocks.insert(1, {
                "type": "text",
                "text": (
                    "\n\nYou have been provided with image(s). "
                    "Carefully analyze the visual content — extract any text, tables, charts, numbers, "
                    "or relevant financial data visible in the image(s). "
                    "Include the extracted information in your analysis.\n"
                ),
            })
            
            human_msg = HumanMessage(content=content_blocks)
            
            # Use vision-capable model for this invocation
            llm = self._get_vision_llm()
        else:
            human_msg = HumanMessage(content=task_prompt)

        # Start with system prompt + task as HumanMessage (clean context)
        working: list[Any] = [sys_msg, human_msg]

        new_messages: list[Any] = []
        tool_calls_made = 0
        empty_retries = 0

        for _round in range(_MAX_TOOL_ROUNDS):
            # Compact older tool results to prevent context bloat
            if _round >= _COMPACT_AFTER_ROUND:
                _compact_working_context(working)

            ctx_chars = sum(len(getattr(m, 'content', '') or '') for m in working)

            # Hard cap: if context still too large after compaction, drop oldest tool msgs
            if ctx_chars > _MAX_TOTAL_CONTEXT_CHARS:
                _hard_trim_context(working, _MAX_TOTAL_CONTEXT_CHARS)
                ctx_chars = sum(len(getattr(m, 'content', '') or '') for m in working)

            logger.info(
                "[%s] LLM call round %d  (context ~%d chars, %d msgs)",
                self.role, _round, ctx_chars, len(working),
            )
            try:
                # Hard wall-clock timeout via ThreadPoolExecutor.
                # request_timeout alone can be fooled by slow-drip streaming.
                # NOTE: We must NOT use `with ThreadPoolExecutor(...) as _tp:`
                # because exiting the context manager calls shutdown(wait=True),
                # which blocks forever if the LLM thread is still hanging.
                _tp = ThreadPoolExecutor(max_workers=1)
                _fut = _tp.submit(llm.invoke, working)
                try:
                    response: AIMessage = _fut.result(timeout=_LLM_HARD_TIMEOUT)  # type: ignore[assignment]
                except FutureTimeout:
                    # Abandon the hanging thread — do NOT wait for it
                    _tp.shutdown(wait=False, cancel_futures=True)
                    logger.warning(
                        "[%s] LLM hard timeout (%ds) on round %d – trying fallback",
                        self.role, _LLM_HARD_TIMEOUT, _round,
                    )
                    new_llm = self._try_fallback_model(llm)
                    if new_llm is not None:
                        llm = new_llm
                        continue  # retry this round with the next model
                    # No fallback available — return what we have
                    if new_messages:
                        break
                    raise TimeoutError(
                        f"{self.role}: LLM hard timeout after {_LLM_HARD_TIMEOUT}s, no fallback available"
                    )
                else:
                    _tp.shutdown(wait=False)
            except TimeoutError:
                raise  # re-raise our own TimeoutError
            except Exception as exc:
                error_str = str(exc).lower()
                is_recoverable = any(kw in error_str for kw in [
                    "no healthy upstream", "model not found", "404", "503",
                    "502", "unavailable", "not available",
                    "timed out", "timeout", "read timeout", "connect timeout",
                    "400", "invalid_request_error", "missing tool calls",
                    "tool_calls_section", "malformed",
                    "429", "rate limit", "rate_limit", "too many requests",
                ])
                
                if is_recoverable:
                    # Try to swap to a fallback model
                    logger.warning(
                        "[%s] Recoverable error on round %d, trying fallback: %s",
                        self.role, _round, str(exc)[:150],
                    )
                    new_llm = self._try_fallback_model(llm)
                    if new_llm is not None:
                        llm = new_llm
                        continue  # Retry with the new model
                
                logger.error("[%s] LLM call failed on round %d: %s", self.role, _round, exc)
                # If we already have some messages, return what we have
                if new_messages:
                    break
                # Otherwise, propagate so the node-level handler can catch it
                raise

            # Detect empty responses (no content AND no tool calls)
            if not response.tool_calls and not _has_content(response):
                logger.warning(
                    "[%s] empty response on round %d – nudging",
                    self.role,
                    _round,
                )
                empty_retries += 1
                if empty_retries >= _MAX_EMPTY_RETRIES:
                    logger.error("[%s] gave up after %d empty retries", self.role, empty_retries)
                    break
                # Nudge the model to call tools
                nudge = HumanMessage(
                    content=(
                        "Your response was empty. You MUST call at least one tool "
                        "to get real data. Here are your available tools: "
                        + ", ".join(t.name for t in self.tools)
                        + ". Call one now to gather data, then provide decisive, actionable analysis."
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

            # If no tool calls, check if we should force a retry
            if not actual_tool_calls:
                # On first round with no tool calls, FORCE the agent to use tools
                if _round == 0 and tool_calls_made == 0 and self.tools:
                    logger.warning(
                        "[%s] tried to respond without calling ANY tools on round 0 - FORCING retry",
                        self.role
                    )
                    # Keep the AI response in `working` to maintain alternating roles,
                    # then add a HumanMessage nudging the model to call tools.
                    force_tool_msg = HumanMessage(
                        content=(
                            f"Your response did not call any tools. You MUST call tools to get real data.\n"
                            f"Available tools: {', '.join(t.name for t in self.tools)}\n"
                            f"Call at least one tool NOW using the function calling mechanism. "
                            f"Do NOT write about calling tools — actually invoke them."
                        )
                    )
                    working.append(force_tool_msg)
                    continue
                elif _round == 0 and tool_calls_made == 0:
                    logger.warning(
                        "[%s] finished without making ANY tool calls - agent may be hallucinating tool usage",
                        self.role
                    )
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

                result_str = _truncate_tool_result(str(result), tool_name)
                tool_msg = ToolMessage(
                    content=result_str,
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

    def _get_vision_llm(self) -> ChatOpenAI:
        """Return a vision-capable LLM for processing image inputs.
        
        Uses Groq's Llama 4 Scout model which supports multimodal vision.
        Falls back to the regular LLM if the vision model isn't available.
        """
        try:
            tools = self.tools
            llm = self._client.get_chat_model(
                role=self.role,
                provider_name="groq",
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                bind_tools=tools if tools else None,
                max_tokens=4096,
            )
            logger.info("[%s] Using vision model: meta-llama/llama-4-scout-17b-16e-instruct", self.role)
            return llm
        except Exception as exc:
            logger.warning(
                "[%s] Vision model unavailable (%s), falling back to default LLM",
                self.role, exc,
            )
            return self._get_llm()

    def _try_fallback_model(self, current_llm: ChatOpenAI) -> ChatOpenAI | None:
        """Try to swap to the next available model when the current one is down.
        
        Returns a new ChatOpenAI instance, or None if no fallback is available.
        """
        current_model = current_llm.model_name
        base_url = getattr(current_llm, "openai_api_base", "") or ""

        # ── Groq fallback chain ──────────────────────────────────────
        if "groq.com" in base_url:
            groq_fallbacks = [
                "llama-3.3-70b-versatile",
                "llama-3.1-70b-versatile",
                "llama-3.1-8b-instant",
                "gemma2-9b-it",
            ]
            try:
                cur_idx = groq_fallbacks.index(current_model)
            except ValueError:
                cur_idx = -1
            next_idx = cur_idx + 1
            if next_idx < len(groq_fallbacks):
                next_model = groq_fallbacks[next_idx]
                logger.info(
                    "[%s] Groq fallback: %s → %s",
                    self.role, current_model, next_model,
                )
                tools = self.tools
                return self._client.get_chat_model(
                    role=self.role,
                    model=next_model,
                    bind_tools=tools if tools else None,
                )
            logger.error("[%s] No Groq fallback models left after %s", self.role, current_model)
            return None

        # ── Fireworks fallback chain (dynamic loader) ────────────────
        category = "general"
        
        try:
            from cecil.models.dynamic_loader import get_next_model
            next_model = get_next_model(category, current_model)
            if next_model is None:
                logger.error("[%s] No fallback models available after %s failed", self.role, current_model.split("/")[-1])
                return None
            
            logger.info(
                "[%s] Switching model: %s → %s",
                self.role, current_model.split("/")[-1], next_model.split("/")[-1],
            )
            tools = self.tools
            return self._client.get_chat_model(
                role=self.role,
                model=next_model,
                bind_tools=tools if tools else None,
            )
        except Exception as exc:
            logger.error("[%s] Failed to load fallback model: %s", self.role, exc)
            return None


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


def _truncate_tool_result(text: str, tool_name: str) -> str:
    """Truncate oversized tool output to keep context manageable.

    Large price arrays, factor tables, etc. can balloon the working
    context and cause the model to hang or time out on the synthesis
    call.  This helper caps results at ``_MAX_TOOL_RESULT_CHARS`` and
    tries to preserve valid JSON when possible.
    """
    if len(text) <= _MAX_TOOL_RESULT_CHARS:
        return text

    original_len = len(text)
    truncation_note = (
        f'\n... [truncated from {original_len:,} to {_MAX_TOOL_RESULT_CHARS:,} chars]'
    )

    # For JSON results, try to keep a valid structure
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        # Keep the first chunk + a note so the model knows data was cut
        cut = text[: _MAX_TOOL_RESULT_CHARS - len(truncation_note)]
        result = cut + truncation_note
    else:
        result = text[: _MAX_TOOL_RESULT_CHARS - len(truncation_note)] + truncation_note

    logger.debug(
        "Truncated %s result: %d → %d chars",
        tool_name,
        original_len,
        len(result),
    )
    return result


def _compact_working_context(working: list[Any]) -> None:
    """Shrink older ToolMessage content in-place to free context budget.

    Keeps the *last* batch of ToolMessages at full size (they are the
    most recent data the model needs for its next decision) and
    aggressively trims everything older.  This prevents the cumulative
    context from growing without bound across tool-call rounds.
    """
    # Find the index of the last AIMessage — everything before it is "old"
    last_ai_idx = -1
    for i in range(len(working) - 1, -1, -1):
        if isinstance(working[i], AIMessage):
            last_ai_idx = i
            break

    if last_ai_idx <= 0:
        return  # nothing old to compact

    compacted = 0
    for i in range(last_ai_idx):
        msg = working[i]
        if isinstance(msg, ToolMessage) and len(msg.content) > _COMPACT_TOOL_CHARS:
            original = len(msg.content)
            short = msg.content[:_COMPACT_TOOL_CHARS] + " ... [earlier result trimmed]"
            working[i] = ToolMessage(
                content=short,
                tool_call_id=msg.tool_call_id,
            )
            compacted += original - len(short)

    if compacted > 0:
        logger.info("Context compacted: freed ~%d chars from older tool results", compacted)


def _hard_trim_context(working: list[Any], target_chars: int) -> None:
    """Drop the oldest ToolMessage/AIMessage pairs until under *target_chars*.

    Never removes the first two messages (SystemMessage + HumanMessage) or the
    last two messages (most recent exchange).  Removes surrounding AI messages
    together with their ToolMessages to avoid orphaned tool_call_ids.
    """
    # Indices we're allowed to remove (everything between first 2 and last 2)
    removable = list(range(2, max(2, len(working) - 2)))
    removed_chars = 0

    total = sum(len(getattr(m, "content", "") or "") for m in working)
    to_remove: list[int] = []

    for idx in removable:
        if total - removed_chars <= target_chars:
            break
        content = getattr(working[idx], "content", "") or ""
        if content:
            to_remove.append(idx)
            removed_chars += len(content)

    if to_remove:
        for idx in reversed(to_remove):
            working.pop(idx)
        logger.warning(
            "Hard-trimmed %d messages (~%d chars) to stay under %d char limit",
            len(to_remove),
            removed_chars,
            target_chars,
        )
