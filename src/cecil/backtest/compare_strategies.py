#!/usr/bin/env python
"""Compare Cecil's agent picks vs quant strategy picks — RIGHT NOW.

This gives a fair instant comparison without look-ahead bias:
1. Run Cecil to get today's AI-powered recommendations
2. Run quant strategies to see what they'd pick today
3. Show both portfolios side-by-side

You can then track both forward to see who wins.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from cecil.graph.builder import compile_graph
from cecil.state.schema import AgentState
from langchain_core.messages import HumanMessage, AIMessage
from cecil.backtest.strategies import (
    momentum_score,
    value_score,
    composite_score,
)

import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from cecil.graph.builder import compile_graph
from cecil.state.schema import AgentState
from langchain_core.messages import HumanMessage, AIMessage

# Enable logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet noisy libraries
for lib in ("httpx", "httpcore", "urllib3", "openai", "yfinance"):
    logging.getLogger(lib).setLevel(logging.WARNING)


UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "AMD", "TSLA",
    "JPM", "GS", "V", "MA",
    "UNH", "JNJ", "LLY", "PFE",
    "WMT", "COST", "HD", "NKE",
    "XOM", "CVX", "CAT", "BA",
]


def get_current_prices(tickers: list[str]) -> dict[str, float]:
    """Fetch current prices for tickers."""
    data = yf.download(tickers, period="5d", progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        prices = data["Close"].iloc[-1]
    else:
        prices = data["Close"].iloc[-1]
    return {t: float(prices[t]) for t in tickers if not pd.isna(prices.get(t, float("nan")))}


def get_historical_prices(tickers: list[str], days: int = 90) -> pd.DataFrame:
    """Fetch historical prices for quant signal calculation."""
    end = datetime.now()
    start = end - timedelta(days=days + 30)  # extra buffer
    data = yf.download(tickers, start=start.strftime("%Y-%m-%d"), progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        return data["Close"].dropna()
    return data[["Close"]].dropna()


def parse_tickers_from_text(text: str, max_n: int = 6) -> list[str]:
    """Extract tickers from Cecil's recommendation."""
    import re
    from collections import Counter
    
    pattern = r'\b([A-Z]{2,5})\b'
    matches = re.findall(pattern, text)
    
    STOPWORDS = {"CEO", "AI", "US", "USA", "IPO", "SEC", "FDA", "ETF", "API", "LLM", "PM", "Q", "I", "IT", "OR", "AN", "AS", "AT", "BY", "DO", "GO", "IF", "IN", "IS", "NO", "OF", "ON", "SO", "TO", "UP", "WE", "FOR", "THE", "AND", "NOT", "BUT", "CAN", "HAS", "HAD", "MAY", "NOW", "OLD", "NEW", "OUR", "OUT", "OWN", "SAY", "SHE", "TOO", "USE", "WAY", "WHO", "BOY", "DID", "GET", "HIM", "HIS", "HOW", "MAN", "OUR", "PUT", "SHE", "TOO", "USE"}
    valid = [t for t in matches if t not in STOPWORDS and t in UNIVERSE]
    
    counted = Counter(valid)
    return [t for t, _ in counted.most_common(max_n)]


def run_cecil(cash: float = 1800) -> tuple[list[str], str]:
    """Run Cecil's agent system and return (tickers, full_recommendation)."""
    print("\n" + "=" * 70)
    print("  RUNNING CECIL AI AGENT SYSTEM")
    print("=" * 70)
    
    task = (
        f"I have ${cash:,.0f} to invest today ({datetime.now().strftime('%B %d, %Y')}). "
        f"Research the current market conditions and recommend 5-6 stocks for a diversified portfolio. "
        f"Consider stocks from: {', '.join(UNIVERSE[:12])}... and others. "
        f"Provide specific ticker symbols with brief reasoning for each pick."
    )
    
    print(f"\n  Task: {task[:80]}...")
    print(f"\n  Running agents with STREAMING output...\n")
    
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
        "max_iterations": 6,  # Reduced from 8 to avoid loops
        "status": "in_progress",
        "error": "",
    }
    
    t0 = time.time()
    
    # Use streaming to see progress
    final_state = None
    for i, step in enumerate(app.stream(initial_state, config={"recursion_limit": 20})):
        node_name = list(step.keys())[0]
        elapsed = time.time() - t0
        print(f"  [{elapsed:5.1f}s] Step {i+1}: {node_name}")
        final_state = step[node_name]
        
        # Show what agent produced
        if "agent_outputs" in final_state:
            latest = final_state.get("current_agent", "unknown")
            if latest in final_state["agent_outputs"]:
                output = final_state["agent_outputs"][latest]
                preview = output[:100].replace("\n", " ")
                print(f"          └─ {preview}...")
    
    elapsed = time.time() - t0
    result = final_state or {}
    
    # Extract final recommendation from messages
    recommendation = ""
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            recommendation = msg.content if isinstance(msg.content, str) else str(msg.content)
            break
    
    # Also check agent_outputs for PM's summary
    agent_outputs = result.get("agent_outputs", {})
    if "project_manager" in agent_outputs:
        recommendation = agent_outputs["project_manager"]
    
    tickers = parse_tickers_from_text(recommendation)
    
    print(f"\n  ✓ Cecil completed in {elapsed:.1f}s")
    print(f"  ✓ Picked {len(tickers)} stocks: {tickers}")
    
    return tickers, recommendation


def run_quant_strategies(prices: pd.DataFrame, top_n: int = 5) -> dict[str, list[str]]:
    """Run quant strategies and return their top picks."""
    results = {}
    
    # Momentum
    mom_scores = momentum_score(prices, lookback=60)
    results["Momentum (60d)"] = mom_scores.nsmallest(top_n).index.tolist()
    
    # Value (mean reversion)
    val_scores = value_score(prices, lookback=60)
    results["Value/Oversold"] = val_scores.nsmallest(top_n).index.tolist()
    
    # Composite
    comp_scores = composite_score(prices, 0.6, 0.4, 60)
    results["Composite (Mom+Val)"] = comp_scores.nsmallest(top_n).index.tolist()
    
    # Short-term momentum
    short_mom = momentum_score(prices, lookback=20)
    results["Short Momentum (20d)"] = short_mom.nsmallest(top_n).index.tolist()
    
    return results


def print_comparison(
    cecil_picks: list[str],
    quant_picks: dict[str, list[str]],
    current_prices: dict[str, float],
    recommendation: str,
):
    """Print side-by-side comparison."""
    print("\n" + "=" * 70)
    print("  STRATEGY COMPARISON — TODAY'S PICKS")
    print("=" * 70)
    
    # Cecil
    print("\n  📊 CECIL AI AGENTS")
    print("  " + "-" * 50)
    total = 0
    for t in cecil_picks:
        price = current_prices.get(t, 0)
        total += price
        print(f"    {t:<6} ${price:>8.2f}")
    print(f"  " + "-" * 50)
    print(f"    Equal-weight portfolio: ${1800/len(cecil_picks):.0f} per stock" if cecil_picks else "    No picks")
    
    # Quant strategies
    print("\n  📈 QUANT STRATEGIES")
    print("  " + "-" * 50)
    for name, picks in quant_picks.items():
        print(f"\n    {name}:")
        for t in picks:
            price = current_prices.get(t, 0)
            print(f"      {t:<6} ${price:>8.2f}")
    
    # Overlap analysis
    print("\n" + "=" * 70)
    print("  OVERLAP ANALYSIS")
    print("=" * 70)
    
    cecil_set = set(cecil_picks)
    for name, picks in quant_picks.items():
        overlap = cecil_set & set(picks)
        pct = len(overlap) / len(cecil_picks) * 100 if cecil_picks else 0
        print(f"  Cecil vs {name}: {len(overlap)}/{len(cecil_picks)} overlap ({pct:.0f}%)")
        if overlap:
            print(f"    Common: {list(overlap)}")
    
    # Cecil's reasoning
    print("\n" + "=" * 70)
    print("  CECIL'S REASONING")
    print("=" * 70)
    # Print first 1000 chars of recommendation
    if recommendation:
        lines = recommendation.split('\n')
        for line in lines[:30]:
            print(f"  {line}")
        if len(lines) > 30:
            print(f"  ... ({len(lines) - 30} more lines)")
    
    # Forward tracking instructions
    print("\n" + "=" * 70)
    print("  📅 FORWARD TRACKING")
    print("=" * 70)
    print(f"""
  Record these picks and check back in 7/30/90 days:
  
  Cecil picks: {cecil_picks}
  Composite quant: {quant_picks.get('Composite (Mom+Val)', [])}
  
  Compare:
  - Which portfolio returned more?
  - Which had lower drawdown?
  - Did Cecil's reasoning predict the moves?
  
  This is the ONLY unbiased way to evaluate AI vs quant!
""")


def main():
    print("\n" + "=" * 70)
    print("  CECIL AI vs QUANT STRATEGIES — LIVE COMPARISON")
    print("=" * 70)
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Universe: {len(UNIVERSE)} stocks")
    print("=" * 70)
    
    # Get current prices
    print("\n  Fetching current prices...")
    current_prices = get_current_prices(UNIVERSE)
    print(f"  ✓ Got prices for {len(current_prices)} stocks")
    
    # Get historical prices for quant signals
    print("  Fetching historical data for quant signals...")
    hist_prices = get_historical_prices(UNIVERSE)
    print(f"  ✓ Got {len(hist_prices)} days of history")
    
    # Run quant strategies (fast)
    print("\n  Running quant strategies...")
    quant_picks = run_quant_strategies(hist_prices)
    print(f"  ✓ Quant strategies complete")
    
    # Run Cecil (slow)
    cecil_picks, recommendation = run_cecil(cash=1800)
    
    # Print comparison
    print_comparison(cecil_picks, quant_picks, current_prices, recommendation)
    
    # Save to file for tracking
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"comparison_{timestamp}.txt"
    with open(filename, "w") as f:
        f.write(f"Date: {datetime.now().isoformat()}\n\n")
        f.write(f"Cecil picks: {cecil_picks}\n")
        f.write(f"Current prices: {current_prices}\n\n")
        for name, picks in quant_picks.items():
            f.write(f"{name}: {picks}\n")
        f.write(f"\n\nCecil recommendation:\n{recommendation}\n")
    print(f"\n  Saved to {filename} for future tracking\n")


if __name__ == "__main__":
    main()
