"""News and macro-data fetching tools.

Uses free RSS feeds and public APIs to pull financial news, macro
indicators, and structured market context.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import feedparser
import httpx
from langchain_core.tools import tool

from cecil.config import get_settings

logger = logging.getLogger(__name__)

# ── RSS feed sources ─────────────────────────────────────────────────

_RSS_FEEDS: dict[str, str] = {
    "reuters_markets": "https://news.google.com/rss/search?q=reuters+markets&hl=en-US&gl=US&ceid=US:en",
    "bloomberg_markets": "https://news.google.com/rss/search?q=bloomberg+markets&hl=en-US&gl=US&ceid=US:en",
    "yahoo_finance": "https://news.google.com/rss/search?q=yahoo+finance+markets&hl=en-US&gl=US&ceid=US:en",
    "macro_economy": "https://news.google.com/rss/search?q=macroeconomy+federal+reserve&hl=en-US&gl=US&ceid=US:en",
}


@tool
def fetch_financial_news(
    query: str = "stock market",
    max_articles: int = 8,
) -> str:
    """Fetch recent financial news articles via Google News RSS.

    Args:
        query: Search query for news (e.g. "AAPL earnings", "Fed interest rates").
        max_articles: Maximum number of articles to return (default 8, max 15).

    Returns:
        JSON list of article summaries with title, link, published date, source.
    """
    max_articles = min(max_articles, 15)
    url = (
        f"https://news.google.com/rss/search?"
        f"q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
    )
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:max_articles]:
            articles.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": entry.get("source", {}).get("title", "Unknown"),
            })
        return json.dumps({
            "query": query,
            "count": len(articles),
            "articles": articles,
            "fetched_at": datetime.now().isoformat(),
        })
    except Exception as exc:
        logger.exception("fetch_financial_news failed")
        return json.dumps({"error": str(exc)})


@tool
def fetch_market_news_by_category(category: str = "markets") -> str:
    """Fetch news from predefined financial RSS categories.

    Args:
        category: One of "reuters_markets", "bloomberg_markets",
                  "yahoo_finance", "macro_economy".

    Returns:
        JSON list of article summaries.
    """
    feed_url = _RSS_FEEDS.get(category)
    if not feed_url:
        return json.dumps({
            "error": f"Unknown category '{category}'",
            "available": list(_RSS_FEEDS.keys()),
        })
    try:
        feed = feedparser.parse(feed_url)
        articles = []
        for entry in feed.entries[:10]:
            articles.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": entry.get("source", {}).get("title", "Unknown"),
            })
        return json.dumps({
            "category": category,
            "count": len(articles),
            "articles": articles,
        })
    except Exception as exc:
        logger.exception("fetch_market_news_by_category failed")
        return json.dumps({"error": str(exc)})


@tool
def fetch_fred_series(series_id: str = "DGS10", limit: int = 30) -> str:
    """Fetch economic data from the FRED (Federal Reserve) API.

    Args:
        series_id: FRED series ID.  Common ones:
            DGS10 – 10-Year Treasury Rate,
            UNRATE – Unemployment Rate,
            CPIAUCSL – CPI,
            FEDFUNDS – Fed Funds Rate,
            GDP – Gross Domestic Product.
        limit: Number of most recent observations.

    Returns:
        JSON with the series observations.
    """
    settings = get_settings()
    api_key = settings.fred_api_key
    if not api_key:
        return json.dumps({
            "error": "FRED_API_KEY not set. Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
        })

    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={api_key}"
        f"&file_type=json&sort_order=desc&limit={limit}"
    )
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        observations = [
            {"date": o["date"], "value": o["value"]}
            for o in data.get("observations", [])
            if o.get("value") != "."
        ]
        return json.dumps({
            "series_id": series_id,
            "count": len(observations),
            "observations": observations,
        })
    except Exception as exc:
        logger.exception("fetch_fred_series failed")
        return json.dumps({"error": str(exc)})


@tool
def fetch_fear_greed_index() -> str:
    """Fetch the CNN Fear & Greed index (alternative.me proxy).

    Returns:
        JSON with the current Fear & Greed index value and classification.
    """
    url = "https://api.alternative.me/fng/?limit=1"
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        record = data.get("data", [{}])[0]
        return json.dumps({
            "value": int(record.get("value", 0)),
            "classification": record.get("value_classification", "N/A"),
            "timestamp": record.get("timestamp", ""),
        })
    except Exception as exc:
        logger.exception("fetch_fear_greed_index failed")
        return json.dumps({"error": str(exc)})


# ── Registry ─────────────────────────────────────────────────────────

NEWS_TOOLS = [
    fetch_financial_news,
    fetch_market_news_by_category,
    fetch_fred_series,
    fetch_fear_greed_index,
]
