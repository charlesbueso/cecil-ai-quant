"""Python computation tools for quantitative analysis.

Provides safe, sandboxed statistical and financial math utilities that
agents can invoke without writing arbitrary code.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any

import numpy as np
import pandas as pd
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def compute_returns(prices_json: str) -> str:
    """Compute daily / periodic returns from a JSON list of prices.

    Args:
        prices_json: JSON array of numbers representing sequential close prices,
                     e.g. '[100, 102, 101, 105]'.

    Returns:
        JSON with simple returns, log returns, cumulative return, and basic stats.
    """
    try:
        prices = json.loads(prices_json)
        if not prices or len(prices) < 2:
            return json.dumps({"error": "Need at least 2 prices"})

        s = pd.Series(prices, dtype=float)
        simple = s.pct_change().dropna()
        log_ret = np.log(s / s.shift(1)).dropna()

        return json.dumps({
            "simple_returns": [round(float(r), 6) for r in simple],
            "log_returns": [round(float(r), 6) for r in log_ret],
            "cumulative_return_pct": round(float((s.iloc[-1] / s.iloc[0] - 1) * 100), 4),
            "mean_return_pct": round(float(simple.mean() * 100), 4),
            "std_dev_pct": round(float(simple.std() * 100), 4),
            "annualized_vol_pct": round(float(simple.std() * math.sqrt(252) * 100), 4),
            "sharpe_approx": round(float(simple.mean() / simple.std() * math.sqrt(252)), 4)
            if simple.std() > 0
            else None,
            "max_drawdown_pct": round(float(((s / s.cummax()) - 1).min() * 100), 4),
            "n_periods": len(simple),
        })
    except Exception as exc:
        logger.exception("compute_returns failed")
        return json.dumps({"error": str(exc)})


@tool
def compute_correlation(series_a_json: str, series_b_json: str) -> str:
    """Compute Pearson correlation between two series.

    Args:
        series_a_json: JSON array of numbers (e.g. prices or returns).
        series_b_json: JSON array of numbers of the same length.

    Returns:
        JSON with correlation, covariance, and beta.
    """
    try:
        a = pd.Series(json.loads(series_a_json), dtype=float)
        b = pd.Series(json.loads(series_b_json), dtype=float)
        if len(a) != len(b):
            return json.dumps({"error": "Series must be the same length"})

        corr = float(a.corr(b))
        cov = float(a.cov(b))
        beta = cov / float(b.var()) if b.var() > 0 else None

        return json.dumps({
            "correlation": round(corr, 6),
            "covariance": round(cov, 8),
            "beta": round(beta, 6) if beta is not None else None,
            "n": len(a),
        })
    except Exception as exc:
        logger.exception("compute_correlation failed")
        return json.dumps({"error": str(exc)})


@tool
def compute_portfolio_metrics(
    weights_json: str,
    returns_matrix_json: str,
) -> str:
    """Compute portfolio-level risk and return metrics.

    Args:
        weights_json: JSON array of portfolio weights (must sum to ~1.0),
                      e.g. '[0.4, 0.3, 0.3]'.
        returns_matrix_json: JSON 2-D array where each inner array is the
                             return series for one asset, e.g.
                             '[[0.01, -0.02, ...], [0.005, 0.01, ...], ...]'.

    Returns:
        JSON with portfolio return, volatility, Sharpe, and per-asset contribution.
    """
    try:
        weights = np.array(json.loads(weights_json), dtype=float)
        returns_matrix = np.array(json.loads(returns_matrix_json), dtype=float)

        if returns_matrix.shape[0] != len(weights):
            return json.dumps({
                "error": f"Weight count ({len(weights)}) ≠ asset count ({returns_matrix.shape[0]})"
            })

        mean_returns = returns_matrix.mean(axis=1)
        cov_matrix = np.cov(returns_matrix)

        port_return = float(weights @ mean_returns)
        port_var = float(weights @ cov_matrix @ weights)
        port_vol = math.sqrt(port_var)
        sharpe = (port_return / port_vol * math.sqrt(252)) if port_vol > 0 else None

        # Risk contribution
        marginal = cov_matrix @ weights
        risk_contrib = weights * marginal
        total_risk = risk_contrib.sum()
        pct_contrib = (risk_contrib / total_risk * 100) if total_risk > 0 else risk_contrib

        return json.dumps({
            "portfolio_daily_return_pct": round(port_return * 100, 4),
            "portfolio_annualized_return_pct": round(port_return * 252 * 100, 4),
            "portfolio_daily_vol_pct": round(port_vol * 100, 4),
            "portfolio_annualized_vol_pct": round(port_vol * math.sqrt(252) * 100, 4),
            "sharpe_ratio": round(sharpe, 4) if sharpe is not None else None,
            "weights": [round(float(w), 4) for w in weights],
            "risk_contribution_pct": [round(float(p), 2) for p in pct_contrib],
        })
    except Exception as exc:
        logger.exception("compute_portfolio_metrics failed")
        return json.dumps({"error": str(exc)})


@tool
def compute_moving_averages(prices_json: str, windows: str = "20,50,200") -> str:
    """Calculate simple and exponential moving averages.

    Args:
        prices_json: JSON array of prices.
        windows: Comma-separated window sizes (e.g. "20,50,200").

    Returns:
        JSON with SMA and EMA values for each window at the latest point.
    """
    try:
        prices = pd.Series(json.loads(prices_json), dtype=float)
        wins = [int(w.strip()) for w in windows.split(",")]
        result: dict[str, Any] = {"latest_price": round(float(prices.iloc[-1]), 2)}

        for w in wins:
            if len(prices) >= w:
                sma = float(prices.rolling(w).mean().iloc[-1])
                ema = float(prices.ewm(span=w, adjust=False).mean().iloc[-1])
                result[f"SMA_{w}"] = round(sma, 2)
                result[f"EMA_{w}"] = round(ema, 2)
            else:
                result[f"SMA_{w}"] = None
                result[f"EMA_{w}"] = None
        return json.dumps(result)
    except Exception as exc:
        logger.exception("compute_moving_averages failed")
        return json.dumps({"error": str(exc)})


@tool
def descriptive_statistics(data_json: str) -> str:
    """Return descriptive statistics for a numeric series.

    Args:
        data_json: JSON array of numbers.

    Returns:
        JSON with count, mean, median, std, min, max, skew, kurtosis, percentiles.
    """
    try:
        s = pd.Series(json.loads(data_json), dtype=float)
        return json.dumps({
            "count": int(s.count()),
            "mean": round(float(s.mean()), 6),
            "median": round(float(s.median()), 6),
            "std": round(float(s.std()), 6),
            "min": round(float(s.min()), 6),
            "max": round(float(s.max()), 6),
            "skewness": round(float(s.skew()), 6),
            "kurtosis": round(float(s.kurtosis()), 6),
            "p25": round(float(s.quantile(0.25)), 6),
            "p75": round(float(s.quantile(0.75)), 6),
            "p95": round(float(s.quantile(0.95)), 6),
        })
    except Exception as exc:
        logger.exception("descriptive_statistics failed")
        return json.dumps({"error": str(exc)})


# ── Registry ─────────────────────────────────────────────────────────

COMPUTATION_TOOLS = [
    compute_returns,
    compute_correlation,
    compute_portfolio_metrics,
    compute_moving_averages,
    descriptive_statistics,
]
