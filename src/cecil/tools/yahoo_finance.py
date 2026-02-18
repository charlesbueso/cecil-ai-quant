"""Lightweight Yahoo Finance client using httpx.

Drop-in replacement for the yfinance APIs used by Cecil tools,
without the `multitasking` dependency that breaks Vercel's
``--only-binary=:all:`` constraint.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Re-usable client (connection pooling across calls within the same Lambda)
_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(headers=_HEADERS, timeout=20, follow_redirects=True)
    return _client


# ── Period / interval mapping ────────────────────────────────────────

_PERIOD_MAP: dict[str, str] = {
    "1d": "1d", "5d": "5d", "1mo": "1mo", "3mo": "3mo",
    "6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y",
    "10y": "10y", "ytd": "ytd", "max": "max",
}

_INTERVAL_MAP: dict[str, str] = {
    "1m": "1m", "2m": "2m", "5m": "5m", "15m": "15m",
    "30m": "30m", "60m": "60m", "90m": "90m", "1h": "1h",
    "1d": "1d", "5d": "5d", "1wk": "1wk", "1mo": "1mo", "3mo": "3mo",
}


# ═══════════════════════════════════════════════════════════════════════
#  Ticker class – mirrors subset of yfinance.Ticker
# ═══════════════════════════════════════════════════════════════════════


class Ticker:
    """Minimal drop-in for ``yfinance.Ticker``."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol.upper()
        self._info: dict[str, Any] | None = None
        self._financials: pd.DataFrame | None = None
        self._balance_sheet: pd.DataFrame | None = None
        self._cashflow: pd.DataFrame | None = None

    # ── info property ────────────────────────────────────────────────

    @property
    def info(self) -> dict[str, Any]:
        if self._info is None:
            self._info = self._fetch_quote_summary()
        return self._info

    def _fetch_quote_summary(self) -> dict[str, Any]:
        """Fetch quote-summary modules and flatten into a single dict."""
        modules = (
            "summaryDetail,defaultKeyStatistics,financialData,"
            "assetProfile,earningsTrend,calendarEvents"
        )
        url = (
            f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/"
            f"{self.symbol}?modules={modules}"
        )
        try:
            resp = _get_client().get(url)
            resp.raise_for_status()
            data = resp.json()
            result_list = data.get("quoteSummary", {}).get("result", [])
            if not result_list:
                return {}
            merged: dict[str, Any] = {}
            for module_dict in result_list:
                for _mod_name, mod_data in module_dict.items():
                    if isinstance(mod_data, dict):
                        for k, v in mod_data.items():
                            merged[k] = _unwrap(v)
            return merged
        except Exception:
            logger.exception("quoteSummary failed for %s", self.symbol)
            return {}

    # ── history ──────────────────────────────────────────────────────

    def history(self, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
        return download(
            self.symbol, period=period, interval=interval, progress=False,
        )

    # ── financial statements ─────────────────────────────────────────

    @property
    def financials(self) -> pd.DataFrame:
        if self._financials is None:
            self._financials = self._fetch_statement("incomeStatementHistory")
        return self._financials

    @property
    def balance_sheet(self) -> pd.DataFrame:
        if self._balance_sheet is None:
            self._balance_sheet = self._fetch_statement("balanceSheetHistory")
        return self._balance_sheet

    @property
    def cashflow(self) -> pd.DataFrame:
        if self._cashflow is None:
            self._cashflow = self._fetch_statement("cashflowStatementHistory")
        return self._cashflow

    def _fetch_statement(self, module: str) -> pd.DataFrame:
        url = (
            f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/"
            f"{self.symbol}?modules={module}"
        )
        try:
            resp = _get_client().get(url)
            resp.raise_for_status()
            data = resp.json()
            result_list = data.get("quoteSummary", {}).get("result", [])
            if not result_list:
                return pd.DataFrame()
            mod_data = result_list[0].get(module, {})
            statements = mod_data.get(
                # The key inside each module varies
                next(
                    (k for k in mod_data if isinstance(mod_data.get(k), list)),
                    "",
                ),
                [],
            )
            if not statements:
                return pd.DataFrame()
            rows: dict[str, dict[str, float | None]] = {}
            for stmt in statements:
                end_date = stmt.get("endDate", {})
                col_label = end_date.get("fmt", str(end_date.get("raw", "")))
                if not col_label:
                    continue
                for key, val in stmt.items():
                    if key in ("endDate", "maxAge"):
                        continue
                    raw_val = val.get("raw") if isinstance(val, dict) else None
                    rows.setdefault(key, {})[col_label] = raw_val
            df = pd.DataFrame(rows).T
            # Convert column labels to datetime for compatibility
            try:
                df.columns = pd.to_datetime(df.columns)
            except Exception:
                pass
            return df
        except Exception:
            logger.exception("_fetch_statement(%s) failed for %s", module, self.symbol)
            return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════
#  download() – mirrors yfinance.download()
# ═══════════════════════════════════════════════════════════════════════


def download(
    tickers: str,
    *,
    period: str = "1mo",
    interval: str = "1d",
    start: str | None = None,
    progress: bool = False,  # ignored, kept for API compat
    timeout: int = 20,
) -> pd.DataFrame:
    """Download OHLCV data for one or more tickers.

    Mimics ``yfinance.download`` return format (DatetimeIndex,
    columns = Open/High/Low/Close/Volume).
    """
    # Handle comma-separated or space-separated tickers
    if isinstance(tickers, str):
        symbols = [t.strip().upper() for t in tickers.replace(",", " ").split() if t.strip()]
    else:
        symbols = [str(t).upper() for t in tickers]

    if len(symbols) == 1:
        return _download_single(symbols[0], period=period, interval=interval, start=start)

    # Multi-ticker: return MultiIndex columns like yfinance
    frames: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = _download_single(sym, period=period, interval=interval, start=start)
        if not df.empty:
            frames[sym] = df

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, axis=1)
    # Swap levels so the first level is the field (Open, High, …) and second is ticker
    combined.columns = combined.columns.swaplevel(0, 1)
    combined.sort_index(axis=1, level=0, inplace=True)
    return combined


def _download_single(
    symbol: str,
    *,
    period: str = "1mo",
    interval: str = "1d",
    start: str | None = None,
) -> pd.DataFrame:
    """Fetch chart data for a single ticker."""
    params: dict[str, str] = {
        "interval": _INTERVAL_MAP.get(interval, interval),
    }
    if start:
        # Convert start date string to epoch
        try:
            dt = datetime.strptime(start[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            params["period1"] = str(int(dt.timestamp()))
            params["period2"] = str(int(datetime.now(tz=timezone.utc).timestamp()))
        except ValueError:
            params["range"] = _PERIOD_MAP.get(period, period)
    else:
        params["range"] = _PERIOD_MAP.get(period, period)

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        resp = _get_client().get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        chart = data.get("chart", {}).get("result", [])
        if not chart:
            return pd.DataFrame()
        result = chart[0]
        timestamps = result.get("timestamp", [])
        if not timestamps:
            return pd.DataFrame()
        indicators = result["indicators"]["quote"][0]
        df = pd.DataFrame(
            {
                "Open": indicators.get("open", []),
                "High": indicators.get("high", []),
                "Low": indicators.get("low", []),
                "Close": indicators.get("close", []),
                "Volume": indicators.get("volume", []),
            },
            index=pd.DatetimeIndex(
                pd.to_datetime(timestamps, unit="s", utc=True),
                name="Date",
            ),
        )
        df.dropna(subset=["Close"], inplace=True)
        # Localise then strip tz for yfinance compat
        df.index = df.index.tz_convert(None)
        return df
    except Exception:
        logger.exception("chart download failed for %s", symbol)
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════


def _unwrap(val: Any) -> Any:
    """Yahoo Finance returns ``{"raw": 1.23, "fmt": "1.23"}``; extract raw."""
    if isinstance(val, dict):
        if "raw" in val:
            return val["raw"]
        # Nested dicts (like address) – just return as-is
        return val
    return val
