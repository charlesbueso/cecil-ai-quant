"""Factor analysis tools – agent-callable functions for factor-based research.

These tools let agents query the factor catalogue, compute factor values
from market data, and run multi-factor screens and comparisons.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from langchain_core.tools import tool

from cecil.tools.factors import (
    FACTORS,
    FactorCategory,
    format_factor_brief,
    get_all_factor_ids,
    get_category_summary,
    get_factor,
    get_factors_by_category,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  REFERENCE TOOLS – query the factor catalogue
# ═══════════════════════════════════════════════════════════════════════


@tool
def list_factor_categories() -> str:
    """List all available investment factor categories and their factors.

    Returns:
        JSON mapping of category names to lists of factor IDs.
    """
    summary = get_category_summary()
    result = {}
    for cat, ids in summary.items():
        result[cat] = [
            {"id": fid, "name": FACTORS[fid].name, "direction": FACTORS[fid].higher_is}
            for fid in ids
        ]
    return json.dumps(result, indent=1)


@tool
def lookup_factor(factor_id: str) -> str:
    """Look up detailed information about a specific investment factor.

    Args:
        factor_id: The factor ID (e.g. "ROE", "FCFP", "EBITDAEV", "PM12xOMR").

    Returns:
        JSON with full factor details including interpretation guidance.
    """
    f = get_factor(factor_id)
    if not f:
        # Try case-insensitive search
        for fid, factor in FACTORS.items():
            if fid.lower() == factor_id.lower():
                f = factor
                break
    if not f:
        return json.dumps({
            "error": f"Factor '{factor_id}' not found",
            "available": get_all_factor_ids()[:20],
            "hint": "Use list_factor_categories to see all factors",
        })
    return json.dumps({
        "factor_id": f.factor_id,
        "name": f.name,
        "category": f.category.value,
        "class_path": f.class_path,
        "description": f.description,
        "higher_is": f.higher_is,
        "interpretation": f.interpretation,
    })


@tool
def get_factors_for_analysis(analysis_type: str) -> str:
    """Get the recommended factors for a specific type of investment analysis.

    Args:
        analysis_type: One of "valuation", "quality", "growth", "momentum",
                       "risk", "income", "comprehensive", "long_term_hold".

    Returns:
        JSON list of recommended factors with interpretation guidance.
    """
    presets: dict[str, list[str]] = {
        "valuation": ["EP", "FEP", "FCFP", "BP", "SP", "SalesEV", "EBITDAEV", "CashEP"],
        "quality": ["ROA", "ROE", "ROIC", "COA", "NEI", "FCFA", "EffTaxRate"],
        "growth": ["SG", "EG", "CFG", "SalesYoYGrw", "EGYoY", "RnDG", "AG_MM_5Y"],
        "momentum": ["PM12xOMR", "ESurprise", "SSurprise", "E_Rev", "E_Diff"],
        "risk": ["Beta", "BetaVol", "OS", "TDTA", "SI", "CrwdNetScore"],
        "income": ["DP", "Dividends", "StckPur", "IntExp", "StckComp"],
        "profitability": ["ROA", "ROE", "ROIC", "IncROIC", "PreTaxROA", "NOPAT"],
        "comprehensive": [
            "FEP", "FCFP", "EBITDAEV",  # Valuation
            "ROIC", "ROE", "FCFA",       # Quality
            "EGYoY", "SalesYoYGrw", "CFG",  # Growth
            "PM12xOMR", "E_Rev",         # Momentum
            "Beta", "TDTA", "SI",        # Risk
        ],
        "long_term_hold": [
            "ROIC", "ROICxRnD", "IncROIC",     # Sustainable profitability
            "FCFP", "FCFA", "CFO12M",           # Cash generation
            "SG", "EG", "CFG", "RnDG",          # Growth trajectory
            "TDTA", "Beta", "BetaVol",          # Risk
            "COA", "NEI",                        # Quality
            "ESurprise", "E_Rev", "E_Diff",     # Market expectations
            "SI", "CrwdNetScore",               # Positioning
            "EP", "FEP", "EBITDAEV",            # Valuation
            "StckPur", "StckComp",              # Capital allocation
        ],
    }

    factor_ids = presets.get(analysis_type.lower(), presets["comprehensive"])
    result = []
    for fid in factor_ids:
        f = get_factor(fid)
        if f:
            result.append({
                "factor_id": f.factor_id,
                "name": f.name,
                "category": f.category.value,
                "higher_is": f.higher_is,
                "interpretation": f.interpretation,
            })

    return json.dumps({
        "analysis_type": analysis_type,
        "factor_count": len(result),
        "factors": result,
    })


# ═══════════════════════════════════════════════════════════════════════
#  COMPUTATION TOOLS – compute factor values from live data
# ═══════════════════════════════════════════════════════════════════════


@tool
def compute_stock_factors(ticker: str) -> str:
    """Compute key investment factors for a stock using live financial data.

    Calculates valuation, profitability, growth, risk, and quality factors
    from Yahoo Finance data. Includes interpretation for each factor.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL", "QUBT").

    Returns:
        JSON with computed factor values, peer context, and interpretations.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y")
        hist_3m = stock.history(period="3mo")

        if hist.empty:
            return json.dumps({"error": f"No data found for {ticker}"})

        # Get financial statements
        try:
            income = stock.financials
            balance = stock.balance_sheet
            cashflow = stock.cashflow
        except Exception:
            income = balance = cashflow = pd.DataFrame()

        result: dict[str, Any] = {
            "ticker": ticker.upper(),
            "name": info.get("shortName", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "factors": {},
        }

        mkt_cap = info.get("marketCap", 0)
        price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        ev = info.get("enterpriseValue", 0)

        # ── Valuation factors ────────────────────────────────────────
        factors = result["factors"]

        _safe_add(factors, "EP", "Earnings to Price",
                  info.get("trailingEps", 0) / price if price else None,
                  "Higher = cheaper. >0.05 is value territory.")

        _safe_add(factors, "FEP", "Forecast Earnings to Price",
                  info.get("forwardEps", 0) / price if price else None,
                  "Forward earnings yield. >0.04 suggests value.")

        pe = info.get("trailingPE")
        _safe_add(factors, "PE_Ratio", "Price to Earnings",
                  pe, "Lower = cheaper. <15 is value, >30 is growth premium.")

        fwd_pe = info.get("forwardPE")
        _safe_add(factors, "Forward_PE", "Forward P/E",
                  fwd_pe, "Based on analyst estimates. Compare to trailing PE for growth trajectory.")

        pb = info.get("priceToBook")
        bp = 1.0 / pb if pb and pb > 0 else None
        _safe_add(factors, "BP", "Book to Price", bp,
                  "Higher = cheaper on book value.")

        ps = info.get("priceToSalesTrailing12Months")
        sp = 1.0 / ps if ps and ps > 0 else None
        _safe_add(factors, "SP", "Sales to Price", sp,
                  "Higher = cheaper on revenue.")

        ev_ebitda = info.get("enterpriseToEbitda")
        ebitda_ev = 1.0 / ev_ebitda if ev_ebitda and ev_ebitda > 0 else None
        _safe_add(factors, "EBITDAEV", "EBITDA to EV", ebitda_ev,
                  "Higher = cheaper operating yield.")

        ev_rev = info.get("enterpriseToRevenue")
        sales_ev = 1.0 / ev_rev if ev_rev and ev_rev > 0 else None
        _safe_add(factors, "SalesEV", "Sales to EV", sales_ev,
                  "Revenue yield on EV. Higher = cheaper.")

        # ── Profitability factors ────────────────────────────────────
        roa = info.get("returnOnAssets")
        _safe_add(factors, "ROA", "Return on Assets", roa,
                  "Core profitability. >0.10 is strong.")

        roe = info.get("returnOnEquity")
        _safe_add(factors, "ROE", "Return on Equity", roe,
                  "Equity efficiency. >0.15 is good. Watch for leverage inflation.")

        profit_margin = info.get("profitMargins")
        _safe_add(factors, "ProfitMargin", "Profit Margin", profit_margin,
                  "Net margin. Higher = more pricing power.")

        op_margin = info.get("operatingMargins")
        _safe_add(factors, "OpMargin", "Operating Margin", op_margin,
                  "Operating efficiency before interest/tax.")

        # ── Cash Flow factors ────────────────────────────────────────
        fcf = info.get("freeCashflow", 0)
        fcfp = fcf / mkt_cap if mkt_cap and fcf else None
        _safe_add(factors, "FCFP", "Free Cash Flow to Price", fcfp,
                  "FCF yield. >0.05 is strong cash generation.")

        op_cf = info.get("operatingCashflow", 0)
        _safe_add(factors, "CFO12M", "Cash from Ops (12M)",
                  op_cf, "Trailing operating cash flow.")

        if op_cf and mkt_cap:
            total_assets = info.get("totalAssets", 0)
            if total_assets:
                _safe_add(factors, "FCFA", "FCF to Assets",
                          fcf / total_assets if fcf else None,
                          "Asset-normalized FCF. Higher = more efficient.")

        # ── Growth factors ───────────────────────────────────────────
        rev_growth = info.get("revenueGrowth")
        _safe_add(factors, "SalesYoYGrw", "Sales Growth YoY", rev_growth,
                  "Revenue growth. >0.10 is solid organic growth.")

        earn_growth = info.get("earningsGrowth")
        _safe_add(factors, "EGYoY", "Earnings Growth YoY", earn_growth,
                  "Earnings trajectory. Accelerating growth is a strong signal.")

        # ── Risk factors ─────────────────────────────────────────────
        beta = info.get("beta")
        _safe_add(factors, "Beta", "Beta", beta,
                  "Market sensitivity. >1.5 = high risk, <0.8 = defensive.")

        # Compute historical volatility
        if not hist.empty:
            returns = hist["Close"].pct_change().dropna()
            vol = float(returns.std() * np.sqrt(252))
            _safe_add(factors, "AnnualizedVol", "Annualized Volatility", round(vol, 4),
                      "Total risk. >0.40 = very volatile, <0.20 = low vol.")

            # Max drawdown
            cummax = hist["Close"].cummax()
            drawdown = (hist["Close"] - cummax) / cummax
            max_dd = float(drawdown.min())
            _safe_add(factors, "MaxDrawdown", "Max Drawdown (1Y)", round(max_dd, 4),
                      "Worst peak-to-trough decline. < -0.30 = significant risk.")

            # Momentum (12M ex-1M)
            if len(hist) > 25:
                ret_12m = float(hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1)
                ret_1m = float(hist["Close"].iloc[-1] / hist["Close"].iloc[-22] - 1) if len(hist) > 22 else 0
                pm12x = ret_12m - ret_1m
                _safe_add(factors, "PM12xOMR", "Momentum 12M ex-1M", round(pm12x, 4),
                          "Positive = uptrend. Classic momentum signal.")

        # ── Leverage ─────────────────────────────────────────────────
        debt_equity = info.get("debtToEquity")
        _safe_add(factors, "DebtToEquity", "Debt to Equity",
                  debt_equity / 100 if debt_equity else None,
                  "Leverage ratio. >1.0 = highly leveraged.")

        total_debt = info.get("totalDebt", 0)
        total_assets = info.get("totalAssets", 0)
        if total_assets:
            _safe_add(factors, "TDTA", "Debt to Assets",
                      round(total_debt / total_assets, 4) if total_debt else None,
                      "Higher = more leverage risk. >0.5 is elevated.")

        # ── Quality signals ──────────────────────────────────────────
        # Net Equity Issuance proxy (shares outstanding change)
        shares = info.get("sharesOutstanding", 0)
        shares_prev = info.get("floatShares", 0)
        if shares and shares_prev and shares_prev > 0:
            nei_est = (shares - shares_prev) / shares_prev
            if abs(nei_est) < 2:  # sanity check
                _safe_add(factors, "NEI_proxy", "Net Equity Issuance (est.)",
                          round(nei_est, 4),
                          "Negative = buybacks (good). Positive = dilution.")

        # Short interest
        short_pct = info.get("shortPercentOfFloat")
        _safe_add(factors, "SI", "Short Interest (% float)",
                  short_pct, "High short interest = bearish pressure or squeeze potential.")

        # ── Dividend ─────────────────────────────────────────────────
        div_yield = info.get("dividendYield")
        _safe_add(factors, "DP", "Dividend Yield", div_yield,
                  "Income return. Check payout ratio for sustainability.")

        payout = info.get("payoutRatio")
        _safe_add(factors, "PayoutRatio", "Payout Ratio", payout,
                  "% of earnings paid as dividends. >0.80 = at risk of cut.")

        # ── Size context ─────────────────────────────────────────────
        _safe_add(factors, "MktCapM", "Market Cap ($M)",
                  round(mkt_cap / 1e6, 1) if mkt_cap else None,
                  "Size bucket: <$300M=micro, <$2B=small, <$10B=mid, >$10B=large.")

        result["factor_count"] = len(factors)
        return json.dumps(result, indent=1, default=str)
    except Exception as exc:
        logger.exception("compute_stock_factors failed for %s", ticker)
        return json.dumps({"error": str(exc)})


def _safe_add(
    factors: dict[str, Any],
    factor_id: str,
    name: str,
    value: Any,
    interpretation: str,
) -> None:
    """Add a factor value only if it's valid."""
    if value is None:
        return
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return
    factors[factor_id] = {
        "name": name,
        "value": round(value, 6) if isinstance(value, float) else value,
        "interpretation": interpretation,
    }


@tool
def compare_stock_factors(tickers: str, focus: str = "comprehensive") -> str:
    """Compare investment factors across multiple stocks side by side.

    Args:
        tickers: Comma-separated ticker symbols (e.g. "AAPL,MSFT,GOOGL").
        focus: Analysis focus – one of "valuation", "quality", "growth",
               "risk", "comprehensive" (default).

    Returns:
        JSON with factor values for each stock and relative rankings.
    """
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()][:6]

    # Define which factors to compare based on focus
    focus_factors: dict[str, list[str]] = {
        "valuation": ["EP", "FEP", "BP", "SP", "EBITDAEV", "SalesEV", "FCFP"],
        "quality": ["ROA", "ROE", "ProfitMargin", "OpMargin", "FCFA"],
        "growth": ["SalesYoYGrw", "EGYoY"],
        "risk": ["Beta", "AnnualizedVol", "MaxDrawdown", "TDTA", "SI"],
        "comprehensive": [
            "EP", "FEP", "FCFP", "EBITDAEV",
            "ROA", "ROE", "ProfitMargin",
            "SalesYoYGrw", "EGYoY",
            "Beta", "AnnualizedVol", "TDTA",
            "MktCapM",
        ],
    }
    selected = focus_factors.get(focus.lower(), focus_factors["comprehensive"])

    results: dict[str, Any] = {"tickers": symbols, "focus": focus, "comparison": {}}

    for sym in symbols:
        try:
            raw = compute_stock_factors.invoke({"ticker": sym})
            data = json.loads(raw)
            if "error" in data:
                results["comparison"][sym] = {"error": data["error"]}
                continue

            factors = data.get("factors", {})
            filtered = {}
            for fid in selected:
                if fid in factors:
                    filtered[fid] = factors[fid]
            filtered["_meta"] = {
                "name": data.get("name", ""),
                "sector": data.get("sector", ""),
            }
            results["comparison"][sym] = filtered
        except Exception as exc:
            results["comparison"][sym] = {"error": str(exc)}

    # Add rankings for each factor
    rankings: dict[str, list[dict[str, Any]]] = {}
    for fid in selected:
        vals = []
        for sym in symbols:
            comp = results["comparison"].get(sym, {})
            if isinstance(comp, dict) and fid in comp and "value" in comp[fid]:
                vals.append({"ticker": sym, "value": comp[fid]["value"]})
        if vals:
            # Sort based on whether higher or lower is better
            factor_info = get_factor(fid)
            reverse = True  # default: higher is better
            if factor_info and factor_info.higher_is == "worse":
                reverse = False
            vals.sort(key=lambda x: x["value"] if x["value"] is not None else float("-inf"), reverse=reverse)
            rankings[fid] = vals

    results["rankings"] = rankings
    return json.dumps(results, indent=1, default=str)


@tool
def factor_screen(
    tickers: str,
    criteria: str = "value_quality",
) -> str:
    """Screen stocks using predefined multi-factor criteria.

    Args:
        tickers: Comma-separated tickers to screen (e.g. "AAPL,MSFT,GOOGL,NVDA,META").
        criteria: Screening preset:
            - "value_quality": Cheap + profitable (FCFP, ROIC, low TDTA)
            - "growth_momentum": Growing + positive momentum (EGYoY, SalesYoYGrw, PM12xOMR)
            - "defensive": Low beta, high dividend, stable
            - "aggressive_growth": High growth, high momentum, accept risk

    Returns:
        JSON with scores and rankings for each stock under the criteria.
    """
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()][:10]

    # Define scoring weights for each preset
    presets: dict[str, dict[str, tuple[float, str]]] = {
        "value_quality": {
            "FCFP": (0.20, "better"),
            "EP": (0.15, "better"),
            "EBITDAEV": (0.15, "better"),
            "ROE": (0.15, "better"),
            "ProfitMargin": (0.10, "better"),
            "TDTA": (0.10, "worse"),
            "AnnualizedVol": (0.15, "worse"),
        },
        "growth_momentum": {
            "SalesYoYGrw": (0.25, "better"),
            "EGYoY": (0.25, "better"),
            "PM12xOMR": (0.20, "better"),
            "ROE": (0.15, "better"),
            "AnnualizedVol": (0.15, "worse"),
        },
        "defensive": {
            "Beta": (0.20, "worse"),
            "AnnualizedVol": (0.20, "worse"),
            "DP": (0.20, "better"),
            "FCFP": (0.15, "better"),
            "TDTA": (0.15, "worse"),
            "MaxDrawdown": (0.10, "worse"),
        },
        "aggressive_growth": {
            "SalesYoYGrw": (0.20, "better"),
            "EGYoY": (0.20, "better"),
            "PM12xOMR": (0.20, "better"),
            "FCFP": (0.15, "better"),
            "ROE": (0.15, "better"),
            "Beta": (0.10, "better"),  # want high beta for aggressive
        },
    }

    weights = presets.get(criteria, presets["value_quality"])

    # Gather factor data
    stock_data: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        try:
            raw = compute_stock_factors.invoke({"ticker": sym})
            data = json.loads(raw)
            stock_data[sym] = data.get("factors", {}) if "factors" in data else {}
        except Exception:
            stock_data[sym] = {}

    # Score each stock
    scores: list[dict[str, Any]] = []
    for sym in symbols:
        fdata = stock_data[sym]
        total_score = 0.0
        max_possible = 0.0
        factor_scores: dict[str, Any] = {}

        for fid, (weight, direction) in weights.items():
            if fid in fdata and "value" in fdata[fid]:
                val = fdata[fid]["value"]
                if val is not None and isinstance(val, (int, float)):
                    # Normalise using rank-based scoring (simplified)
                    all_vals = []
                    for s in symbols:
                        if fid in stock_data.get(s, {}) and "value" in stock_data[s].get(fid, {}):
                            v = stock_data[s][fid]["value"]
                            if v is not None:
                                all_vals.append(v)

                    if len(all_vals) > 1:
                        sorted_vals = sorted(all_vals, reverse=(direction == "better"))
                        rank = sorted_vals.index(val)
                        pct_rank = 1.0 - (rank / (len(sorted_vals) - 1))
                    else:
                        pct_rank = 0.5

                    weighted = pct_rank * weight
                    total_score += weighted
                    max_possible += weight
                    factor_scores[fid] = {
                        "value": val,
                        "percentile_rank": round(pct_rank, 2),
                        "weighted_score": round(weighted, 4),
                    }

        final_score = round(total_score / max_possible * 100, 1) if max_possible > 0 else 0
        scores.append({
            "ticker": sym,
            "composite_score": final_score,
            "factor_scores": factor_scores,
            "data_coverage": f"{len(factor_scores)}/{len(weights)}",
        })

    scores.sort(key=lambda x: x["composite_score"], reverse=True)

    return json.dumps({
        "criteria": criteria,
        "description": {
            "value_quality": "Screens for cheap, profitable, low-risk stocks",
            "growth_momentum": "Screens for high growth with positive price momentum",
            "defensive": "Screens for low-volatility, income-generating, stable stocks",
            "aggressive_growth": "Screens for maximum growth, accepts higher risk",
        }.get(criteria, "Custom screen"),
        "rankings": scores,
    }, indent=1, default=str)


# ── Registry ─────────────────────────────────────────────────────────

FACTOR_TOOLS = [
    list_factor_categories,
    lookup_factor,
    get_factors_for_analysis,
    compute_stock_factors,
    compare_stock_factors,
    factor_screen,
]
