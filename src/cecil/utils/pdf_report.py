"""PDF report generator for Cecil AI agent analysis results.

Generates professional PDF reports with:
- Executive summary
- Agent collaboration flow
- Data visualizations (price charts, metrics)
- Detailed findings from each specialist
- Final recommendations
"""

from __future__ import annotations

import io
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# matplotlib and reportlab are optional — only needed for local PDF generation.
# They are excluded from the Vercel production bundle to stay under size limits.
try:
    import matplotlib
    import matplotlib.pyplot as plt
    matplotlib.use('Agg')  # Non-interactive backend for server environments
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False

logger = logging.getLogger(__name__)


class CecilPDFReport:
    """Generate PDF reports from Cecil AI agent execution results."""

    def __init__(self, output_dir: str = "reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Create custom paragraph styles for the report."""
        self.styles.add(
            ParagraphStyle(
                name="CustomTitle",
                parent=self.styles["Title"],
                fontSize=24,
                textColor=colors.HexColor("#1a1a1a"),
                spaceAfter=30,
                alignment=1,  # Center
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading1"],
                fontSize=16,
                textColor=colors.HexColor("#2c3e50"),
                spaceAfter=12,
                spaceBefore=20,
                borderWidth=0,
                borderColor=colors.HexColor("#3498db"),
                borderPadding=5,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="AgentHeader",
                parent=self.styles["Heading2"],
                fontSize=13,
                textColor=colors.HexColor("#16a085"),
                spaceAfter=8,
                spaceBefore=12,
            )
        )

    def generate_report(self, state: dict[str, Any], task: str) -> str:
        """Generate a comprehensive PDF report from agent state.

        Parameters
        ----------
        state : dict
            Final agent state containing results, messages, etc.
        task : str
            Original user task/query

        Returns
        -------
        str
            Path to generated PDF file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create safe filename from task
        safe_task = re.sub(r'[^\w\s-]', '', task)[:50].strip().replace(' ', '_')
        filename = f"cecil_report_{safe_task}_{timestamp}.pdf"
        filepath = self.output_dir / filename

        # Build PDF
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=1 * inch,
            bottomMargin=0.75 * inch,
        )

        story = []

        # Title page
        story.extend(self._build_title_page(task, state))

        # Executive Summary
        story.extend(self._build_executive_summary(state))

        # Agent Collaboration Flow
        story.extend(self._build_collaboration_section(state))

        # Data Visualizations
        charts = self._build_visualizations(state)
        story.extend(charts)

        # Detailed Agent Findings
        story.extend(self._build_agent_findings(state))

        # Final Recommendation
        story.extend(self._build_final_recommendation(state))

        # Build PDF
        doc.build(story)
        logger.info(f"PDF report generated: {filepath}")

        return str(filepath.absolute())

    def _build_title_page(self, task: str, state: dict) -> list:
        """Create title page elements."""
        elements = []
        
        # Title
        elements.append(Paragraph("CECIL AI", self.styles["CustomTitle"]))
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(
            Paragraph("Multi-Agent Financial Research Report", self.styles["Heading2"])
        )
        elements.append(Spacer(1, 0.5 * inch))

        # Task box
        task_style = ParagraphStyle(
            name="TaskBox",
            parent=self.styles["Normal"],
            fontSize=12,
            textColor=colors.HexColor("#2c3e50"),
            backColor=colors.HexColor("#ecf0f1"),
            borderWidth=1,
            borderColor=colors.HexColor("#95a5a6"),
            borderPadding=10,
        )
        elements.append(Paragraph(f"<b>Research Query:</b><br/>{task}", task_style))
        elements.append(Spacer(1, 0.3 * inch))

        # Metadata table
        metadata = [
            ["Report Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["Iterations:", str(state.get("iteration", 0))],
            ["Agents Involved:", str(len(state.get("agent_outputs", {})))],
            ["Total Steps:", str(len(state.get("results", [])))],
        ]
        
        # Calculate total tool calls
        total_tools = sum(
            r.get("tool_calls_made", 0) for r in state.get("results", [])
        )
        metadata.append(["Tool Calls:", str(total_tools)])

        t = Table(metadata, colWidths=[2 * inch, 3 * inch])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#34495e")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.whitesmoke),
                ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#ecf0f1")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        elements.append(t)
        elements.append(PageBreak())

        return elements

    def _build_executive_summary(self, state: dict) -> list:
        """Build executive summary section."""
        elements = []
        elements.append(Paragraph("Executive Summary", self.styles["SectionHeader"]))

        # Extract key findings from agent outputs
        agent_outputs = state.get("agent_outputs", {})
        
        summary_text = []
        
        # Try to extract key numbers/findings
        for agent, output in agent_outputs.items():
            # Extract first meaningful sentence or key data point
            lines = output.split('\n')
            for line in lines[:10]:  # First 10 lines
                if any(kw in line.lower() for kw in ['price', 'return', 'risk', 'valuation']):
                    summary_text.append(f"• {line.strip()}")
                    break

        summary = "<br/>".join(summary_text[:8]) if summary_text else "Analysis complete. See detailed findings below."
        
        elements.append(Paragraph(summary, self.styles["Normal"]))
        elements.append(Spacer(1, 0.3 * inch))

        return elements

    def _build_collaboration_section(self, state: dict) -> list:
        """Build agent collaboration flow diagram."""
        elements = []
        elements.append(
            Paragraph("Agent Collaboration Flow", self.styles["SectionHeader"])
        )

        results = state.get("results", [])
        
        # Build flow table
        flow_data = [["Step", "Agent", "Tools Called", "Status"]]
        
        for i, result in enumerate(results, 1):
            agent = result.get("agent", "unknown")
            tools = result.get("tool_calls_made", 0)
            status = "✓ Complete" if tools > 0 or agent == "project_manager" else "⚠ No tools"
            
            flow_data.append([
                str(i),
                agent.replace('_', ' ').title(),
                str(tools),
                status,
            ])

        t = Table(flow_data, colWidths=[0.6 * inch, 2.5 * inch, 1.2 * inch, 1.5 * inch])
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3498db")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 11),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
            ])
        )
        elements.append(t)
        elements.append(Spacer(1, 0.3 * inch))

        return elements

    def _build_visualizations(self, state: dict) -> list:
        """Generate data visualizations from agent outputs."""
        elements = []
        elements.append(Paragraph("Data Analysis", self.styles["SectionHeader"]))

        # Try to extract price data for charts
        price_chart = self._create_price_chart(state)
        if price_chart:
            elements.append(price_chart)

        # Agent activity chart
        activity_chart = self._create_agent_activity_chart(state)
        if activity_chart:
            elements.append(activity_chart)

        return elements

    def _create_price_chart(self, state: dict) -> Any | None:
        """Create stock price chart if price data exists in results."""
        try:
            # Search for historical price data in agent outputs
            agent_outputs = state.get("agent_outputs", {})
            
            for agent, output in agent_outputs.items():
                # Look for price patterns in text
                if "historical_prices" in output.lower() or "3-month" in output.lower():
                    # Try to extract data - this is a simplified version
                    # In production, you'd parse structured data
                    return None  # Skip for now if no structured data
            
            return None
        except Exception as e:
            logger.warning(f"Failed to create price chart: {e}")
            return None

    def _create_agent_activity_chart(self, state: dict) -> Any:
        """Create bar chart showing agent tool usage."""
        try:
            results = state.get("results", [])
            
            # Aggregate tool calls by agent
            agent_tools = {}
            for result in results:
                agent = result.get("agent", "unknown")
                tools = result.get("tool_calls_made", 0)
                agent_tools[agent] = agent_tools.get(agent, 0) + tools

            if not agent_tools or all(v == 0 for v in agent_tools.values()):
                return Spacer(1, 0.1 * inch)

            # Create chart
            fig, ax = plt.subplots(figsize=(6, 3))
            agents = [a.replace('_', ' ').title() for a in agent_tools.keys()]
            counts = list(agent_tools.values())
            
            bars = ax.bar(agents, counts, color='#3498db', alpha=0.8)
            ax.set_ylabel('Tool Calls', fontsize=10)
            ax.set_title('Agent Tool Usage', fontsize=12, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            
            # Rotate labels if needed
            plt.xticks(rotation=45, ha='right', fontsize=9)
            plt.tight_layout()

            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)

            # Import Image from reportlab
            from reportlab.platypus import Image
            img = Image(buf, width=5.5 * inch, height=2.75 * inch)
            
            return img

        except Exception as e:
            logger.warning(f"Failed to create activity chart: {e}")
            return Spacer(1, 0.1 * inch)

    def _build_agent_findings(self, state: dict) -> list:
        """Build detailed findings from each specialist agent."""
        elements = []
        elements.append(PageBreak())
        elements.append(
            Paragraph("Detailed Agent Findings", self.styles["SectionHeader"])
        )

        agent_outputs = state.get("agent_outputs", {})
        
        for agent, output in agent_outputs.items():
            if agent == "project_manager":
                continue  # Skip PM, show specialist findings only
            
            agent_name = agent.replace('_', ' ').title()
            elements.append(Paragraph(agent_name, self.styles["AgentHeader"]))
            
            # Clean and format output
            formatted_output = self._format_agent_output(output)
            elements.append(Paragraph(formatted_output, self.styles["Normal"]))
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _format_agent_output(self, output: str) -> str:
        """Clean and format agent output for PDF."""
        # Truncate if too long
        if len(output) > 2500:
            output = output[:2500] + "...\n\n[Output truncated for brevity]"
        
        # Escape HTML chars
        output = output.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Convert markdown-style bold
        output = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', output)
        
        # Convert newlines to breaks
        output = output.replace('\n', '<br/>')
        
        return output

    def _build_final_recommendation(self, state: dict) -> list:
        """Build final recommendation section."""
        elements = []
        elements.append(PageBreak())
        elements.append(
            Paragraph("Final Synthesis & Recommendation", self.styles["SectionHeader"])
        )

        # Get PM's final synthesis
        results = state.get("results", [])
        final_pm_text = ""
        
        for result in reversed(results):
            if result.get("agent") == "project_manager":
                summary = result.get("summary", "")
                # Look for synthesis in the sub_task field (that's where PM puts conclusion)
                if "synthesize" in summary.lower() or "__end__" in summary:
                    final_pm_text = summary
                    break

        if not final_pm_text and results:
            # Fallback to last result
            final_pm_text = results[-1].get("summary", "Analysis complete.")

        formatted = self._format_agent_output(final_pm_text)
        elements.append(Paragraph(formatted, self.styles["Normal"]))
        elements.append(Spacer(1, 0.3 * inch))

        # Footer
        footer_style = ParagraphStyle(
            name="Footer",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=colors.grey,
            alignment=1,  # Center
        )
        elements.append(Spacer(1, 0.5 * inch))
        elements.append(
            Paragraph(
                f"Generated by Cecil AI on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}",
                footer_style,
            )
        )

        return elements
