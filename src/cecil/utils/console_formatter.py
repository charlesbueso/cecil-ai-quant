"""Enhanced console output formatter for Cecil AI results.

Provides rich, colorful terminal output with tables and structured formatting.
"""

from __future__ import annotations

import json
import re
from typing import Any


class Colors:
    """ANSI color codes for terminal output."""
    
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Backgrounds
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'


class ConsoleFormatter:
    """Format Cecil AI output for enhanced console display."""
    
    AGENT_COLORS = {
        "project_manager": Colors.BRIGHT_MAGENTA,
        "quant_researcher": Colors.BRIGHT_CYAN,
        "portfolio_analyst": Colors.BRIGHT_GREEN,
        "research_intelligence": Colors.BRIGHT_YELLOW,
        "software_developer": Colors.BRIGHT_BLUE,
    }
    
    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors
    
    def colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if not self.use_colors:
            return text
        return f"{color}{text}{Colors.RESET}"
    
    def print_header(self, text: str, char: str = "═", width: int = 80) -> None:
        """Print a prominent header."""
        print(f"\n{self.colorize(char * width, Colors.BRIGHT_CYAN)}")
        centered = text.center(width)
        print(self.colorize(centered, Colors.BRIGHT_WHITE + Colors.BOLD))
        print(self.colorize(char * width, Colors.BRIGHT_CYAN))
    
    def print_section(self, title: str, width: int = 80) -> None:
        """Print a section divider."""
        print(f"\n{self.colorize('─' * width, Colors.BRIGHT_BLACK)}")
        print(self.colorize(f"  {title}", Colors.BRIGHT_YELLOW + Colors.BOLD))
        print(self.colorize('─' * width, Colors.BRIGHT_BLACK))
    
    def print_agent_step(self, step_num: int, agent: str, tool_calls: int, 
                         summary: str, max_summary_len: int = 600) -> None:
        """Print an agent execution step with formatting."""
        agent_color = self.AGENT_COLORS.get(agent, Colors.WHITE)
        
        # Step header
        header = f"  Step {step_num}: {agent}"
        tools_info = f"(🔧 {tool_calls} tools)" if tool_calls > 0 else "(⚠️  no tools used)"
        
        # Warn if agent should have tools but didn't use them
        if tool_calls == 0 and agent != "project_manager":
            tools_info = self.colorize(tools_info, Colors.YELLOW)
        
        print(f"\n{self.colorize(header, agent_color + Colors.BOLD)} {tools_info}")
        
        # Summary with truncation
        if len(summary) > max_summary_len:
            truncated = summary[:max_summary_len] + "..."
        else:
            truncated = summary
        
        # Format the summary with indentation
        lines = truncated.split('\n')
        for line in lines:
            if line.strip():
                # Highlight important markers
                formatted_line = self._highlight_content(line)
                print(f"  {formatted_line}")
    
    def _highlight_content(self, text: str) -> str:
        """Highlight important content in text."""
        # Highlight numbers with $ or %
        text = re.sub(r'\$[\d,]+\.?\d*', lambda m: self.colorize(m.group(), Colors.BRIGHT_GREEN), text)
        text = re.sub(r'-?\d+\.?\d*%', lambda m: self.colorize(m.group(), Colors.BRIGHT_CYAN), text)
        
        # Highlight risk indicators
        text = re.sub(r'\b(EXTREME|HIGH|CRITICAL|WARNING)\b', 
                     lambda m: self.colorize(m.group(), Colors.BRIGHT_RED + Colors.BOLD), 
                     text, flags=re.IGNORECASE)
        
        # Highlight positive indicators  
        text = re.sub(r'\b(SUCCESS|COMPLETE|POSITIVE)\b',
                     lambda m: self.colorize(m.group(), Colors.BRIGHT_GREEN + Colors.BOLD),
                     text, flags=re.IGNORECASE)
        
        # Highlight stock tickers (2-5 uppercase letters)
        text = re.sub(r'\b[A-Z]{2,5}\b',
                     lambda m: self.colorize(m.group(), Colors.BRIGHT_YELLOW),
                     text)
        
        return text
    
    def print_metric_table(self, metrics: dict[str, Any], title: str = "Key Metrics") -> None:
        """Print a formatted table of metrics."""
        if not metrics:
            return
        
        print(f"\n  {self.colorize(title, Colors.BRIGHT_CYAN + Colors.BOLD)}")
        print(f"  {self.colorize('┌' + '─' * 58 + '┐', Colors.BRIGHT_BLACK)}")
        
        for key, value in metrics.items():
            key_formatted = key.replace('_', ' ').title()
            value_str = str(value)
            
            # Color-code based on value type
            if isinstance(value, (int, float)):
                if value < 0:
                    value_colored = self.colorize(value_str, Colors.BRIGHT_RED)
                else:
                    value_colored = self.colorize(value_str, Colors.BRIGHT_GREEN)
            else:
                value_colored = self.colorize(value_str, Colors.WHITE)
            
            # Format as table row
            row = f"  │ {key_formatted:<30} {value_colored:>25} │"
            print(row)
        
        print(f"  {self.colorize('└' + '─' * 58 + '┘', Colors.BRIGHT_BLACK)}")
    
    def print_final_output(self, content: str) -> None:
        """Print the final output with enhanced formatting."""
        self.print_section("FINAL OUTPUT", width=80)
        
        # Try to parse as JSON for better formatting
        try:
            data = json.loads(content)
            # If it's a routing JSON to __end__, extract sub_task
            if data.get("next_agent") == "__end__" and data.get("sub_task"):
                self.print_final_synthesis(data["sub_task"])
            else:
                self._print_json_formatted(data)
        except (json.JSONDecodeError, TypeError):
            # Plain text - apply highlighting
            lines = content.split('\n')
            for line in lines:
                if line.strip().startswith('##'):
                    # Markdown H2
                    print(f"\n{self.colorize(line, Colors.BRIGHT_CYAN + Colors.BOLD)}")
                elif line.strip().startswith('#'):
                    # Markdown H1
                    print(f"\n{self.colorize(line, Colors.BRIGHT_MAGENTA + Colors.BOLD)}")
                elif line.strip().startswith('**') and line.strip().endswith('**'):
                    # Bold text
                    print(self.colorize(line, Colors.BRIGHT_YELLOW + Colors.BOLD))
                elif line.strip().startswith('-') or line.strip().startswith('*'):
                    # List items
                    highlighted = self._highlight_content(line)
                    print(highlighted)
                else:
                    highlighted = self._highlight_content(line)
                    print(highlighted)
    
    def print_final_synthesis(self, content: str) -> None:
        """Print the PM's final synthesis with special formatting."""
        lines = content.split('\n')
        for line in lines:
            if not line.strip():
                print()
                continue
            
            # Enhanced formatting for synthesis
            if any(keyword in line.upper() for keyword in ['BUY', 'SELL', 'HOLD', 'RECOMMENDATION']):
                print(f"  {self.colorize('▶', Colors.BRIGHT_CYAN)} {self.colorize(line, Colors.BRIGHT_WHITE + Colors.BOLD)}")
            elif line.strip().startswith('##'):
                print(f"\n{self.colorize(line, Colors.BRIGHT_MAGENTA + Colors.BOLD)}")
            elif line.strip().startswith('#'):
                print(f"\n{self.colorize(line, Colors.BRIGHT_CYAN + Colors.BOLD)}")
            elif line.strip().startswith('-') or line.strip().startswith('•'):
                highlighted = self._highlight_content(line)
                print(f"  {highlighted}")
            elif ':' in line and len(line) < 100:
                # Key-value pairs
                parts = line.split(':', 1)
                key = self.colorize(parts[0] + ':', Colors.BRIGHT_YELLOW + Colors.BOLD)
                value = self._highlight_content(parts[1])
                print(f"  {key}{value}")
            else:
                highlighted = self._highlight_content(line)
                print(f"  {highlighted}")
    
    def _print_json_formatted(self, data: dict) -> None:
        """Print JSON data with formatting."""
        for key, value in data.items():
            key_formatted = key.replace('_', ' ').title()
            print(f"\n  {self.colorize(key_formatted + ':', Colors.BRIGHT_YELLOW + Colors.BOLD)}")
            
            if isinstance(value, str):
                # Multi-line strings
                for line in value.split('\n'):
                    if line.strip():
                        highlighted = self._highlight_content(line)
                        print(f"    {highlighted}")
            else:
                print(f"    {self.colorize(str(value), Colors.WHITE)}")
    
    def print_summary(self, iteration: int, total_steps: int, status: str) -> None:
        """Print execution summary."""
        print(f"\n{self.colorize('─' * 80, Colors.BRIGHT_BLACK)}")
        
        status_color = Colors.BRIGHT_GREEN if status == "completed" else Colors.BRIGHT_YELLOW
        status_display = self.colorize(f"Status: {status.upper()}", status_color + Colors.BOLD)
        
        print(f"  {status_display}")
        print(f"  Total iterations: {self.colorize(str(iteration), Colors.BRIGHT_CYAN)}")
        print(f"  Agent steps: {self.colorize(str(total_steps), Colors.BRIGHT_CYAN)}")
        
        print(self.colorize('═' * 80, Colors.BRIGHT_CYAN))
    
    def print_tip(self, message: str) -> None:
        """Print a helpful tip."""
        icon = "💡"
        print(f"\n  {icon} {self.colorize('TIP:', Colors.BRIGHT_YELLOW + Colors.BOLD)} {message}")


def print_formatted_results(state: dict) -> None:
    """Enhanced version of print_results with colors and formatting."""
    formatter = ConsoleFormatter()
    
    formatter.print_header("CECIL AI – TASK COMPLETE")
    
    # Print agent contributions
    results = state.get("results", [])
    if results:
        formatter.print_section(f"Agent Collaboration Flow ({len(results)} steps)")
        
        for i, r in enumerate(results, 1):
            agent = r.get("agent", "unknown")
            summary = r.get("summary", "")
            tool_calls = r.get("tool_calls_made", 0)
            formatter.print_agent_step(i, agent, tool_calls, summary)
    
    # Extract final synthesis using same strategy as HTML report
    messages = state.get("messages", [])
    agent_outputs = state.get("agent_outputs", {})
    final_output = ""
    
    # Strategy 1: Look for PM's last output in agent_outputs (most reliable)
    if state.get("next_agent") == "__end__" and "project_manager" in agent_outputs:
        pm_output = agent_outputs["project_manager"]
        # Check if this is the final synthesis (not just routing JSON)
        if pm_output and not pm_output.strip().startswith("{"):
            final_output = pm_output
    
    # Strategy 2: Look in results for PM's final synthesis
    if not final_output:
        for result in reversed(results):
            if result.get("agent") == "project_manager":
                summary = result.get("summary", "")
                # Check if this looks like a synthesis (not routing JSON)
                if summary and "__end__" in summary and not summary.strip().startswith('{"next_agent"'):
                    final_output = summary
                    break
    
    # Strategy 3: Extract reasoning + sub_task from the final routing decision
    if not final_output:
        from langchain_core.messages import AIMessage
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                try:
                    import json
                    data = json.loads(content)
                    if data.get("next_agent") == "__end__":
                        # Combine reasoning and sub_task for a complete synthesis
                        reasoning = data.get("reasoning", "")
                        sub_task = data.get("sub_task", "")
                        if reasoning or sub_task:
                            final_output = f"{reasoning}\n\n{sub_task}" if reasoning and sub_task else (reasoning or sub_task)
                            break
                except (json.JSONDecodeError, TypeError, KeyError):
                    # Fallback to regular final output
                    final_output = content
                    break
    
    # Display final synthesis if we found it
    if final_output:
        formatter.print_section("🎯 FINAL SYNTHESIS", width=80)
        formatter.print_final_synthesis(final_output)
    
    # Print summary
    iterations = state.get("iteration", 0)
    status = state.get("status", "completed")
    formatter.print_summary(iterations, len(results), status)
    
    # Print helpful tips
    formatter.print_tip("Generate a PDF report with: python -m cecil.main \"your query\" --pdf")
    formatter.print_tip("Generate an HTML report with: python -m cecil.main \"your query\" --html")
    formatter.print_tip("Stream live updates with: python -m cecil.main \"your query\" --stream")
    print()
