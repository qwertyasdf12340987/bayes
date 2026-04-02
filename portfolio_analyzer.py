"""
portfolio_analyzer.py
---------------------
Measures a stock portfolio's:
  1. Factor exposures  — Fama-French 5-factor + Momentum regressions,
                         plus industry (sector ETF) regressions
  2. Covariance structure — pairwise stock covariances, correlations,
                            and contribution to portfolio volatility

Data sources
  - yfinance : adjusted stock price history
  - requests : Ken French's factor library (FF5 + Momentum), downloaded
               directly as CSV zip files from the Dartmouth data library
"""

from __future__ import annotations

import io
import warnings
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm
import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)


def _yf_download(*args, **kwargs) -> pd.DataFrame:
    """Wrapper around yf.download that always returns flat (non-MultiIndex) columns.
    Newer yfinance versions return MultiIndex columns even for a single ticker,
    which breaks code that expects raw["Close"] to be a Series."""
    df = yf.download(*args, **kwargs)
    if isinstance(df.columns, pd.MultiIndex):
        if df.columns.get_level_values(1).nunique() == 1:
            # Single ticker — drop the ticker level so columns are just ["Close","Open",…]
            df.columns = df.columns.droplevel(1)
    return df


# ---------------------------------------------------------------------------
# Sector ETFs used as industry factor proxies
# ---------------------------------------------------------------------------
SECTOR_ETFS: Dict[str, str] = {
    "Technology":          "XLK",
    "Healthcare":          "XLV",
    "Financials":          "XLF",
    "Consumer Disc.":      "XLY",
    "Consumer Staples":    "XLP",
    "Energy":              "XLE",
    "Utilities":           "XLU",
    "Materials":           "XLB",
    "Industrials":         "XLI",
    "Real Estate":         "XLRE",
    "Communication":       "XLC",
}

# Ken French data library — direct CSV zip URLs
_KF_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
FF5_URL  = f"{_KF_BASE}/F-F_Research_Data_5_Factors_2x3_CSV.zip"
MOM_URL  = f"{_KF_BASE}/F-F_Momentum_Factor_CSV.zip"


def _fetch_french_csv(url: str) -> pd.DataFrame:
    """
    Download a Ken French CSV zip, extract the monthly data section,
    and return a DataFrame with a DatetimeIndex (end-of-month).

    French CSV format:
      - Variable number of description header lines
      - Monthly data rows: YYYYMM  col1  col2 ...
      - Annual data rows:  YYYY    col1  col2 ...  (we stop before these)
    Values are in percent; caller converts to decimal if needed.
    """
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_name = next(n for n in zf.namelist() if n.endswith(".CSV") or n.endswith(".csv"))
        raw_text = zf.read(csv_name).decode("utf-8", errors="replace")

    # Parse: collect only rows whose first token is a 6-digit YYYYMM date
    header: Optional[list] = None
    rows: list = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(",")
        if len(parts[0].strip()) == 6 and parts[0].strip().isdigit():
            rows.append(parts)
        elif rows:
            # First non-data line after data started → annual section; stop
            break
        else:
            # Still in header; last non-empty line before data is the column header
            candidate = [p.strip() for p in parts if p.strip()]
            if candidate:
                header = candidate

    if not rows:
        raise ValueError(f"No monthly data found in {url}")

    df = pd.DataFrame(rows)
    # First column = YYYYMM date; remaining = factor values
    df.columns = ["Date"] + (header if header else [f"col{i}" for i in range(1, len(df.columns))])
    df["Date"] = pd.to_datetime(df["Date"].str.strip(), format="%Y%m") + pd.offsets.MonthEnd(0)
    df = df.set_index("Date")
    df = df.apply(pd.to_numeric, errors="coerce").dropna(how="all")
    return df


# ---------------------------------------------------------------------------
# PortfolioAnalyzer
# ---------------------------------------------------------------------------
class PortfolioAnalyzer:
    """
    Parameters
    ----------
    tickers : list of str
        Stock tickers (e.g. ['AAPL', 'MSFT', 'NVDA']).
    weights : list of float, optional
        Portfolio weights. Defaults to equal-weight. Need not sum to 1
        (they are normalised internally).
    start_date : str, optional
        'YYYY-MM-DD'. Defaults to 5 years ago.
    end_date : str, optional
        'YYYY-MM-DD'. Defaults to today.
    frequency : {'monthly', 'daily'}
        Return frequency used for all analyses. Monthly is strongly
        recommended for factor regressions.
    """

    def __init__(
        self,
        tickers: List[str],
        weights: Optional[List[float]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: str = "monthly",
    ) -> None:
        self.tickers = [t.upper() for t in tickers]
        n = len(self.tickers)

        if weights is None:
            self.weights = np.ones(n) / n
        else:
            w = np.asarray(weights, dtype=float)
            self.weights = w / w.sum()

        today = datetime.today()
        self.end_date   = end_date   or today.strftime("%Y-%m-%d")
        self.start_date = start_date or (today - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
        self.frequency  = frequency

        # cached data
        self._prices:           Optional[pd.DataFrame] = None
        self._returns:          Optional[pd.DataFrame] = None
        self._portfolio_returns: Optional[pd.Series]   = None
        self._ff_factors:       Optional[pd.DataFrame] = None
        self._sector_returns:   Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def fetch_prices(self) -> pd.DataFrame:
        """Download adjusted close prices for all tickers via yfinance."""
        print(f"Fetching prices for: {', '.join(self.tickers)} ...")
        raw = _yf_download(
            self.tickers,
            start=self.start_date,
            end=self.end_date,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        if len(self.tickers) == 1:
            prices = raw[["Close"]].rename(columns={"Close": self.tickers[0]})
        else:
            prices = raw["Close"][self.tickers]

        self._prices = prices.dropna(how="all")
        return self._prices

    @property
    def returns(self) -> pd.DataFrame:
        """Periodic (daily or monthly) simple returns for each ticker."""
        if self._returns is not None:
            return self._returns

        if self._prices is None:
            self.fetch_prices()

        daily = self._prices.pct_change().dropna(how="all")
        if self.frequency == "monthly":
            self._returns = daily.resample("ME").apply(
                lambda x: (1 + x).prod() - 1
            )
        else:
            self._returns = daily
        return self._returns

    @property
    def portfolio_returns(self) -> pd.Series:
        """Weighted portfolio returns."""
        if self._portfolio_returns is None:
            self._portfolio_returns = (self.returns * self.weights).sum(axis=1)
            self._portfolio_returns.name = "Portfolio"
        return self._portfolio_returns

    def fetch_ff_factors(self, include_momentum: bool = True) -> pd.DataFrame:
        """
        Download Fama-French 5-factor data (+ optional momentum) directly
        from Kenneth French's Dartmouth data library as CSV zip files.
        """
        print("Fetching Fama-French factor data ...")
        ff5 = _fetch_french_csv(FF5_URL) / 100  # percent → decimal

        # Trim to requested date range
        ff5 = ff5.loc[self.start_date : self.end_date]

        if include_momentum:
            mom = _fetch_french_csv(MOM_URL) / 100
            mom.columns = ["MOM"]
            ff5 = ff5.join(mom, how="inner")
            ff5 = ff5.loc[self.start_date : self.end_date]

        # Rename RF column if it came through with extra spaces
        ff5.columns = [c.strip() for c in ff5.columns]

        self._ff_factors = ff5
        return self._ff_factors

    def fetch_sector_returns(self) -> pd.DataFrame:
        """Download sector ETF returns for industry exposure analysis."""
        tickers = list(SECTOR_ETFS.values())
        print(f"Fetching sector ETF data ({len(tickers)} sectors) ...")
        raw = _yf_download(
            tickers,
            start=self.start_date,
            end=self.end_date,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        daily = raw["Close"].pct_change().dropna(how="all")
        if self.frequency == "monthly":
            sector_rets = daily.resample("ME").apply(
                lambda x: (1 + x).prod() - 1
            )
        else:
            sector_rets = daily

        ticker_to_sector = {v: k for k, v in SECTOR_ETFS.items()}
        sector_rets = sector_rets.rename(columns=ticker_to_sector)
        self._sector_returns = sector_rets
        return self._sector_returns

    # ------------------------------------------------------------------
    # Regression helper
    # ------------------------------------------------------------------

    def _run_ols(self, y: pd.Series, X: pd.DataFrame) -> dict:
        """
        Align y and X, run OLS with a constant, and return a structured
        results dictionary.
        """
        data = pd.concat([y, X], axis=1).dropna()
        y_fit = data.iloc[:, 0]
        X_fit = sm.add_constant(data.iloc[:, 1:])

        model = sm.OLS(y_fit, X_fit).fit(cov_type="HC3")  # robust SEs

        periods = 12 if self.frequency == "monthly" else 252
        alpha_ann = (1 + model.params["const"]) ** periods - 1

        return {
            "alpha":            model.params["const"],
            "alpha_annualized": alpha_ann,
            "alpha_tstat":      model.tvalues["const"],
            "alpha_pval":       model.pvalues["const"],
            "betas":  model.params.drop("const").to_dict(),
            "tstats": model.tvalues.drop("const").to_dict(),
            "pvals":  model.pvalues.drop("const").to_dict(),
            "r_squared":     model.rsquared,
            "r_squared_adj": model.rsquared_adj,
            "n_obs": int(model.nobs),
        }

    # ------------------------------------------------------------------
    # Factor analysis
    # ------------------------------------------------------------------

    def factor_analysis(
        self,
        include_momentum: bool = True,
        per_stock: bool = True,
    ) -> dict:
        """
        Regress portfolio (and optionally each stock) returns on the
        Fama-French 5-factor model + momentum.

        Returns a dict with keys 'portfolio' and (if per_stock) 'stocks'.
        """
        if self._ff_factors is None:
            self.fetch_ff_factors(include_momentum=include_momentum)

        ff = self._ff_factors.copy()
        factors = [c for c in ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM"]
                   if c in ff.columns]

        def _to_eom(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
            """Snap any DatetimeIndex to end-of-month so it aligns with FF data."""
            return idx.to_period("M").to_timestamp("M")

        # Portfolio excess returns
        port = self.portfolio_returns.copy()
        port.index = _to_eom(port.index)
        port_excess = port - ff["RF"]

        results: dict = {}
        results["portfolio"] = self._run_ols(port_excess, ff[factors])

        if per_stock:
            stock_rets = self.returns.copy()
            stock_rets.index = _to_eom(stock_rets.index)
            results["stocks"] = {}
            for ticker in self.tickers:
                excess = stock_rets[ticker] - ff["RF"]
                results["stocks"][ticker] = self._run_ols(excess, ff[factors])

        return results

    def industry_analysis(self) -> dict:
        """
        Regress portfolio returns on sector ETF returns to measure industry
        (sector) exposures.

        Uses OLS (not constrained); betas reflect marginal sector tilts.
        """
        if self._sector_returns is None:
            self.fetch_sector_returns()

        def _to_eom(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
            return idx.to_period("M").to_timestamp("M")

        port = self.portfolio_returns.copy()
        sector = self._sector_returns.copy()

        if self.frequency == "monthly":
            port.index   = _to_eom(port.index)
            sector.index = _to_eom(sector.index)

        return self._run_ols(port, sector)

    # ------------------------------------------------------------------
    # Covariance analysis
    # ------------------------------------------------------------------

    def covariance_matrix(self, annualized: bool = True) -> pd.DataFrame:
        """Pairwise covariance matrix of stock returns."""
        cov = self.returns.cov()
        if annualized:
            periods = 12 if self.frequency == "monthly" else 252
            cov = cov * periods
        return cov

    def correlation_matrix(self) -> pd.DataFrame:
        """Pairwise Pearson correlation matrix of stock returns."""
        return self.returns.corr()

    def stock_volatilities(self, annualized: bool = True) -> pd.Series:
        """Annualised return volatility for each stock."""
        periods = 12 if self.frequency == "monthly" else 252
        vols = self.returns.std()
        return vols * np.sqrt(periods) if annualized else vols

    def portfolio_volatility(self) -> float:
        """Annualised portfolio volatility (w' Σ w) ^ 0.5."""
        cov = self.covariance_matrix(annualized=True)
        return float(np.sqrt(self.weights @ cov.values @ self.weights))

    def marginal_risk_contributions(self) -> pd.Series:
        """
        Each stock's percentage contribution to total portfolio variance.
        Sums to 100%.
        """
        cov = self.covariance_matrix(annualized=True)
        port_var = self.weights @ cov.values @ self.weights
        mrc = (cov.values @ self.weights) * self.weights / port_var
        return pd.Series(mrc, index=self.tickers, name="Risk Contribution")

    # ------------------------------------------------------------------
    # Performance analytics
    # ------------------------------------------------------------------

    def _periods_per_year(self) -> int:
        return 12 if self.frequency == "monthly" else 252

    def _rf_series(self) -> pd.Series:
        """Risk-free rate per period from FF data (or zero if unavailable)."""
        try:
            if self._ff_factors is None:
                self.fetch_ff_factors(include_momentum=False)
            ff = self._ff_factors.copy()
            rf = ff["RF"].copy()
            port = self.portfolio_returns.copy()
            port.index = port.index.to_period("M").to_timestamp("M")
            rf.index   = rf.index.to_period("M").to_timestamp("M")
            return rf.reindex(port.index).fillna(0)
        except Exception:
            return pd.Series(0.0, index=self.portfolio_returns.index)

    def sharpe_ratio(self) -> float:
        """Annualised Sharpe ratio using FF risk-free rate."""
        ppy = self._periods_per_year()
        ret = self.portfolio_returns
        rf  = self._rf_series()
        excess = ret.values - rf.values
        if excess.std() == 0:
            return 0.0
        return float((excess.mean() / excess.std()) * np.sqrt(ppy))

    def sortino_ratio(self) -> float:
        """Annualised Sortino ratio (penalises only downside deviation)."""
        ppy = self._periods_per_year()
        ret = self.portfolio_returns
        rf  = self._rf_series()
        excess = ret.values - rf.values
        downside = excess[excess < 0]
        if len(downside) == 0 or downside.std() == 0:
            return float("inf")
        downside_std = np.sqrt((downside ** 2).mean())
        return float((excess.mean() / downside_std) * np.sqrt(ppy))

    def max_drawdown(self) -> dict:
        """Maximum drawdown and the dates of peak and trough."""
        cum = (1 + self.portfolio_returns).cumprod()
        rolling_max = cum.cummax()
        drawdown = (cum - rolling_max) / rolling_max
        trough_idx = drawdown.idxmin()
        peak_idx   = cum[:trough_idx].idxmax()
        return {
            "max_drawdown": float(drawdown.min()),
            "peak_date":    peak_idx,
            "trough_date":  trough_idx,
        }

    def calmar_ratio(self) -> float:
        """Annualised return divided by absolute max drawdown."""
        ppy  = self._periods_per_year()
        ann_ret = (1 + self.portfolio_returns.mean()) ** ppy - 1
        mdd  = abs(self.max_drawdown()["max_drawdown"])
        return float(ann_ret / mdd) if mdd > 0 else float("inf")

    def var(self, confidence: float = 0.95) -> float:
        """Historical Value-at-Risk (single-period, annualised scaling)."""
        return float(np.percentile(self.portfolio_returns, (1 - confidence) * 100))

    def cvar(self, confidence: float = 0.95) -> float:
        """Conditional VaR / Expected Shortfall at given confidence."""
        v   = self.var(confidence)
        ret = self.portfolio_returns
        return float(ret[ret <= v].mean())

    def annualised_return(self) -> float:
        ppy = self._periods_per_year()
        return float((1 + self.portfolio_returns.mean()) ** ppy - 1)

    def benchmark_returns(self, benchmark: str = "SPY") -> pd.Series:
        """Fetch and return the benchmark's periodic returns."""
        raw = _yf_download(benchmark, start=self.start_date, end=self.end_date,
                          auto_adjust=True, progress=False)
        daily = raw["Close"].pct_change().dropna()
        if self.frequency == "monthly":
            b = daily.resample("ME").apply(lambda x: (1 + x).prod() - 1)
        else:
            b = daily
        b.name = benchmark
        return b

    def rolling_factor_betas(
        self,
        window: int = 36,
        include_momentum: bool = True,
    ) -> pd.DataFrame:
        """
        Rolling OLS factor betas over a sliding window.
        Returns a DataFrame indexed by date with one column per factor.
        """
        if self._ff_factors is None:
            self.fetch_ff_factors(include_momentum=include_momentum)

        ff      = self._ff_factors.copy()
        factors = [c for c in ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM"]
                   if c in ff.columns]

        def _to_eom(idx):
            return idx.to_period("M").to_timestamp("M")

        port = self.portfolio_returns.copy()
        port.index = _to_eom(port.index)
        excess = (port - ff["RF"]).dropna()

        records = []
        for i in range(window, len(excess) + 1):
            y_w = excess.iloc[i - window: i]
            X_w = ff[factors].reindex(y_w.index).dropna()
            y_w = y_w.reindex(X_w.index)
            if len(y_w) < window // 2:
                continue
            try:
                res = sm.OLS(y_w, sm.add_constant(X_w)).fit()
                row = {"date": y_w.index[-1]}
                row.update(res.params.drop("const").to_dict())
                records.append(row)
            except Exception:
                continue

        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records).set_index("date")
        return df

    # ------------------------------------------------------------------
    # Hedge suggestions
    # ------------------------------------------------------------------

    # Best single-factor ETFs for hedging each FF factor
    HEDGE_ETFS = {
        "Mkt-RF": "SPY",   # market beta
        "SMB":    "IWM",   # small-cap tilt
        "HML":    "IVE",   # value tilt (iShares S&P 500 Value)
        "RMW":    "QUAL",  # profitability / quality
        "CMA":    "USMV",  # conservative investment / min-vol
        "MOM":    "MTUM",  # momentum
    }

    HEDGE_SECTOR_ETFS = {
        "Technology":       "XLK",
        "Healthcare":       "XLV",
        "Financials":       "XLF",
        "Consumer Disc.":   "XLY",
        "Consumer Staples": "XLP",
        "Energy":           "XLE",
        "Utilities":        "XLU",
        "Materials":        "XLB",
        "Industrials":      "XLI",
        "Real Estate":      "XLRE",
        "Communication":    "XLC",
    }

    def hedge_suggestions(
        self,
        ff_results: dict,
        industry_results: Optional[dict] = None,
        portfolio_value: float = 100_000,
        significance_threshold: float = 0.10,
        beta_threshold: float = 0.15,
    ) -> dict:
        """
        Compute positions needed to bring each significant factor beta to zero.

        For each factor where |beta| > beta_threshold and p < significance_threshold:
          1. Get the hedge ETF's own factor betas via FF regression
          2. Compute notional = -(port_beta / etf_beta_to_factor) * portfolio_value
          3. Positive notional = buy, negative = short

        Returns a dict with 'factor_hedges' and 'industry_hedges' lists.
        """
        port_betas = ff_results["portfolio"]["betas"]
        port_pvals = ff_results["portfolio"]["pvals"]

        # ── factor hedges ─────────────────────────────────────────────
        factor_hedges = []
        hedge_tickers = list(set(self.HEDGE_ETFS.values()))

        # Download hedge ETF price data and compute their FF betas
        raw = _yf_download(hedge_tickers, start=self.start_date, end=self.end_date,
                          auto_adjust=True, progress=False)
        if len(hedge_tickers) == 1:
            etf_prices = raw[["Close"]].rename(columns={"Close": hedge_tickers[0]})
        else:
            etf_prices = raw["Close"]

        etf_daily   = etf_prices.pct_change().dropna(how="all")
        etf_monthly = etf_daily.resample("ME").apply(lambda x: (1 + x).prod() - 1)

        ff = self._ff_factors.copy()
        factors = [c for c in ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM"]
                   if c in ff.columns]

        def _to_eom(idx):
            return idx.to_period("M").to_timestamp("M")

        etf_monthly.index = _to_eom(etf_monthly.index)
        ff.index          = _to_eom(ff.index)

        # Compute factor betas for each hedge ETF
        etf_betas: dict = {}
        for etf in hedge_tickers:
            if etf not in etf_monthly.columns:
                continue
            excess = etf_monthly[etf] - ff["RF"]
            try:
                res = self._run_ols(excess, ff[factors])
                etf_betas[etf] = res["betas"]
            except Exception:
                continue

        # For each factor, compute hedge
        for factor, port_beta in port_betas.items():
            p_val = port_pvals.get(factor, 1.0)
            if abs(port_beta) < beta_threshold or p_val > significance_threshold:
                continue
            if factor not in self.HEDGE_ETFS:
                continue

            hedge_etf = self.HEDGE_ETFS[factor]
            if hedge_etf not in etf_betas:
                continue

            etf_factor_beta = etf_betas[hedge_etf].get(factor, 0)
            if abs(etf_factor_beta) < 0.1:
                continue  # ETF has negligible exposure to this factor

            notional = -(port_beta / etf_factor_beta) * portfolio_value
            direction = "BUY" if notional > 0 else "SHORT"

            # Fetch current price for share count estimate
            try:
                current_px = float(
                    _yf_download(hedge_etf, period="1d", progress=False)["Close"].iloc[-1]
                )
                shares = abs(notional) / current_px
            except Exception:
                current_px, shares = None, None

            factor_hedges.append({
                "factor":       factor,
                "port_beta":    round(port_beta, 3),
                "hedge_etf":    hedge_etf,
                "direction":    direction,
                "notional":     round(abs(notional), 0),
                "current_price": round(current_px, 2) if current_px else None,
                "approx_shares": round(shares, 1) if shares else None,
                "etf_factor_beta": round(etf_factor_beta, 3),
            })

        # ── industry hedges ───────────────────────────────────────────
        industry_hedges = []
        if industry_results:
            ind_betas = industry_results.get("betas", {})
            ind_pvals = industry_results.get("pvals", {})
            for sector, beta in ind_betas.items():
                p_val = ind_pvals.get(sector, 1.0)
                if abs(beta) < beta_threshold or p_val > significance_threshold:
                    continue
                etf = self.HEDGE_SECTOR_ETFS.get(sector)
                if not etf:
                    continue
                notional  = -beta * portfolio_value
                direction = "BUY" if notional > 0 else "SHORT"
                try:
                    current_px = float(
                        _yf_download(etf, period="1d", progress=False)["Close"].iloc[-1]
                    )
                    shares = abs(notional) / current_px
                except Exception:
                    current_px, shares = None, None

                industry_hedges.append({
                    "sector":        sector,
                    "port_beta":     round(beta, 3),
                    "hedge_etf":     etf,
                    "direction":     direction,
                    "notional":      round(abs(notional), 0),
                    "current_price": round(current_px, 2) if current_px else None,
                    "approx_shares": round(shares, 1) if shares else None,
                })

        return {
            "factor_hedges":   factor_hedges,
            "industry_hedges": industry_hedges,
        }

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _stars(pval: float) -> str:
        if pval < 0.01: return "***"
        if pval < 0.05: return "**"
        if pval < 0.10: return "*"
        return ""

    def _print_factor_results(self, r: dict, title: str) -> None:
        freq_label = "months" if self.frequency == "monthly" else "days"
        print(f"\n{'='*62}")
        print(f"  FACTOR ANALYSIS — {title}")
        print(f"{'='*62}")
        print(f"  Obs: {r['n_obs']} {freq_label} | "
              f"R² = {r['r_squared']:.3f} | adj R² = {r['r_squared_adj']:.3f}")
        print(f"\n  {'Factor':<16} {'Beta / α':>9} {'t-stat':>8} {'':>4}")
        print(f"  {'-'*42}")

        alpha_pct = r["alpha_annualized"] * 100
        print(f"  {'Alpha (ann.)':16} {alpha_pct:>8.2f}% "
              f"{r['alpha_tstat']:>8.2f}  {self._stars(r['alpha_pval'])}")

        for factor, beta in r["betas"].items():
            t   = r["tstats"][factor]
            p   = r["pvals"][factor]
            print(f"  {factor:<16} {beta:>9.3f} {t:>8.2f}  {self._stars(p)}")

        print(f"\n  Significance: *** p<0.01  ** p<0.05  * p<0.10")
        print(f"  (Heteroskedasticity-robust standard errors, HC3)")

    def _print_covariance_results(self) -> None:
        cov  = self.covariance_matrix(annualized=True)
        corr = self.correlation_matrix()
        vols = self.stock_volatilities(annualized=True)
        mrc  = self.marginal_risk_contributions()

        print(f"\n{'='*62}")
        print(f"  COVARIANCE ANALYSIS (annualised)")
        print(f"{'='*62}")

        print(f"\n  Stock Volatilities & Risk Contributions:")
        print(f"  {'Ticker':<10} {'Weight':>7} {'Vol (ann.)':>12} {'Risk Contrib':>14}")
        print(f"  {'-'*46}")
        for i, ticker in enumerate(self.tickers):
            print(f"  {ticker:<10} {self.weights[i]:>7.1%} "
                  f"{vols[ticker]*100:>11.2f}%  {mrc[ticker]:>13.1%}")

        print(f"\n  Portfolio Volatility (ann.): {self.portfolio_volatility()*100:.2f}%")

        print(f"\n  Correlation Matrix:")
        print(corr.round(3).to_string())

        if len(self.tickers) > 1:
            print(f"\n  Covariance Matrix (annualised, decimal):")
            print(cov.round(6).to_string())

    # ------------------------------------------------------------------
    # Plots
    # ------------------------------------------------------------------

    def plot_factor_loadings(
        self,
        results: dict,
        title: str = "Portfolio",
        save_path: Optional[str] = None,
    ) -> None:
        """Bar chart of factor betas with approximate 95% confidence intervals."""
        r = results["portfolio"]
        factors = list(r["betas"].keys())
        betas   = [r["betas"][f]  for f in factors]
        tstats  = [r["tstats"][f] for f in factors]
        # CI half-width ≈ |beta / t| * 1.96
        errors  = [abs(b / t) * 1.96 if t != 0 else 0
                   for b, t in zip(betas, tstats)]
        colors  = ["#d62728" if v < 0 else "#1f77b4" for v in betas]

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(factors, betas, color=colors, alpha=0.8,
               yerr=errors, capsize=5,
               error_kw={"elinewidth": 1.5, "ecolor": "black"})
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title(f"Factor Loadings — {title}  (95% CI)", fontsize=13, fontweight="bold")
        ax.set_ylabel("Beta")
        ax.set_xlabel("Factor")

        info = (f"Alpha (ann.): {r['alpha_annualized']*100:.2f}%  "
                f"(t = {r['alpha_tstat']:.2f})\n"
                f"R² = {r['r_squared']:.3f}")
        ax.text(0.02, 0.98, info, transform=ax.transAxes, va="top",
                fontsize=9, bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.6))

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150)
        plt.show()

    def plot_correlation_heatmap(self, save_path: Optional[str] = None) -> None:
        """Annotated heatmap of pairwise stock correlations."""
        corr = self.correlation_matrix()
        n = len(self.tickers)
        fig, ax = plt.subplots(figsize=(max(6, n + 1), max(5, n)))
        sns.heatmap(
            corr, annot=True, fmt=".2f", cmap="RdYlGn",
            center=0, vmin=-1, vmax=1,
            ax=ax, linewidths=0.5, annot_kws={"size": 10},
        )
        ax.set_title("Stock Correlation Matrix", fontsize=13, fontweight="bold")
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150)
        plt.show()

    def plot_stock_factor_heatmap(
        self, results: dict, save_path: Optional[str] = None
    ) -> None:
        """Heatmap of per-stock factor loadings (betas + annualised alpha)."""
        if "stocks" not in results:
            print("Per-stock results not available.")
            return

        rows = {}
        for ticker, r in results["stocks"].items():
            row = {"Alpha (ann.)": r["alpha_annualized"] * 100}
            row.update(r["betas"])
            rows[ticker] = row

        df = pd.DataFrame(rows).T

        n_stocks  = len(df)
        n_factors = len(df.columns)
        fig, ax = plt.subplots(figsize=(max(8, n_factors + 2), max(4, n_stocks + 1)))
        sns.heatmap(
            df, annot=True, fmt=".2f", cmap="RdYlGn",
            center=0, ax=ax, linewidths=0.5, annot_kws={"size": 9},
        )
        ax.set_title("Per-Stock Factor Loadings", fontsize=13, fontweight="bold")
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150)
        plt.show()

    def plot_risk_contributions(self, save_path: Optional[str] = None) -> None:
        """Horizontal bar chart of each stock's % risk contribution."""
        mrc  = self.marginal_risk_contributions() * 100
        vols = self.stock_volatilities() * 100

        fig, axes = plt.subplots(1, 2, figsize=(12, max(4, len(self.tickers))))

        # Risk contributions
        colors = plt.cm.Blues(np.linspace(0.4, 0.85, len(self.tickers)))
        axes[0].barh(mrc.index, mrc.values, color=colors)
        axes[0].set_xlabel("% of Portfolio Variance")
        axes[0].set_title("Risk Contribution", fontweight="bold")
        axes[0].axvline(100 / len(self.tickers), color="red",
                        linestyle="--", linewidth=1, label="Equal-risk")
        axes[0].legend(fontsize=8)
        for i, v in enumerate(mrc.values):
            axes[0].text(v + 0.3, i, f"{v:.1f}%", va="center", fontsize=9)

        # Individual vols
        colors2 = plt.cm.Oranges(np.linspace(0.4, 0.85, len(self.tickers)))
        axes[1].barh(vols.index, vols.values, color=colors2)
        axes[1].set_xlabel("Annualised Volatility (%)")
        axes[1].set_title("Individual Stock Volatility", fontweight="bold")
        axes[1].axvline(self.portfolio_volatility() * 100, color="navy",
                        linestyle="--", linewidth=1, label="Portfolio vol")
        axes[1].legend(fontsize=8)
        for i, v in enumerate(vols.values):
            axes[1].text(v + 0.3, i, f"{v:.1f}%", va="center", fontsize=9)

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150)
        plt.show()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(
        self,
        factor_model: bool = True,
        industry_model: bool = True,
        covariance: bool = True,
        plots: bool = True,
        per_stock: bool = True,
    ) -> None:
        """
        Run all analyses and print results.

        Parameters
        ----------
        factor_model   : run FF5 + momentum factor regression
        industry_model : run sector-ETF industry regression
        covariance     : compute and display covariance / correlation
        plots          : display matplotlib figures
        per_stock      : include per-stock factor regressions
        """
        print("\n" + "=" * 62)
        print("  PORTFOLIO ANALYZER")
        print("=" * 62)
        print(f"  Holdings : {', '.join(f'{t} ({w:.1%})' for t, w in zip(self.tickers, self.weights))}")
        print(f"  Period   : {self.start_date}  to  {self.end_date}")
        print(f"  Frequency: {self.frequency}")

        # Pre-fetch prices (shared by all analyses)
        self.fetch_prices()

        # 1. Fama-French factor analysis
        if factor_model:
            ff_results = self.factor_analysis(
                include_momentum=True, per_stock=per_stock
            )
            self._print_factor_results(ff_results["portfolio"], "Portfolio — FF5 + Momentum")
            if per_stock and len(self.tickers) > 1:
                for ticker in self.tickers:
                    self._print_factor_results(ff_results["stocks"][ticker], ticker)
            if plots:
                self.plot_factor_loadings(ff_results)
                if per_stock and len(self.tickers) > 1:
                    self.plot_stock_factor_heatmap(ff_results)

        # 2. Industry / sector factor analysis
        if industry_model:
            ind_results = self.industry_analysis()
            self._print_factor_results(ind_results, "Portfolio — Industry (Sector ETFs)")
            if plots:
                self.plot_factor_loadings(
                    {"portfolio": ind_results}, title="Industry Factors"
                )

        # 3. Covariance structure
        if covariance:
            self._print_covariance_results()
            if plots:
                if len(self.tickers) > 1:
                    self.plot_correlation_heatmap()
                self.plot_risk_contributions()
