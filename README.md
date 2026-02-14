<p align="center">
  <img src="assets/cecilia-y-demas.jpg" alt="Cecil AI" width="600">
</p>

# Cecil AI — Multi-Agent Financial Research System

Multi-agent system built with **LangGraph** that orchestrates AI agents for financial research, portfolio analysis, and quantitative reasoning.

## Quick Setup

```bash
# 1. Clone & install
cd cecil-ai
pip install -e .

# 2. Configure (add at least one LLM API key)
cp .env.example .env
```

**.env** minimum config:
```env
FIREWORKS_API_KEY=your_key_here

# All agents use Fireworks (fast, cheap):
QUANT_RESEARCHER_PROVIDER=fireworks
PORTFOLIO_ANALYST_PROVIDER=fireworks
SOFTWARE_DEVELOPER_PROVIDER=fireworks
PROJECT_MANAGER_PROVIDER=fireworks
RESEARCH_INTELLIGENCE_PROVIDER=fireworks
```

```bash
# 3. Run
python -m cecil.main "Analyse AAPL"
```

## Architecture

**Cecil AI enforces deep, multi-perspective analysis.** The Project Manager is configured to:
- Require **minimum 3 specialist agents** for investment decisions
- Never conclude after just 1-2 responses
- Demand specific metrics and data points
- Surface both bullish and bearish perspectives
- Push for thorough quantitative and qualitative analysis

```
User Task
    │
    ▼
┌──────────────────┐
│  Project Manager  │ ◄── orchestrates all routing
└────────┬─────────┘
         │ routes to best agent
    ┌────┼────┬──────────┬───────────┐
    ▼    ▼    ▼          ▼           ▼
  Quant  Portfolio  Software   Research
  Rschr  Analyst   Developer  Intelligence
    │    │         │          │
    └────┴─────────┴──────────┘
         │
         ▼ results back to PM
    ┌──────────────────┐
    │  Project Manager  │ → decides next step or END
    └──────────────────┘
```

### Agents

| Agent | Role | Tools |
|-------|------|-------|
| **Project Manager** | Routes tasks, synthesises results | None (routing via state) |
| **Quant Researcher** | Statistical analysis, market data | Financial data, computation |
| **Portfolio Analyst** | Risk metrics, allocation advice | Financial data, computation |
| **Software Developer** | Code generation & execution | Code sandbox, computation |
| **Research Intelligence** | News, macro data, sentiment | News feeds, financial data |

### LLM Providers

All models are accessed via OpenAI-compatible APIs. Supported providers:
- **Groq** (fast inference, free tier)
- **Together AI**
- **Fireworks AI** (auto-detects available models at runtime)
- **OpenRouter**

**Fireworks AI Dynamic Loading**: Cecil automatically detects which models are available in your Fireworks account at runtime, ensuring you never get 404 errors from deprecated models.

## Quick Start

```bash
# Run default example
python -m cecil.main

# Custom task
python -m cecil.main "Analyse NVDA's recent price action"

# More iterations for deeper analysis
python -m cecil.main "Is TSLA a good buy?" --max-iterations 15

# Generate PDF report
python -m cecil.main market_analysis --pdf

# Analyze a PDF or text file
python -m cecil.main "Summarize the key findings from this report" --file ./earnings_report.pdf

# List examples
python -m cecil.main --list-examples
```

### File Input Support

Cecil can analyze PDF, text, and code files as context for tasks:

```bash
# Analyze a PDF earnings report
python -m cecil.main "What are the key investment opportunities in this report?" --file quarterly_earnings.pdf

# Review code files
python -m cecil.main "Identify bugs and suggest improvements" --file myapp.py

# Analyze multiple files (e.g., portfolio CSVs)
python -m cecil.main "Analyze my portfolio and recommend trades for next 2 weeks" \
  --file assets/Portfolio_Positions.csv \
  --file assets/Transaction_History.csv \
  --max-iterations 15

# With report generation
python -m cecil.main "Summarize this research paper" --file research.pdf --html
```

**Supported formats:** `.pdf`, `.txt`, `.md`, `.log`, `.json`, `.csv`, `.yaml`, `.py`, `.js`, `.ts`, `.java`, `.cpp`, `.c`, `.h`

The file content is automatically parsed and provided to all agents as context. Use `--file` multiple times to include multiple files.

Logs auto-saved to `logs/conversation_YYYYMMDD_HHMMSS.txt`

## Backtesting: Cecil vs Quant Strategies

Compare AI agent picks against quant strategies **in real-time** (no look-ahead bias):

```bash
python compare_strategies.py
```

**What it does:**
1. Fetches current prices for 24-stock universe
2. Runs Cecil's full agent workflow → AI-powered picks
3. Runs momentum/value/composite quant strategies
4. Prints side-by-side comparison with overlap analysis
5. Saves to `comparison_YYYYMMDD_HHMMSS.txt` for forward tracking

**Stock Universe:** AAPL, MSFT, NVDA, GOOGL, META, AMZN, AMD, TSLA, JPM, GS, V, MA, UNH, JNJ, LLY, PFE, WMT, COST, HD, NKE, XOM, CVX, CAT, BA

You can also run pure quant backtests (fast, no LLM):
```bash
python run_backtest.py --period 1y --cash 1800
```

## Project Structure

```
src/cecil/
├── main.py              # Entry point - run_task()
├── config.py            # Settings from .env
├── models/
│   ├── client.py        # LLM client factory
│   └── providers.py     # Provider configs (add new providers here)
├── agents/              # One file per agent
│   ├── base.py          # Base agent with tool-call loop
│   ├── project_manager.py
│   ├── quant_researcher.py
│   ├── portfolio_analyst.py
│   ├── software_developer.py
│   └── research_intelligence.py
├── tools/               # @tool decorated functions
│   ├── financial.py     # get_stock_price, get_historical_prices
│   ├── news.py          # fetch_financial_news, RSS feeds
│   └── computation.py   # compute_returns, portfolio metrics
├── graph/
│   ├── builder.py       # StateGraph construction
│   ├── nodes.py         # Node functions calling agents
│   └── routing.py       # PM routing logic
└── backtest/
    ├── engine.py        # Portfolio tracking, trade execution
    ├── strategies.py    # Momentum, value, mean-reversion
    └── visualize.py     # Charts & PDF reports

compare_strategies.py    # Cecil vs Quant comparison (root)
run_backtest.py          # Pure quant backtester (root)
```

## Programmatic Usage

```python
from cecil.main import run_task

result = run_task("Compare AAPL and MSFT", max_iterations=8)
for r in result["results"]:
    print(f"{r['agent']}: {r['summary'][:200]}")
```

## Extending

**New Agent:** Create in `agents/`, add role to `state/schema.py`, register in `graph/builder.py`

**New Tool:** Add `@tool` function in `tools/`, include in agent's `tools` list

**New Provider:** Add `ProviderConfig` in `models/providers.py`, add key to `config.py`

## Supported Providers

| Provider | Speed | Cost | Model |
|----------|-------|------|-------|
| Fireworks | Fast | $$ | deepseek-v3 |
| Groq | Very Fast | Free tier | llama-3.3-70b |
| Together | Medium | $ | llama-3.3-70b |
| OpenRouter | Varies | Varies | Any model |
