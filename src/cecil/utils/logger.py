"""Conversation logger – captures all agent messages to a text file."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage


class ConversationLogger:
    """Logs all agent interactions to a timestamped text file."""

    def __init__(self, log_dir: str = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"conversation_{timestamp}.txt"
        
        self._write_header()

    def _write_header(self) -> None:
        """Write the log file header."""
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("  CECIL AI – AGENT CONVERSATION LOG\n")
            f.write(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

    def log_state(self, state: dict[str, Any], step_name: str = "") -> None:
        """Log the current state after each graph node execution."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            if step_name:
                f.write("\n" + "─" * 80 + "\n")
                f.write(f"  STEP: {step_name}\n")
                f.write("─" * 80 + "\n")
            
            current = state.get("current_agent", "unknown")
            iteration = state.get("iteration", 0)
            
            f.write(f"\nIteration: {iteration}\n")
            f.write(f"Current Agent: {current}\n")
            f.write(f"Next Agent: {state.get('next_agent', 'N/A')}\n\n")
            
            # Log messages
            messages = state.get("messages", [])
            if messages:
                # Get only new messages (last few)
                for msg in messages[-5:]:  # Last 5 messages
                    self._log_message(f, msg)
            
            f.write("\n")

    def _log_message(self, f: Any, msg: Any) -> None:
        """Log a single message with formatting."""
        if isinstance(msg, HumanMessage):
            f.write("┌─ HUMAN ─────────────────────────────────────────\n")
            f.write(f"│ {msg.content}\n")
            f.write("└─────────────────────────────────────────────────\n\n")
        
        elif isinstance(msg, AIMessage):
            f.write("┌─ AI ────────────────────────────────────────────\n")
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            # Wrap long lines
            for line in content.split("\n"):
                if len(line) > 75:
                    while line:
                        f.write(f"│ {line[:75]}\n")
                        line = line[75:]
                else:
                    f.write(f"│ {line}\n")
            
            if msg.tool_calls:
                f.write("│\n│ 🔧 Tool Calls:\n")
                for tc in msg.tool_calls:
                    f.write(f"│   - {tc['name']}({', '.join(f'{k}=...' for k in tc.get('args', {}).keys())})\n")
            f.write("└─────────────────────────────────────────────────\n\n")
        
        elif isinstance(msg, ToolMessage):
            f.write("┌─ TOOL RESULT ───────────────────────────────────\n")
            content = str(msg.content)
            # Truncate very long tool results
            if len(content) > 500:
                content = content[:500] + "\n... [truncated]"
            for line in content.split("\n")[:10]:  # Max 10 lines
                f.write(f"│ {line[:75]}\n")
            f.write("└─────────────────────────────────────────────────\n\n")

    def log_final_summary(self, state: dict[str, Any]) -> None:
        """Log the final summary at the end."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write("  FINAL SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            
            results = state.get("results", [])
            f.write(f"Total agent contributions: {len(results)}\n")
            f.write(f"Total iterations: {state.get('iteration', 0)}\n")
            f.write(f"Status: {state.get('status', 'unknown')}\n\n")
            
            for i, r in enumerate(results, 1):
                agent = r.get("agent", "unknown")
                summary = r.get("summary", "")
                f.write(f"\n── Contribution {i}: {agent} ──\n")
                f.write(summary[:1000] + ("\n... [truncated]" if len(summary) > 1000 else "") + "\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"  Log completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n")

    def get_log_path(self) -> str:
        """Return the path to the current log file."""
        return str(self.log_file.absolute())
