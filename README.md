<p align="center">
  <img src="assets/cecilia-y-demas.jpg" alt="Cecil AI" width="600">
</p>

# Cecil AI

Multi-agent financial research system powered by **LangGraph** + **Next.js** + **FastAPI**, deployable as a Vercel serverless app.

Cecil orchestrates specialist AI agents -- quantitative research, portfolio analysis, market intelligence -- to produce deep, multi-perspective financial analysis with real-time streaming and HTML report generation.

---

## Architecture

```
+-----------------------------------------------------------+
|                     Vercel Platform                        |
|  /api/*  -> Python Serverless (FastAPI)                    |
|  /*      -> Next.js Frontend (React 19)                    |
+-----------------------------------------------------------+
         |                          |
    FastAPI Backend            Next.js Frontend
    +----------+              +--------------+
    | SSE      | <----------> | Chat UI      |
    | Streaming|   auth via   | Supabase Auth|
    | REST API |   JWT        | Agent Viz    |
    +----+-----+              +--------------+
         |
    LangGraph Agent Orchestration
    +----+-------------------------------------+
    |         Project Manager                  |
    |    (routes tasks, synthesises)            |
    +------+----------+--------------+---------+
    | Quant| Portfolio |  Research    | Software|
    | Rschr| Analyst   |  Intelligence| Dev    |
    +------+----------+--------------+---------+
```

### Agents

| Agent | Role | Capabilities |
|---|---|---|
| **Project Manager** | Orchestrator | Routes tasks to specialists, synthesises multi-agent results |
| **Quant Researcher** | Quantitative analysis | Stock data, factor computation, statistical metrics |
| **Portfolio Analyst** | Portfolio construction | Risk metrics, allocation advice, rebalancing |
| **Research Intelligence** | Market context | Financial news, macro data, economic indicators |
| **Software Developer** | Code execution | Code generation, computation, data processing |

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS 4, TypeScript |
| Backend API | FastAPI (Python 3.11+), SSE streaming |
| Agent Framework | LangGraph, LangChain |
| Auth & DB | Supabase (Auth, PostgreSQL, Storage) |
| LLM Providers | Groq, Fireworks AI, Together AI, OpenRouter |
| Data Sources | yfinance, FRED, FMP, Finnhub, Alpha Vantage, NewsAPI |
| Deployment | Vercel (serverless Python + Next.js) |

---

## Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com) project (free tier works)
- At least one LLM provider API key

### 1. Install

```bash
git clone https://github.com/your-org/cecil-ai.git
cd cecil-ai

# Python backend
pip install -e .

# Next.js frontend
cd frontend && npm install && cd ..
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your keys
```

Required environment variables:

```env
# Supabase (Dashboard -> Settings -> API)
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# LLM Provider (at least one)
GROQ_API_KEY=your-key
# or: FIREWORKS_API_KEY, TOGETHER_API_KEY, OPENROUTER_API_KEY

# Agent -> provider mapping
QUANT_RESEARCHER_PROVIDER=groq
PORTFOLIO_ANALYST_PROVIDER=groq
SOFTWARE_DEVELOPER_PROVIDER=groq
PROJECT_MANAGER_PROVIDER=groq
RESEARCH_INTELLIGENCE_PROVIDER=groq
```

Optional data API keys (enhance analysis quality):

```env
FRED_API_KEY=           # Federal Reserve economic data
FMP_API_KEY=            # Financial Modeling Prep
FINNHUB_API_KEY=        # Finnhub market data
ALPHA_VANTAGE_API_KEY=  # Alpha Vantage stock data
NEWS_API_KEY=           # NewsAPI headlines
```

### 3. Run (local)

```bash
# Terminal 1: FastAPI backend
uvicorn api.index:app --reload

# Terminal 2: Next.js frontend
cd frontend && npm run dev
```

Open http://localhost:3000. The frontend proxies `/api/*` to the FastAPI backend at `localhost:8000`.

### CLI Mode

Cecil also runs standalone from the command line without the web UI:

```bash
python -m cecil.main "Analyse AAPL's recent price action"
python -m cecil.main "Compare NVDA and AMD" --max-iterations 15
python -m cecil.main "Portfolio review" --file assets/positions.csv --html
```

---

## Deploy to Vercel

### 1. Install Vercel CLI

```bash
npm i -g vercel
```

### 2. Link and Deploy

```bash
vercel          # First-time: links project, follow prompts
# or
vercel --prod   # Production deployment
```

### 3. Set Environment Variables

In Vercel Dashboard -> Project -> Settings -> Environment Variables, add all keys from `.env.example`.

Key variables:

| Variable | Required | Notes |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase anon/public key |
| `SUPABASE_URL` | Yes | Same as above (for Python backend) |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `GROQ_API_KEY` | Yes* | At least one LLM provider key |
| `FIREWORKS_API_KEY` | Optional | Fireworks AI key |
| `*_PROVIDER` vars | Optional | Agent-to-provider mapping (defaults to groq) |
| Data API keys | Optional | FRED, FMP, Finnhub, Alpha Vantage, NewsAPI |

> **Note:** Vercel Hobby plan limits serverless functions to 60s. Complex multi-agent analysis may need the Pro plan (300s max duration).

### How It Works on Vercel

- `vercel.json` defines two builds: `@vercel/next` (frontend) + `@vercel/python` (API)
- Routes: `/api/*` -> Python serverless function, `/*` -> Next.js
- Python deps auto-install from `requirements.txt`
- `src/cecil/` is added to `sys.path` at runtime for package imports

---

## Supabase Setup

Run the migrations in `supabase/` against your project:

1. **Tables**: `conversations`, `messages` (see `supabase/migration.sql`)
2. **Storage**: `chat-attachments` bucket (see `supabase/002_chat_attachments_storage.sql`)
3. **Auth**: Enable Email/Password sign-up in Supabase Dashboard -> Authentication

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/health` | No | Health check + provider status |
| `GET` | `/api/examples` | No | Preset example tasks |
| `GET` | `/api/agents` | No | Available agent info |
| `POST` | `/api/task` | Yes | Submit task (sync response) |
| `POST` | `/api/task/stream` | Yes | Submit task (SSE streaming) |
| `POST` | `/api/upload` | Yes | Upload file for analysis context |
| `DELETE` | `/api/upload/{id}` | Yes | Delete uploaded file |
| `GET` | `/api/reports` | No | List generated reports |
| `GET` | `/api/reports/{file}` | No | View HTML report |
| `GET` | `/api/conversations` | Yes | List user conversations |
| `POST` | `/api/conversations` | Yes | Create conversation |
| `GET` | `/api/conversations/{id}/messages` | Yes | Get messages |
| `POST` | `/api/conversations/{id}/messages` | Yes | Add message |
| `DELETE` | `/api/conversations/{id}` | Yes | Delete conversation |

---

## Project Structure

```
cecil-ai/
+-- api/
|   +-- index.py                 # FastAPI app (Vercel serverless entry)
+-- frontend/
|   +-- src/
|   |   +-- app/                 # Next.js App Router pages
|   |   |   +-- chat/            # Main chat interface
|   |   |   +-- login/           # Auth page
|   |   |   +-- reports/         # Report viewer
|   |   |   +-- settings/        # Settings page
|   |   +-- components/          # React components
|   |   +-- contexts/            # Auth context (Supabase)
|   |   +-- lib/                 # API client, Supabase helpers
|   +-- package.json
|   +-- next.config.ts
+-- src/cecil/                   # Core agent framework
|   +-- main.py                  # Entry point, run_task()
|   +-- config.py                # Settings from env
|   +-- agents/                  # Agent implementations
|   |   +-- base.py              # Base agent with tool-call loop
|   |   +-- project_manager.py   # Orchestrator agent
|   |   +-- quant_researcher.py
|   |   +-- portfolio_analyst.py
|   |   +-- research_intelligence.py
|   |   +-- software_developer.py
|   +-- graph/                   # LangGraph orchestration
|   |   +-- builder.py           # StateGraph construction
|   |   +-- nodes.py             # Node functions
|   |   +-- routing.py           # PM routing logic
|   +-- models/                  # LLM client factory + providers
|   +-- tools/                   # @tool functions
|   |   +-- financial.py         # Stock prices, historical data
|   |   +-- computation.py       # Returns, portfolio metrics
|   |   +-- factors.py           # Factor analysis
|   |   +-- news.py              # RSS feeds, news API
|   +-- state/                   # AgentState schema
|   +-- utils/                   # Report gen, file parsing, logging
+-- supabase/                    # Database migrations
+-- vercel.json                  # Vercel deployment config
+-- requirements.txt             # Python deps (used by Vercel)
+-- pyproject.toml               # Python project metadata
+-- .env.example                 # Environment variable template
```

---

## Supported LLM Providers

| Provider | Speed | Notes |
|---|---|---|
| **Groq** | Very fast | Free tier available, good for development |
| **Fireworks AI** | Fast | Auto-detects available models at runtime |
| **Together AI** | Medium | Wide model selection |
| **OpenRouter** | Varies | Access to any model via unified API |

All providers are accessed via OpenAI-compatible APIs. Set `{AGENT_ROLE}_PROVIDER` to route each agent to a specific provider.

---

## License

Private -- All rights reserved.
