"""Financial data retrieval tools.

Wraps Yahoo Finance (yfinance) and optional Alpha Vantage / FRED APIs
behind LangChain ``@tool`` functions so any agent can pull market data.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ── Yahoo Finance tools ─────────────────────────────────────────────


@tool
def get_stock_price(ticker: str) -> str:
    """Get the current / latest stock price and basic info for a ticker symbol.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL", "MSFT").

    Returns:
        JSON string with price data and company info.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="5d")
        if hist.empty:
            return json.dumps({"error": f"No data found for {ticker}"})

        latest = hist.iloc[-1]
        result = {
            "ticker": ticker.upper(),
            "name": info.get("shortName", "N/A"),
            "current_price": round(float(latest["Close"]), 2),
            "previous_close": round(float(hist.iloc[-2]["Close"]), 2) if len(hist) > 1 else None,
            "volume": int(latest["Volume"]),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector", "N/A"),
            "timestamp": datetime.now().isoformat(),
        }
        return json.dumps(result, default=str)
    except Exception as exc:
        logger.exception("get_stock_price failed for %s", ticker)
        return json.dumps({"error": str(exc)})


@tool
def get_historical_prices(
    ticker: str,
    period: str = "1mo",
    interval: str = "1d",
) -> str:
    """Download historical OHLCV data for a ticker.

    Args:
        ticker: Stock ticker symbol.
        period: Data period – "1d","5d","1mo","3mo","6mo","1y","2y","5y","10y","ytd","max".
        interval: Bar size – "1m","2m","5m","15m","30m","60m","90m","1h","1d","5d","1wk","1mo","3mo".

    Returns:
        JSON string with a list of OHLCV records.
    """
    try:
        hist = yf.download(ticker, period=period, interval=interval, progress=False)
        if hist.empty:
            return json.dumps({"error": f"No historical data for {ticker}"})

        # Flatten multi-index columns if present
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)

        records = []
        for date, row in hist.iterrows():
            records.append({
                "date": str(date.date()) if hasattr(date, "date") else str(date),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return json.dumps({"ticker": ticker.upper(), "records": records[-60:]})  # cap output
    except Exception as exc:
        logger.exception("get_historical_prices failed")
        return json.dumps({"error": str(exc)})


@tool
def get_multiple_stock_prices(tickers: str) -> str:
    """Get current prices for multiple tickers at once.

    Args:
        tickers: Comma-separated ticker symbols (e.g. "AAPL,MSFT,GOOGL").

    Returns:
        JSON with price data for each ticker.
    """
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    results: list[dict[str, Any]] = []
    for sym in symbols[:10]:  # cap at 10
        try:
            stock = yf.Ticker(sym)
            hist = stock.history(period="2d")
            if hist.empty:
                results.append({"ticker": sym, "error": "no data"})
                continue
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest
            change_pct = ((latest["Close"] - prev["Close"]) / prev["Close"]) * 100
            results.append({
                "ticker": sym,
                "price": round(float(latest["Close"]), 2),
                "change_pct": round(float(change_pct), 2),
                "volume": int(latest["Volume"]),
            })
        except Exception as exc:
            results.append({"ticker": sym, "error": str(exc)})
    return json.dumps(results)


@tool
def get_financial_statements(ticker: str, statement_type: str = "income") -> str:
    """Retrieve financial statements for a company.

    Args:
        ticker: Stock ticker symbol.
        statement_type: One of "income", "balance", "cashflow".

    Returns:
        JSON with the most recent annual statement data.
    """
    try:
        stock = yf.Ticker(ticker)
        stmt_map = {
            "income": stock.financials,
            "balance": stock.balance_sheet,
            "cashflow": stock.cashflow,
        }
        df = stmt_map.get(statement_type)
        if df is None or df.empty:
            return json.dumps({"error": f"No {statement_type} statement for {ticker}"})

        # Take most recent column
        latest = df.iloc[:, 0]
        data = {str(k): float(v) if pd.notna(v) else None for k, v in latest.items()}
        return json.dumps({
            "ticker": ticker.upper(),
            "statement_type": statement_type,
            "period": str(df.columns[0].date()) if hasattr(df.columns[0], "date") else str(df.columns[0]),
            "data": data,
        }, default=str)
    except Exception as exc:
        logger.exception("get_financial_statements failed")
        return json.dumps({"error": str(exc)})


# ── Registry ─────────────────────────────────────────────────────────

FINANCIAL_TOOLS = [
    get_stock_price,
    get_historical_prices,
    get_multiple_stock_prices,
    get_financial_statements,
]
