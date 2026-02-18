"""Quick health check for all configured API keys.

Run:  python scripts/test_api_keys.py
"""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

PASS = "✅"
FAIL = "❌"
SKIP = "⬚ "
TIMEOUT = 10


def _header(title: str):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


# ── LLM Providers ───────────────────────────────────────────────────

def test_groq():
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        return SKIP, "no key set"
    try:
        r = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            models = [m["id"] for m in r.json().get("data", [])[:5]]
            return PASS, f"{len(r.json()['data'])} models  (e.g. {', '.join(models)})"
        return FAIL, f"HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return FAIL, str(e)[:120]


def test_fireworks():
    key = os.getenv("FIREWORKS_API_KEY", "")
    if not key:
        return SKIP, "no key set"
    try:
        r = httpx.get(
            "https://api.fireworks.ai/inference/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            return PASS, f"{len(data)} models available"
        return FAIL, f"HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return FAIL, str(e)[:120]


def test_together():
    key = os.getenv("TOGETHER_API_KEY", "")
    if not key:
        return SKIP, "no key set"
    try:
        r = httpx.get(
            "https://api.together.xyz/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return PASS, f"{len(r.json())} models available"
        return FAIL, f"HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return FAIL, str(e)[:120]


def test_openrouter():
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        return SKIP, "no key set"
    try:
        r = httpx.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            return PASS, f"{len(data)} models available"
        return FAIL, f"HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return FAIL, str(e)[:120]


# ── Data Providers ───────────────────────────────────────────────────

def test_fred():
    key = os.getenv("FRED_API_KEY", "")
    if not key:
        return SKIP, "no key set"
    try:
        r = httpx.get(
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id=DGS10&api_key={key}&file_type=json&limit=1",
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            obs = r.json().get("observations", [])
            val = obs[0]["value"] if obs else "?"
            return PASS, f"10Y Treasury = {val}%"
        return FAIL, f"HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return FAIL, str(e)[:120]


def test_alpha_vantage():
    key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    if not key:
        return SKIP, "no key set"
    try:
        r = httpx.get(
            f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey={key}",
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            if "Global Quote" in data and data["Global Quote"]:
                price = data["Global Quote"].get("05. price", "?")
                return PASS, f"AAPL = ${price}"
            if "Note" in data or "Information" in data:
                return FAIL, "rate limited (free tier: 25 req/day)"
            return FAIL, f"unexpected response: {str(data)[:100]}"
        return FAIL, f"HTTP {r.status_code}"
    except Exception as e:
        return FAIL, str(e)[:120]


def test_finnhub():
    key = os.getenv("FINNHUB_API_KEY", "")
    if not key:
        return SKIP, "no key set"
    try:
        r = httpx.get(
            f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={key}",
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("c"):
                return PASS, f"AAPL = ${data['c']}"
            if data.get("error"):
                return FAIL, data["error"]
            return FAIL, f"empty response: {data}"
        if r.status_code == 401:
            return FAIL, "invalid API key"
        return FAIL, f"HTTP {r.status_code}"
    except Exception as e:
        return FAIL, str(e)[:120]


def test_fmp():
    key = os.getenv("FMP_API_KEY", "")
    if not key:
        return SKIP, "no key set"
    try:
        r = httpx.get(
            f"https://financialmodelingprep.com/stable/profile?symbol=AAPL&apikey={key}",
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                return PASS, f"AAPL = ${data[0].get('price', '?')}"
            if isinstance(data, dict) and "Error Message" in data:
                return FAIL, data["Error Message"][:100]
            return PASS, "connected"
        if r.status_code == 401:
            return FAIL, "invalid API key"
        return FAIL, f"HTTP {r.status_code}"
    except Exception as e:
        return FAIL, str(e)[:120]


def test_newsapi():
    key = os.getenv("NEWS_API_KEY", "")
    if not key:
        return SKIP, "no key set"
    try:
        r = httpx.get(
            f"https://newsapi.org/v2/top-headlines?country=us&category=business&pageSize=1&apiKey={key}",
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            total = data.get("totalResults", 0)
            return PASS, f"{total} headlines available"
        if r.status_code == 401:
            return FAIL, "invalid API key"
        if r.status_code == 426:
            return FAIL, "free tier blocked (localhost only)"
        return FAIL, f"HTTP {r.status_code}: {r.text[:100]}"
    except Exception as e:
        return FAIL, str(e)[:120]


# ── Run all ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n🔑  Cecil AI — API Key Health Check\n")

    _header("LLM Providers")
    for name, fn in [
        ("Groq", test_groq),
        ("Fireworks AI", test_fireworks),
        ("Together AI", test_together),
        ("OpenRouter", test_openrouter),
    ]:
        status, detail = fn()
        print(f"  {status}  {name:<16} {detail}")

    _header("Data Providers")
    for name, fn in [
        ("FRED", test_fred),
        ("Alpha Vantage", test_alpha_vantage),
        ("Finnhub", test_finnhub),
        ("FMP", test_fmp),
        ("NewsAPI", test_newsapi),
    ]:
        status, detail = fn()
        print(f"  {status}  {name:<16} {detail}")

    print(f"\n{'─' * 50}")
    print(f"  {PASS} = active    {FAIL} = error    {SKIP} = no key")
    print(f"{'─' * 50}\n")
