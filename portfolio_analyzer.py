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

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import seaborn as sns
import statsmodels.api as sm
import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)


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
        raw = yf.download(
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
        raw = yf.download(
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
