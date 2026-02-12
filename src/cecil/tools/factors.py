"""Quantitative factor registry – loaded from ab-2024.xlsx.

Provides a structured catalogue of 70+ investment factors spanning
valuation, profitability, growth, quality, momentum, risk, and
alternative-data categories.  Agents can query the registry to
understand what analytical dimensions are available and how to compute
or interpret each factor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FactorCategory(str, Enum):
    VALUATION = "valuation"
    PROFITABILITY = "profitability"
    GROWTH = "growth"
    QUALITY = "quality"
    SURPRISE_REVISION = "surprise_revision"
    CASH_FLOW = "cash_flow"
    RISK_MOMENTUM = "risk_momentum"
    BALANCE_SHEET = "balance_sheet"
    SIZE = "size"
    RND_INNOVATION = "rnd_innovation"
    INCOME_DIVIDEND = "income_dividend"
    MACRO = "macro"
    SENTIMENT_ALT = "sentiment_alt"
    LEVERAGE = "leverage"


@dataclass(frozen=True, slots=True)
class Factor:
    """One investment factor from the quantm factor library."""

    factor_id: str          # Short id (e.g. "EP", "ROE")
    name: str               # Human-readable name
    category: FactorCategory
    class_path: str         # quantm.factor.* path
    description: str        # What the factor measures
    higher_is: str          # "better", "worse", "neutral"
    interpretation: str     # How an analyst should read this factor
    active: bool = True


# ═══════════════════════════════════════════════════════════════════════
#  FACTOR CATALOGUE  –  sourced from ab-2024.xlsx (active factors)
# ═══════════════════════════════════════════════════════════════════════

FACTORS: dict[str, Factor] = {}

def _r(f: Factor) -> None:
    """Register a factor."""
    FACTORS[f.factor_id] = f


# ── Valuation ────────────────────────────────────────────────────────

_r(Factor("EP", "Earnings to Price", FactorCategory.VALUATION,
    "quantm.factor.earnings.EP", "Earnings yield – net income divided by market cap",
    "better", "Higher EP = cheaper stock on an earnings basis. Classic value signal."))

_r(Factor("FEP", "Forecast Earnings to Price", FactorCategory.VALUATION,
    "quantm.factor.earnings.ForecastEarningsToPrice",
    "Forward earnings yield using consensus analyst estimates",
    "better", "Higher FEP = cheaper on forward estimates. Preferred over trailing EP when estimates are reliable."))

_r(Factor("CashEP", "Cash Earnings to Price", FactorCategory.VALUATION,
    "quantm.factor.earnings.CashEarningsToPrice",
    "Cash earnings (earnings adjusted for non-cash items) divided by price",
    "better", "Higher = cheaper on cash-basis earnings. Filters out accounting distortions."))

_r(Factor("FCFP", "Free Cash Flow to Price", FactorCategory.VALUATION,
    "quantm.factor.freecashflow.FCFP",
    "Free cash flow yield – FCF divided by market cap",
    "better", "Higher FCFP = more actual cash generation per dollar of market cap. Strong value signal."))

_r(Factor("BP", "Book to Price", FactorCategory.VALUATION,
    "quantm.factor.book.BookToPrice",
    "Book value of equity divided by market capitalisation",
    "better", "Higher BP = cheaper on book value. Traditional deep-value metric."))

_r(Factor("TBP", "Tangible Book to Price", FactorCategory.VALUATION,
    "quantm.factor.book.TangibleBookToPrice",
    "Tangible book value (excl. goodwill/intangibles) divided by price",
    "better", "Like BP but strips intangibles. Better for capital-intensive sectors."))

_r(Factor("SP", "Sales to Price", FactorCategory.VALUATION,
    "quantm.factor.sales.SalesToPrice", "Revenue divided by market cap",
    "better", "Higher SP = cheaper on revenue basis. Useful for unprofitable growth companies."))

_r(Factor("SalesEV", "Sales to EV", FactorCategory.VALUATION,
    "quantm.factor.sales.SalesToEV",
    "Revenue divided by enterprise value (market cap + debt − cash)",
    "better", "Revenue yield on EV basis. Captures capital structure; preferred for capital-heavy firms."))

_r(Factor("EBITDAEV", "EBITDA to EV", FactorCategory.VALUATION,
    "quantm.factor.earnings.EBITDAEV",
    "EBITDA divided by enterprise value",
    "better", "Operating earnings yield. High EBITDAEV = cheap operating assets. Cross-sector comparable."))

_r(Factor("EBITDAEVFin", "EBITDA to EV (Financials)", FactorCategory.VALUATION,
    "quantm.factor.earnings.EBITDAEVFin",
    "EBITDA/EV adjusted for financial-sector balance sheets",
    "better", "Like EBITDAEV but with financial-sector-specific adjustments."))

_r(Factor("EV", "Enterprise Value", FactorCategory.VALUATION,
    "quantm.factor.earnings.EnterpriseValue",
    "Market cap + total debt − cash & equivalents",
    "neutral", "Size-like measure of total firm value including debt holders."))

_r(Factor("DP", "Dividend Yield", FactorCategory.INCOME_DIVIDEND,
    "quantm.factor.dividend.DividendYield",
    "Common dividends divided by market cap",
    "better", "Higher DP = higher income return. Check payout sustainability before relying on this."))

# ── Profitability ────────────────────────────────────────────────────

_r(Factor("ROA", "Return on Assets", FactorCategory.PROFITABILITY,
    "quantm.factor.roa.ROA", "Net income divided by total assets",
    "better", "Higher ROA = more efficient use of assets. Core profitability signal."))

_r(Factor("ROE", "Return on Equity", FactorCategory.PROFITABILITY,
    "quantm.factor.roe.ROE", "Net income divided by shareholders' equity",
    "better", "Higher ROE = better equity efficiency. Watch for leverage-driven ROE inflation."))

_r(Factor("ROIC", "Return on Invested Capital", FactorCategory.PROFITABILITY,
    "quantm.factor.roic.ROIC",
    "NOPAT divided by invested capital (equity + debt − excess cash)",
    "better", "Best profitability metric – measures returns on ALL capital regardless of financing."))

_r(Factor("ROICxRnD", "ROIC excluding R&D", FactorCategory.PROFITABILITY,
    "quantm.factor.roic.ROICxRnD",
    "ROIC calculated by capitalising R&D instead of expensing it",
    "better", "Adjusts ROIC for R&D-intensive firms. Better for tech/pharma comparisons."))

_r(Factor("IncROIC", "Incremental ROIC", FactorCategory.PROFITABILITY,
    "quantm.factor.roic.Incremental_ROIC",
    "Change in NOPAT divided by change in invested capital",
    "better", "Measures marginal return on new investment. Key for growth assessment."))

_r(Factor("PreTaxROA", "Pre-Tax ROA", FactorCategory.PROFITABILITY,
    "quantm.factor.roa.PreTaxROA", "Pre-tax income divided by total assets",
    "better", "ROA before tax effects – better for cross-jurisdiction comparison."))

_r(Factor("PostTaxROA", "Post-Tax ROA", FactorCategory.PROFITABILITY,
    "quantm.factor.roa.PostTaxROA", "Post-tax income divided by total assets",
    "better", "Actual after-tax return on the asset base."))

_r(Factor("NOPAT", "Net Operating Profit After Tax", FactorCategory.PROFITABILITY,
    "quantm.factor.profitability.NOPAT",
    "Operating profit × (1 − tax rate). Numerator for ROIC.",
    "better", "Core operating earnings independent of capital structure."))

_r(Factor("EffTaxRate", "Effective Tax Rate", FactorCategory.PROFITABILITY,
    "quantm.factor.income.EffectiveTaxRate",
    "Income taxes paid divided by pre-tax income",
    "neutral", "Unusually low rates may signal tax avoidance risk; high rates compress returns."))

# ── Growth ───────────────────────────────────────────────────────────

_r(Factor("SG", "Sales Growth", FactorCategory.GROWTH,
    "quantm.factor.stablegrowth.SalesGrowth", "Revenue growth rate",
    "better", "Top-line growth signal. Sustained SG indicates market share gains."))

_r(Factor("EG", "Earnings Growth", FactorCategory.GROWTH,
    "quantm.factor.stablegrowth.EarningsGrowth", "Earnings growth rate",
    "better", "Bottom-line growth. High EG + high SG = operating leverage."))

_r(Factor("CFG", "Cash Flow Growth", FactorCategory.GROWTH,
    "quantm.factor.stablegrowth.CashFlowGrowth",
    "Cash flow from operations growth rate. Value is in decimal percent (1.20 = 120% increase).",
    "better", "Cash-basis growth confirmation. Divergence from EG signals accrual issues."))

_r(Factor("SalesYoYGrw", "Sales Growth YoY", FactorCategory.GROWTH,
    "quantm.factor.sales.SalesYoYGrowth",
    "Year-on-year revenue growth. Value is in decimal percent (1.20 = 120% increase).",
    "better", "Annual revenue growth eliminates seasonality. Check for base-effect distortions."))

_r(Factor("EGYoY", "Earnings Growth YoY", FactorCategory.GROWTH,
    "quantm.factor.earnings.EarningsGrowthYoY",
    "LTM percent change of net income before extraordinary items. Decimal percent (1.20 = 120%).",
    "better", "Year-on-year earnings trajectory. Accelerating EGYoY is a strong signal."))

_r(Factor("RnDG", "R&D Growth", FactorCategory.GROWTH,
    "quantm.factor.stablegrowth.RnDGrowth", "Growth rate of R&D expenditures",
    "better", "Rising R&D spending signals investment in future capabilities. Key for tech."))

# ── Quality / Accruals ──────────────────────────────────────────────

_r(Factor("COA", "Current Operating Accruals", FactorCategory.QUALITY,
    "quantm.factor.accrual.COA",
    "Accrual component of earnings (non-cash portion of income)",
    "worse", "LOWER COA = higher earnings quality. High accruals often precede earnings reversals."))

_r(Factor("NEI", "Net Equity Issuance", FactorCategory.QUALITY,
    "quantm.factor.nei.NEI",
    "Net shares issued (issuance minus buybacks) as a fraction of shares outstanding",
    "worse", "LOWER/negative NEI = buybacks (positive signal). High issuance = dilution risk."))

# ── Surprise / Revision ─────────────────────────────────────────────

_r(Factor("ESurprise", "Earnings Surprise", FactorCategory.SURPRISE_REVISION,
    "quantm.factor.surprise.EarningsSurprise",
    "Actual earnings minus consensus estimate, scaled by price",
    "better", "Positive surprise = company beat expectations. Triggers post-earnings drift."))

_r(Factor("SSurprise", "Sales Surprise", FactorCategory.SURPRISE_REVISION,
    "quantm.factor.surprise.SalesSurprise",
    "Actual revenue minus consensus estimate",
    "better", "Revenue beats are harder to manipulate than earnings beats."))

_r(Factor("CFSurprise", "Cash Flow Surprise", FactorCategory.SURPRISE_REVISION,
    "quantm.factor.surprise.CashFlowSurprise",
    "Actual cash flow minus estimate",
    "better", "Cash flow beats confirm earnings quality."))

_r(Factor("E_Rev", "Earnings Revision", FactorCategory.SURPRISE_REVISION,
    "quantm.factor.revision.EarningsRevision",
    "4-month change in FY1/FY2/FY3 earnings estimates scaled by price",
    "better", "Positive revisions = analysts raising estimates. Strong momentum predictor."))

_r(Factor("E_Diff", "Earnings Diffusion", FactorCategory.SURPRISE_REVISION,
    "quantm.factor.diffusion.EarningsDiffusion",
    "Number of upward estimate revisions minus downward, scaled by total estimates (FY1-FY3)",
    "better", "Breadth of estimate changes. Positive diffusion = broad analyst optimism."))

# ── Cash Flow ────────────────────────────────────────────────────────

_r(Factor("FCFA", "Free Cash Flow to Assets", FactorCategory.CASH_FLOW,
    "quantm.factor.freecashflow.FCFA",
    "Free cash flow divided by total assets",
    "better", "Asset-normalised FCF generation. Better cross-sector comparison than absolute FCF."))

_r(Factor("CFO12M", "Cash from Operations 12M", FactorCategory.CASH_FLOW,
    "quantm.factor.freecashflow.CFO12M",
    "Trailing 12-month cash flow from operations",
    "better", "Total operating cash generation. Compare to net income to assess quality."))

_r(Factor("GCFO", "Gross Cash Flow from Operations", FactorCategory.CASH_FLOW,
    "quantm.factor.freecashflow.GCFO",
    "Gross (pre-capex) cash flow from operations",
    "better", "Operating cash before reinvestment. Shows raw earning power."))

# ── Risk & Momentum ─────────────────────────────────────────────────

_r(Factor("Beta", "Beta", FactorCategory.RISK_MOMENTUM,
    "quantm.factor.beta.Beta",
    "5-year beta estimated from weekly observations with equal weights",
    "neutral", "Market sensitivity. Beta > 1 = amplifies market moves. Key for portfolio construction."))

_r(Factor("BetaVol", "Beta Volatility", FactorCategory.RISK_MOMENTUM,
    "quantm.factor.volatility.BetaVolatility",
    "Volatility (instability) of the beta estimate over time",
    "worse", "High BetaVol = unreliable risk profile. Makes position sizing harder."))

_r(Factor("PM12xOMR", "Price Momentum 12M ex-1M", FactorCategory.RISK_MOMENTUM,
    "quantm.factor.momentum.PriceMomentum12ExOMR",
    "12-month price return excluding the most recent month",
    "better", "Classic momentum factor. Excludes last month to avoid short-term reversal noise."))

_r(Factor("OS", "Option Skew", FactorCategory.RISK_MOMENTUM,
    "quantm.factor.skew.OptionSkew",
    "Skew in options implied volatility surface",
    "neutral", "High skew = market pricing in tail risk. Useful for sentiment/fear assessment."))

# ── Balance Sheet ────────────────────────────────────────────────────

_r(Factor("TotalAsset", "Total Assets", FactorCategory.BALANCE_SHEET,
    "quantm.factor.asset.TotalAsset", "Total assets on the balance sheet",
    "neutral", "Size proxy. Use for normalisation and cross-company scaling."))

_r(Factor("NetAsset", "Net Assets", FactorCategory.BALANCE_SHEET,
    "quantm.factor.asset.NetAsset", "Total assets minus total liabilities",
    "better", "Book value of equity. Negative = distressed."))

_r(Factor("AvgNetAsset", "Average Net Assets", FactorCategory.BALANCE_SHEET,
    "quantm.factor.asset.AvgNetAsset", "Average net assets over the period",
    "better", "Smoothed NAV. Better denominator for ratios than point-in-time NAV."))

_r(Factor("TotalDebt", "Total Debt", FactorCategory.BALANCE_SHEET,
    "quantm.factor.debt.TotalDebt", "Total short-term + long-term debt",
    "neutral", "Absolute debt level. Normalise by assets or EBITDA to assess burden."))

_r(Factor("TotalLiabilities", "Total Liabilities", FactorCategory.BALANCE_SHEET,
    "quantm.factor.asset.TotalLiabilities",
    "All liabilities including debt, payables, provisions",
    "neutral", "Broader than TotalDebt. Compare to TotalAsset for solvency assessment."))

_r(Factor("APIC", "Additional Paid-In Capital", FactorCategory.BALANCE_SHEET,
    "quantm.factor.capital.AdditionalPaidInCapital",
    "Capital received from share issuance above par value",
    "neutral", "High APIC with low retained earnings = funded by equity issuance, not profits."))

# ── Leverage ─────────────────────────────────────────────────────────

_r(Factor("TDTA", "Debt to Assets", FactorCategory.LEVERAGE,
    "quantm.factor.leverage.DebtToAsset",
    "Total debt divided by total assets",
    "worse", "Higher = more leverage risk. >0.5 is elevated. Cross-check with interest coverage."))

# ── Size ─────────────────────────────────────────────────────────────

_r(Factor("MktCapMMCmpyUSD", "Market Cap (USD millions)", FactorCategory.SIZE,
    "quantm.factor.size.MktCapMMCmpyUSD",
    "Market capitalisation of the company in USD millions (Bloomberg/DataStream)",
    "neutral", "Core size measure. Small caps (<$2B) have higher risk premia but also higher volatility."))

_r(Factor("LastPrice", "Last Price", FactorCategory.SIZE,
    "quantm.factor.size.LastPrice", "Most recent stock price",
    "neutral", "Raw price level. Low absolute price ≠ cheap (use ratios instead)."))

_r(Factor("SharesOutCmpy", "Shares Outstanding", FactorCategory.SIZE,
    "quantm.factor.size.SharesOutCmpy",
    "Total shares outstanding for the company",
    "neutral", "Check trend over time – rising = dilution, falling = buybacks."))

# ── R&D / Innovation ────────────────────────────────────────────────

_r(Factor("RnDP", "R&D to Price", FactorCategory.RND_INNOVATION,
    "quantm.factor.rnd.RnDP", "R&D spending divided by market cap",
    "better", "R&D 'yield'. High RnDP = market undervaluing R&D investment. Tech alpha signal."))

_r(Factor("RnDS", "R&D to Sales", FactorCategory.RND_INNOVATION,
    "quantm.factor.rnd.RnDS", "R&D spending as a fraction of revenue",
    "neutral", "R&D intensity. High for tech/pharma. Compare within sector only."))

_r(Factor("RnDA", "R&D to Assets", FactorCategory.RND_INNOVATION,
    "quantm.factor.rnd.RnDA", "R&D expenditure divided by total assets",
    "neutral", "R&D intensity normalised by asset base."))

_r(Factor("RnDInv", "R&D Investment", FactorCategory.RND_INNOVATION,
    "quantm.factor.rnd.RnDInv", "Absolute R&D investment level",
    "neutral", "Absolute spending. Normalise by size for comparison."))

# ── Income / Dividend ────────────────────────────────────────────────

_r(Factor("Dividends", "Dividends", FactorCategory.INCOME_DIVIDEND,
    "quantm.factor.dividend.Dividends", "Total dividends paid",
    "neutral", "Absolute payout. Use DP (dividend yield) for comparison."))

_r(Factor("IntExp", "Interest Expense", FactorCategory.INCOME_DIVIDEND,
    "quantm.factor.expense.InterestExpense", "Total interest expense",
    "worse", "Higher = bigger debt burden. Compare to EBITDA for coverage ratio."))

_r(Factor("GrIntExp", "Gross Interest Expense", FactorCategory.INCOME_DIVIDEND,
    "quantm.factor.expense.GrossInterestExpense", "Gross interest expense before offsets",
    "worse", "Full interest cost before netting interest income."))

_r(Factor("StckComp", "Stock-Based Compensation", FactorCategory.INCOME_DIVIDEND,
    "quantm.factor.revenue.StockBasedCompensation",
    "Non-cash compensation expense from equity grants",
    "worse", "High SBC dilutes shareholders. Add back to earnings but track dilution separately."))

_r(Factor("StckPur", "Stock Purchases (Buybacks)", FactorCategory.INCOME_DIVIDEND,
    "quantm.factor.value.StockPurchases", "Value of shares repurchased",
    "better", "Aggressive buybacks signal management confidence and reduce share count."))

_r(Factor("DefRevLT", "Deferred Revenue (LT)", FactorCategory.INCOME_DIVIDEND,
    "quantm.factor.revenue.DeferredRevenueLT", "Long-term deferred revenue",
    "better", "Growing deferred revenue = strong forward revenue visibility (e.g. subscriptions)."))

_r(Factor("DefRevCL", "Deferred Revenue (Current)", FactorCategory.INCOME_DIVIDEND,
    "quantm.factor.revenue.DeferredRevenueCurrentLiabilities",
    "Current-period deferred revenue",
    "better", "Short-term revenue already contracted but not yet recognised."))

# ── Macro ────────────────────────────────────────────────────────────

_r(Factor("IntRate", "Interest Rate", FactorCategory.MACRO,
    "quantm.factor.interest.InterestRate", "Prevailing interest rate",
    "neutral", "Macro reference. Rising rates hurt growth/duration assets."))

_r(Factor("GDPDeflator", "GDP Deflator", FactorCategory.MACRO,
    "quantm.factor.macro.GDPDeflator", "Broad price deflator for nominal GDP",
    "neutral", "Inflation proxy. Faster-rising deflator = tightening conditions."))

_r(Factor("NomGDP", "Nominal GDP", FactorCategory.MACRO,
    "quantm.factor.macro.NominalGDP", "Nominal gross domestic product",
    "neutral", "Aggregate economic size. Corporate profits track nominal GDP long-term."))

_r(Factor("TotalValue", "Total Value", FactorCategory.MACRO,
    "quantm.factor.macro.TotalValue", "Total market/asset class value",
    "neutral", "Macro aggregate. Use for market-to-GDP or Buffett-indicator style analysis."))

_r(Factor("DepAmrtz", "Depreciation & Amortization", FactorCategory.MACRO,
    "quantm.factor.macro.DepreciationAmortization",
    "Depreciation and amortisation charges",
    "neutral", "Add back to earnings for EBITDA. Rising D&A signals heavy past capex."))

# ── Sentiment / Alt Data ────────────────────────────────────────────

_r(Factor("SI", "Short Interest", FactorCategory.SENTIMENT_ALT,
    "quantm.factor.shortinterest.ShortInterest",
    "Ratio of shares sold short to total shares outstanding (Source: Data Explorers)",
    "worse", "High SI = bearish positioning. Can also signal short-squeeze potential."))

_r(Factor("TrxAnlstSntmnt", "Transcript Analyst Sentiment", FactorCategory.SENTIMENT_ALT,
    "quantm.factor.nlp.TranscriptAnalystSentiment",
    "Analyst question section sentiment score from earnings calls – higher = more positive (Source: S&P Transcripts)",
    "better", "NLP-derived sentiment from analyst Q&A. Low sentiment = skeptical Street."))

_r(Factor("TrxExecSntmnt", "Transcript Executive Sentiment", FactorCategory.SENTIMENT_ALT,
    "quantm.factor.nlp.TranscriptExecutiveSentiment",
    "Executive presentation section sentiment from earnings calls – higher = more positive (Source: S&P Transcripts)",
    "better", "Management tone. Divergence from analyst sentiment is a red flag."))

_r(Factor("CrwdNetScore", "Crowding Net Score", FactorCategory.SENTIMENT_ALT,
    "quantm.factor.score.CrowdingNetScore",
    "Calculated from position data: (long rank decile − short rank decile). Range −100 to +100. (Source: JPM Prime Brokerage)",
    "neutral", "Institutional positioning. Extreme +100 = overcrowded long; −100 = heavy short."))

_r(Factor("AG_MM_5Y", "Asset Growth (M&M) 5-Year", FactorCategory.GROWTH,
    "quantm.factor.assetgrowth.MillerModiglianiAssetGrowth5Yr",
    "5-year Miller-Modigliani asset growth rate",
    "worse", "Historically, LOW asset growth firms outperform. High growth = empire building risk."))

_r(Factor("MinrInt", "Minority Interest", FactorCategory.BALANCE_SHEET,
    "quantm.factor.macro.MinorityInterest", "Minority interest on the balance sheet",
    "neutral", "Non-controlling interest. Large value = complex corporate structure."))

_r(Factor("PrefStck", "Preferred Stock", FactorCategory.BALANCE_SHEET,
    "quantm.factor.macro.PreferredStock", "Preferred stock on the balance sheet",
    "neutral", "Senior to common equity. Large preferred = more claims ahead of common shareholders."))


# ═══════════════════════════════════════════════════════════════════════
#  QUERY HELPERS
# ═══════════════════════════════════════════════════════════════════════

def get_factors_by_category(category: FactorCategory) -> list[Factor]:
    """Return all factors in a given category."""
    return [f for f in FACTORS.values() if f.category == category]


def get_factor(factor_id: str) -> Factor | None:
    """Look up a single factor by its short ID."""
    return FACTORS.get(factor_id)


def get_all_factor_ids() -> list[str]:
    """Return all registered factor IDs."""
    return list(FACTORS.keys())


def get_category_summary() -> dict[str, list[str]]:
    """Return {category_name: [factor_ids]} mapping."""
    out: dict[str, list[str]] = {}
    for f in FACTORS.values():
        out.setdefault(f.category.value, []).append(f.factor_id)
    return out


def format_factor_brief(factor_id: str) -> str:
    """One-line human-readable summary of a factor."""
    f = FACTORS.get(factor_id)
    if not f:
        return f"Unknown factor: {factor_id}"
    direction = {"better": "↑ higher is better", "worse": "↓ lower is better", "neutral": "— directionally neutral"}
    return f"{f.factor_id} ({f.name}): {f.description} [{direction.get(f.higher_is, '')}]"
