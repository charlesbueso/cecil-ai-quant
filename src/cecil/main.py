"""Cecil AI – main entry point and example execution flows.

Run directly:
    python -m cecil.main

Or import and use programmatically:
    from cecil.main import run_task
    result = run_task("Analyse AAPL vs MSFT performance over the last 3 months")
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from cecil.config import get_settings
from cecil.graph.builder import compile_graph
from cecil.state.schema import AgentState
from cecil.utils.file_parser import format_file_context, parse_file
from cecil.utils.logger import ConversationLogger
from cecil.utils.console_formatter import print_formatted_results

load_dotenv()

# ── Logging setup ────────────────────────────────────────────────────

def _setup_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s │ %(name)-30s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    # Quieten noisy libraries
    for lib in ("httpx", "httpcore", "urllib3", "openai", "yfinance"):
        logging.getLogger(lib).setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


# ── Core execution ───────────────────────────────────────────────────

def run_task(
    task: str,
    *,
    max_iterations: int | None = None,
    stream: bool = False,
    generate_pdf: bool = False,
    generate_html: bool = False,
    file_paths: list[str] | None = None,
) -> dict:
    """Execute a multi-agent task end-to-end.

    Parameters
    ----------
    task:
        Natural-language description of what to accomplish.
    max_iterations:
        Override the default iteration cap.
    stream:
        If True, yield intermediate state dicts (for real-time UIs).
    generate_pdf:
        If True, generate a PDF report of the analysis.
    generate_html:
        If True, generate an HTML report of the analysis.

    Returns
    -------
    dict
        The final ``AgentState`` after the graph completes.
    """
    _setup_logging()
    settings = get_settings()

    logger.info("═" * 60)
    logger.info("  Cecil AI – starting task")
    logger.info("  Task: %s", task[:200])
    logger.info("═" * 60)
    
    # Parse files if provided
    file_context = ""
    if file_paths:
        try:
            file_contexts = []
            for file_path in file_paths:
                logger.info("  Parsing file: %s", file_path)
                file_info = parse_file(file_path)
                file_contexts.append(format_file_context(file_info))
                logger.info("  File parsed successfully: %s (%s)", file_info['name'], file_info['type'])
            file_context = "\n\n".join(file_contexts)
        except Exception as e:
            logger.error("Failed to parse file: %s", e)
            raise

    # Initialize conversation logger
    conv_logger = ConversationLogger()
    logger.info("  Conversation log: %s", conv_logger.get_log_path())
    
    app = compile_graph()

    initial_state: AgentState = {
        "messages": [HumanMessage(content=task)],
        "task": task,
        "current_agent": "project_manager",
        "next_agent": "project_manager",
        "sub_task": "",
        "context": {},
        "results": [],
        "agent_outputs": {},
        "iteration": 0,
        "max_iterations": max_iterations or settings.max_agent_iterations,
        "status": "in_progress",
        "error": "",
        "file_context": file_context,
    }

    if stream:
        final_state = None
        for step in app.stream(initial_state, {"recursion_limit": 50}):
            node_name = list(step.keys())[0]
            logger.info("▶ Completed node: %s", node_name)
            state_snapshot = step[node_name]
            conv_logger.log_state(state_snapshot, node_name)
            final_state = state_snapshot
        if final_state:
            conv_logger.log_final_summary(final_state)
    else:
        final_state = app.invoke(initial_state, {"recursion_limit": 50})
        
        # Log final state
        conv_logger.log_final_summary(final_state)
        logger.info("  Full conversation saved to: %s", conv_logger.get_log_path())
    
    # Generate PDF report if requested (works for both stream and non-stream)
    if generate_pdf and final_state:
        try:
            from cecil.utils.pdf_report import CecilPDFReport
            pdf_gen = CecilPDFReport()
            pdf_path = pdf_gen.generate_report(final_state, task)
            logger.info("  PDF report generated: %s", pdf_path)
            print(f"\n  📄 PDF Report: {pdf_path}")
        except Exception as e:
            logger.error(f"Failed to generate PDF report: {e}", exc_info=True)
            print(f"\n  ⚠️ PDF generation failed: {e}")
    
    # Generate HTML report if requested
    if generate_html and final_state:
        try:
            from cecil.utils.html_report import CecilHTMLReport
            html_gen = CecilHTMLReport()
            html_path = html_gen.generate_report(final_state, task)
            logger.info("  HTML report generated: %s", html_path)
            print(f"\n  🌐 HTML Report: {html_path}")
            
            # Auto-open HTML report in default browser
            try:
                os.startfile(html_path)
                logger.info("  Opened HTML report in default browser")
            except Exception as open_error:
                logger.warning(f"Could not auto-open HTML report: {open_error}")
        except Exception as e:
            logger.error(f"Failed to generate HTML report: {e}", exc_info=True)
            print(f"\n  ⚠️ HTML generation failed: {e}")
    
    return final_state or {}  # type: ignore[return-value]


def print_results(state: dict) -> None:
    """Pretty-print the final state for CLI usage."""
    print("\n" + "═" * 70)
    print("  CECIL AI – TASK COMPLETE")
    print("═" * 70)

    # Print agent contributions
    results = state.get("results", [])
    if results:
        print(f"\n  Agent contributions ({len(results)} steps):")
        for i, r in enumerate(results, 1):
            agent = r.get("agent", "unknown")
            summary = r.get("summary", "")
            tool_calls = r.get("tool_calls_made", 0)
            print(f"\n  ── Step {i}: {agent} (tools called: {tool_calls}) ──")
            # Print first 500 chars of summary
            if len(summary) > 500:
                print(f"  {summary[:500]}...")
            else:
                print(f"  {summary}")

    # Print final message
    messages = state.get("messages", [])
    if messages:
        from langchain_core.messages import AIMessage
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                print("\n" + "─" * 70)
                print("  FINAL OUTPUT:")
                print("─" * 70)
                print(content)
                break

    iterations = state.get("iteration", 0)
    print(f"\n  Total iterations: {iterations}")
    print("═" * 70 + "\n")


# ── Example tasks ────────────────────────────────────────────────────

EXAMPLE_TASKS = {
    "market_analysis": (
        "Perform a comprehensive analysis of the current technology sector. "
        "Get the latest prices for AAPL, MSFT, GOOGL, NVDA, and META. "
        "Compute their recent returns and volatility. "
        "Fetch recent market news about these companies. "
        "Provide a summary of which stocks look strongest and any risks."
    ),
    "portfolio_review": (
        "I have a portfolio with the following allocation: "
        "40% AAPL, 25% MSFT, 20% GOOGL, 15% AMZN. "
        "Analyse the portfolio's recent performance, compute risk metrics "
        "(volatility, Sharpe ratio, max drawdown), assess diversification, "
        "and suggest any rebalancing changes."
    ),
    "macro_research": (
        "Research the current macroeconomic environment. "
        "What are the latest trends in interest rates, inflation, and employment? "
        "Fetch recent financial news about Federal Reserve policy. "
        "How might the macro environment affect equity markets in the near term? "
        "Provide specific data points and a structured analysis."
    ),
    "quant_screen": (
        "Run a quantitative comparison of AAPL vs MSFT. "
        "Get 3 months of historical prices for both stocks. "
        "Compute returns, volatility, Sharpe ratio, "
        "correlation between the two, and moving averages. "
        "Write a Python script to visualise the comparison "
        "and present the results in a structured format."
    ),
}


# ── CLI entry point ──────────────────────────────────────────────────

def main() -> None:
    """Run an example task from the command line."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Cecil AI – Multi-agent financial research system",
    )
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="Task description (free text) or example name: "
        + ", ".join(EXAMPLE_TASKS.keys()),
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum agent iterations (default from config)",
    )
    parser.add_argument(
        "--list-examples",
        action="store_true",
        help="List available example tasks",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream intermediate results",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        default=False,
        help="Generate a PDF report of the analysis",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        default=True,
        help="Generate an HTML report of the analysis (enabled by default, use --no-html to disable)",
    )
    parser.add_argument(
        "--no-html",
        action="store_false",
        dest="html",
        help="Disable HTML report generation",
    )
    parser.add_argument(
        "--file",
        type=str,
        action="append",
        dest="files",
        default=None,
        help="Path to a file (PDF, TXT, CSV, etc.) to include as context. Can be used multiple times.",
    )
    args = parser.parse_args()

    if args.list_examples:
        print("\nAvailable example tasks:\n")
        for name, desc in EXAMPLE_TASKS.items():
            print(f"  {name}:")
            print(f"    {desc[:100]}...")
            print()
        return

    if args.task is None:
        # Default to the market analysis example
        task_text = EXAMPLE_TASKS["market_analysis"]
        print(f"No task specified – running default example: market_analysis\n")
    elif args.task in EXAMPLE_TASKS:
        task_text = EXAMPLE_TASKS[args.task]
    else:
        task_text = args.task

    result = run_task(
        task_text,
        max_iterations=args.max_iterations,
        stream=args.stream,
        generate_pdf=args.pdf,
        generate_html=args.html,
        file_paths=args.files,
    )
    print_formatted_results(result)


if __name__ == "__main__":
    main()
