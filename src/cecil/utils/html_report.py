"""HTML report generator for Cecil AI agent analysis results.

Generates interactive HTML reports with:
- Collapsible sections for each agent step
- Syntax highlighting for code and data
- Responsive design for mobile/desktop
- Easy sharing and archiving
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CecilHTMLReport:
    """Generate interactive HTML reports from Cecil AI execution results."""

    def __init__(self, output_dir: str = "reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def generate_report(self, state: dict[str, Any], task: str) -> str:
        """Generate an HTML report from agent state.

        Parameters
        ----------
        state : dict
            Final agent state containing results, messages, etc.
        task : str
            Original user task/query

        Returns
        -------
        str
            Path to generated HTML file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_task = re.sub(r'[^\w\s-]', '', task)[:50].strip().replace(' ', '_')
        filename = f"cecil_report_{safe_task}_{timestamp}.html"
        filepath = self.output_dir / filename

        html_content = self._build_html(state, task, timestamp)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"HTML report generated: {filepath}")
        return str(filepath.absolute())

    def _build_html(self, state: dict[str, Any], task: str, timestamp: str) -> str:
        """Build complete HTML document."""
        results = state.get("results", [])
        messages = state.get("messages", [])
        iteration = state.get("iteration", 0)
        status = state.get("status", "completed")
        agent_outputs = state.get("agent_outputs", {})

        # Extract final output - look for PM's final synthesis when task is complete
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
                        pass

        # Build agent steps HTML
        agent_steps_html = self._build_agent_steps_html(results)

        # Format final output
        final_output_html = self._format_final_output(final_output)

        # Complete HTML template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cecil AI Report - {timestamp}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #e4e4e7;
            background: #0f0f14;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #1a1a24;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            overflow: hidden;
            border: 1px solid #2a2a3a;
        }}
        
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
        }}
        
        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .metadata {{
            opacity: 0.9;
            font-size: 0.95em;
        }}
        
        .metadata span {{
            display: inline-block;
            margin-right: 20px;
        }}
        
        .content {{
            padding: 40px;
        }}
        
        .section {{
            margin-bottom: 40px;
        }}
        
        .section-title {{
            font-size: 1.8em;
            color: #e4e4e7;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #818cf8;
        }}
        
        .task-box {{
            background: #252530;
            padding: 20px;
            border-left: 4px solid #818cf8;
            border-radius: 4px;
            margin-bottom: 30px;
            border: 1px solid #3a3a4a;
        }}
        
        .task-box h3 {{
            color: #818cf8;
            margin-bottom: 10px;
        }}
        
        .agent-step {{
            background: #1e1e28;
            margin-bottom: 20px;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #2a2a3a;
        }}
        
        .agent-header {{
            padding: 15px 20px;
            cursor: pointer;
            background: #252530;
            border-bottom: 1px solid #2a2a3a;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.3s;
        }}
        
        .agent-header:hover {{
            background: #2a2a35;
        }}
        
        .agent-name {{
            font-weight: 600;
            font-size: 1.1em;
        }}
        
        .agent-name.project_manager {{ color: #c084fc; }}
        .agent-name.quant_researcher {{ color: #60a5fa; }}
        .agent-name.portfolio_analyst {{ color: #34d399; }}
        .agent-name.research_intelligence {{ color: #fbbf24; }}
        .agent-name.software_developer {{ color: #f87171; }}
        
        .agent-meta {{
            color: #9ca3af;
            font-size: 0.9em;
        }}
        
        .agent-content {{
            padding: 20px;
            display: none;
            line-height: 1.8;
        }}
        
        .agent-content.expanded {{
            display: block;
        }}
        
        .expand-icon {{
            transition: transform 0.3s;
        }}
        
        .expand-icon.rotated {{
            transform: rotate(180deg);
        }}
        
        .final-output {{
            background: #1e1e28;
            padding: 30px;
            border-radius: 8px;
            border-left: 4px solid #34d399;
            border: 1px solid #2a2a3a;
        }}
        
        .final-synthesis {{
            background: linear-gradient(135deg, #1e1e28 0%, #2a2a35 100%);
            padding: 30px;
            border-radius: 8px;
            border-left: 5px solid #818cf8;
            line-height: 1.8;
            border: 1px solid #3a3a4a;
        }}
        
        .final-synthesis h2, .final-synthesis h3, .final-synthesis h4 {{
            color: #818cf8;
            margin-top: 20px;
            margin-bottom: 10px;
        }}
        
        .final-synthesis ul {{
            margin-left: 20px;
            margin-top: 10px;
            margin-bottom: 10px;
        }}
        
        .final-synthesis li {{
            margin: 8px 0;
        }}
        
        .final-synthesis strong {{
            color: #a78bfa;
            font-weight: 600;
        }}
        
        .metric {{
            display: inline-block;
            background: #252530;
            padding: 15px 25px;
            margin: 10px 10px 10px 0;
            border-radius: 6px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            border: 1px solid #3a3a4a;
        }}
        
        .metric-label {{
            color: #9ca3af;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .metric-value {{
            font-size: 1.8em;
            font-weight: 600;
            color: #e4e4e7;
            margin-top: 5px;
        }}
        
        .status {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 600;
        }}
        
        .status.completed {{
            background: #1e3a2e;
            color: #34d399;
        }}
        
        .ticker {{
            background: #2a2a35;
            padding: 2px 6px;
            border-radius: 3px;
            font-weight: 600;
            color: #fbbf24;
            border: 1px solid #3a3a4a;
        }}
        
        .negative {{
            color: #f87171;
            font-weight: 600;
        }}
        
        .positive {{
            color: #34d399;
            font-weight: 600;
        }}
        
        pre {{
            background: #2a2a35;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
            border: 1px solid #3a3a4a;
            color: #e4e4e7;
        }}
        
        code {{
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.9em;
            background: #2a2a35;
            color: #e4e4e7;
            padding: 2px 6px;
            border-radius: 3px;
            border: 1px solid #3a3a4a;
        }}
        
        footer {{
            background: #1a1a24;
            padding: 20px 40px;
            text-align: center;
            color: #9ca3af;
            border-top: 1px solid #2a2a3a;
        }}
        
        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}
            
            header {{
                padding: 20px;
            }}
            
            header h1 {{
                font-size: 1.8em;
            }}
            
            .content {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 Cecil AI Analysis Report</h1>
            <div class="metadata">
                <span>📅 Generated: {timestamp}</span>
                <span>🔄 Iterations: {iteration}</span>
                <span class="status {status}">{status.upper()}</span>
            </div>
        </header>
        
        <div class="content">
            <div class="section">
                <div class="task-box">
                    <h3>📋 Task</h3>
                    <p>{self._escape_html(task)}</p>
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">📊 Execution Summary</h2>
                <div>
                    <div class="metric">
                        <div class="metric-label">Agent Steps</div>
                        <div class="metric-value">{len(results)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Total Iterations</div>
                        <div class="metric-value">{iteration}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Status</div>
                        <div class="metric-value" style="font-size: 1.2em;">{status}</div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">🔄 Agent Collaboration Flow</h2>
                {agent_steps_html}
            </div>
            
            <div class="section">
                <h2 class="section-title">🎯 Final Synthesis & Recommendations</h2>
                <div class="final-output">
                    {final_output_html}
                </div>
            </div>
        </div>
        
        <footer>
            <p>Generated by Cecil AI - Multi-agent Financial Research System</p>
            <p style="margin-top: 5px; font-size: 0.9em;">Powered by LangGraph</p>
        </footer>
    </div>
    
    <script>
        // Toggle agent step expansion
        document.querySelectorAll('.agent-header').forEach(header => {{
            header.addEventListener('click', () => {{
                const content = header.nextElementSibling;
                const icon = header.querySelector('.expand-icon');
                
                content.classList.toggle('expanded');
                icon.classList.toggle('rotated');
            }});
        }});
        
        // Expand first step by default
        const firstStep = document.querySelector('.agent-content');
        const firstIcon = document.querySelector('.expand-icon');
        if (firstStep) {{
            firstStep.classList.add('expanded');
            firstIcon.classList.add('rotated');
        }}
    </script>
</body>
</html>"""
        return html

    def _build_agent_steps_html(self, results: list[dict]) -> str:
        """Build HTML for agent execution steps."""
        if not results:
            return "<p>No agent steps recorded.</p>"

        html_parts = []
        for i, result in enumerate(results, 1):
            agent = result.get("agent", "unknown")
            summary = result.get("summary", "")
            tool_calls = result.get("tool_calls_made", 0)

            # Highlight content
            summary_html = self._highlight_content(self._escape_html(summary))

            step_html = f"""
            <div class="agent-step">
                <div class="agent-header">
                    <div>
                        <span class="agent-name {agent}">Step {i}: {agent.replace('_', ' ').title()}</span>
                        <span class="agent-meta"> • {tool_calls} tool call{'s' if tool_calls != 1 else ''}</span>
                    </div>
                    <div class="expand-icon">▼</div>
                </div>
                <div class="agent-content">
                    {summary_html}
                </div>
            </div>"""
            html_parts.append(step_html)

        return "\n".join(html_parts)

    def _format_final_output(self, content: str) -> str:
        """Format the final output content."""
        if not content:
            return "<p>No final output available.</p>"

        # Try to parse as JSON (if PM didn't provide synthesis in sub_task)
        try:
            data = json.loads(content)
            # If it's a routing JSON to __end__, extract sub_task
            if data.get("next_agent") == "__end__" and data.get("sub_task"):
                content = data["sub_task"]
            else:
                # Otherwise format as structured JSON
                return self._format_json_output(data)
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Format as rich text
        html = self._escape_html(content)
        html = self._highlight_content(html)
        
        # Convert markdown-style formatting
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        
        # Convert markdown-style headers
        html = re.sub(r'^#### (.+)$', r'<h5>\1</h5>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        
        # Convert bullet points
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*?</li>)', r'<ul>\1</ul>', html, flags=re.DOTALL)
        
        # Convert numbered lists
        html = re.sub(r'^\d+\. (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        
        # Convert line breaks  
        html = html.replace('\n\n', '</p><p>')
        html = html.replace('\n', '<br>')
        
        return f'<div class="final-synthesis"><p>{html}</p></div>'

    def _format_json_output(self, data: dict) -> str:
        """Format JSON output as HTML."""
        html_parts = []
        for key, value in data.items():
            key_formatted = key.replace('_', ' ').title()
            html_parts.append(f'<h3 style="color: #667eea; margin-top: 20px;">{key_formatted}</h3>')

            if isinstance(value, str):
                value_html = self._escape_html(value)
                value_html = self._highlight_content(value_html)
                value_html = value_html.replace('\n', '<br>')
                html_parts.append(f'<p>{value_html}</p>')
            else:
                html_parts.append(f'<pre><code>{self._escape_html(str(value))}</code></pre>')

        return "\n".join(html_parts)

    def _highlight_content(self, text: str) -> str:
        """Highlight important content in HTML."""
        # Highlight stock tickers (2-5 uppercase letters)
        text = re.sub(r'\b([A-Z]{2,5})\b',
                     r'<span class="ticker">\1</span>',
                     text)

        # Highlight positive/negative percentages
        text = re.sub(r'(-\d+\.?\d*%)',
                     r'<span class="negative">\1</span>',
                     text)
        text = re.sub(r'(\+?\d+\.?\d*%)',
                     r'<span class="positive">\1</span>',
                     text)

        # Highlight dollar amounts
        text = re.sub(r'(\$[\d,]+\.?\d*)',
                     r'<strong style="color: #28a745;">\1</strong>',
                     text)

        return text

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
