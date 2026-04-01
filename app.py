"""
app.py — Portfolio Analyzer
Run with:  streamlit run app.py
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import date, timedelta

from db import TradeDB
from portfolio_analyzer import PortfolioAnalyzer

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design tokens ─────────────────────────────────────────────────────────────
BG       = "#0a0a10"
CARD     = "#13131c"
CARD2    = "#1c1c28"
BORDER   = "#2a2a38"
ACCENT   = "#d946ef"   # fuchsia
ACCENT2  = "#a855f7"   # purple
PINK     = "#f472b6"   # chart line color
POS      = "#4ade80"   # green
NEG      = "#fb7185"   # red
TXT      = "#f0f0ff"
TXT2     = "#8888aa"

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
/* ── base ─────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stMain"] {{
    background-color: {BG} !important;
    color: {TXT};
}}
[data-testid="stHeader"] {{
    background-color: {BG} !important;
    border-bottom: 1px solid {BORDER};
}}

/* ── sidebar ──────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: #0d0d16 !important;
    border-right: 1px solid {BORDER} !important;
}}
[data-testid="stSidebar"] * {{ color: {TXT} !important; }}

/* ── metrics ──────────────────────────────── */
[data-testid="metric-container"] {{
    background: {CARD};
    border-radius: 16px;
    border: 1px solid {BORDER};
    padding: 20px 24px !important;
}}
[data-testid="stMetricValue"] {{
    font-size: 26px !important;
    font-weight: 700 !important;
    color: {TXT} !important;
}}
[data-testid="stMetricLabel"] {{
    color: {TXT2} !important;
    font-size: 12px !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}

/* ── tabs ─────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    background: {CARD};
    border-radius: 12px;
    padding: 4px 6px;
    border: 1px solid {BORDER};
    gap: 4px;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px !important;
    color: {TXT2} !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 8px 18px !important;
    border: none !important;
}}
.stTabs [aria-selected="true"] {{
    background: linear-gradient(135deg, {ACCENT}, {ACCENT2}) !important;
    color: white !important;
}}
[data-testid="stTabContent"] {{
    padding-top: 24px;
}}

/* ── buttons ──────────────────────────────── */
.stButton > button {{
    border-radius: 12px !important;
    font-weight: 600 !important;
    border: 1px solid {BORDER} !important;
    background: {CARD2} !important;
    color: {TXT} !important;
    transition: all 0.2s;
}}
.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {ACCENT}, {ACCENT2}) !important;
    border: none !important;
    color: white !important;
}}
.stButton > button:hover {{ opacity: 0.85 !important; }}

/* ── inputs ───────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] div,
[data-testid="stDateInput"] input {{
    background: {CARD2} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
    color: {TXT} !important;
}}

/* ── data tables ──────────────────────────── */
[data-testid="stDataFrame"],
[data-testid="stTable"] {{
    background: {CARD};
    border-radius: 12px;
    border: 1px solid {BORDER};
    overflow: hidden;
}}

/* ── dividers ─────────────────────────────── */
hr {{ border-color: {BORDER} !important; }}

/* ── custom components ────────────────────── */
.kpi-card {{
    background: {CARD};
    border-radius: 16px;
    border: 1px solid {BORDER};
    padding: 20px 24px;
    margin-bottom: 8px;
}}
.section-label {{
    color: {TXT2};
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 12px;
}}
.accent-bar {{
    display: inline-block;
    width: 3px;
    height: 18px;
    background: linear-gradient(180deg, {ACCENT}, {ACCENT2});
    border-radius: 2px;
    margin-right: 10px;
    vertical-align: middle;
}}
.section-header {{
    font-size: 17px;
    font-weight: 700;
    color: {TXT};
    margin: 4px 0 18px 0;
}}
.pill-badge {{
    display: inline-block;
    background: {CARD2};
    border: 1px solid {BORDER};
    border-radius: 20px;
    padding: 3px 10px;
    font-size: 11px;
    color: {TXT2};
    font-weight: 600;
}}
</style>
""", unsafe_allow_html=True)

# ── Plotly dark layout defaults ───────────────────────────────────────────────
_PLOTLY = dict(
    template="plotly_dark",
    paper_bgcolor=CARD,
    plot_bgcolor="#0d0d14",
    font=dict(color=TXT, family="Inter, system-ui, sans-serif", size=12),
    margin=dict(l=16, r=16, t=48, b=16),
)


# ── Database (auto-detects Supabase vs SQLite) ────────────────────────────────
@st.cache_resource
def get_db() -> TradeDB:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except (KeyError, FileNotFoundError):
        url, key = "", ""
    return TradeDB(supabase_url=url, supabase_key=key)


# ── Cached analysis ───────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def run_analysis(tickers_t, weights_t, start_str, end_str, include_industry):
    a = PortfolioAnalyzer(list(tickers_t), list(weights_t), start_str, end_str, "monthly")
    a.fetch_prices()
    ff  = a.factor_analysis(include_momentum=True, per_stock=True)
    ind = a.industry_analysis() if include_industry else None
    bench = a.benchmark_returns("SPY")
    mdd   = a.max_drawdown()
    return {
        "ff":             ff,
        "ind":            ind,
        "cov":            a.covariance_matrix(annualized=True),
        "corr":           a.correlation_matrix(),
        "vols":           a.stock_volatilities(),
        "mrc":            a.marginal_risk_contributions(),
        "port_vol":       a.portfolio_volatility(),
        "returns":        a.returns.copy(),
        "port_returns":   a.portfolio_returns.copy(),
        "benchmark":      bench,
        "sharpe":         a.sharpe_ratio(),
        "sortino":        a.sortino_ratio(),
        "max_drawdown":   mdd["max_drawdown"],
        "calmar":         a.calmar_ratio(),
        "var95":          a.var(0.95),
        "cvar95":         a.cvar(0.95),
        "ann_return":     a.annualised_return(),
        "rolling_betas":  a.rolling_factor_betas(window=36),
        # hedge suggestions computed separately (needs portfolio_value input)
        "_analyzer":      a,   # stored only for hedge computation
    }


# ── Chart helpers ─────────────────────────────────────────────────────────────
def _stars(p):
    if p < 0.01: return "★★★"
    if p < 0.05: return "★★"
    if p < 0.10: return "★"
    return ""


def chart_cumulative(port_ret: pd.Series, returns: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    palette = [PINK, "#818cf8", "#34d399", "#fb923c", "#f472b6",
               "#a78bfa", "#60a5fa", "#fbbf24"]
    for i, col in enumerate(returns.columns):
        cum = (1 + returns[col]).cumprod()
        fig.add_trace(go.Scatter(
            x=cum.index, y=cum.values, mode="lines", name=col,
            line=dict(color=palette[i % len(palette)], width=1.5),
            opacity=0.6,
        ))
    cum_port = (1 + port_ret).cumprod()
    fig.add_trace(go.Scatter(
        x=cum_port.index, y=cum_port.values, mode="lines",
        name="Portfolio", line=dict(color="white", width=2.5),
    ))
    fig.add_hline(y=1, line_dash="dash", line_color=TXT2, line_width=1)
    fig.update_layout(
        **_PLOTLY,
        title=dict(text="Cumulative Returns", font=dict(size=15, color=TXT)),
        yaxis_title="Growth of $1",
        height=340,
        legend=dict(orientation="h", y=-0.2, font=dict(color=TXT2)),
        xaxis=dict(gridcolor=BORDER, showgrid=True),
        yaxis=dict(gridcolor=BORDER, showgrid=True),
    )
    return fig


def chart_factor_bar(result: dict, title: str) -> go.Figure:
    factors = list(result["betas"].keys())
    betas   = [result["betas"][f]  for f in factors]
    tstats  = [result["tstats"][f] for f in factors]
    errors  = [abs(b / t) * 1.96 if t else 0 for b, t in zip(betas, tstats)]
    colors  = [ACCENT if b >= 0 else NEG for b in betas]

    fig = go.Figure(go.Bar(
        x=betas, y=factors, orientation="h",
        marker=dict(color=colors, opacity=0.85,
                    line=dict(color=BORDER, width=1)),
        error_x=dict(type="data", array=errors, visible=True,
                     color=TXT2, thickness=1.5),
        hovertemplate="%{y}: %{x:.3f}<extra></extra>",
    ))
    alpha_pct = result["alpha_annualized"] * 100
    fig.update_layout(
        **_PLOTLY,
        title=dict(text=title, font=dict(size=15, color=TXT)),
        xaxis=dict(title="Beta", gridcolor=BORDER, zerolinecolor=TXT2),
        yaxis=dict(autorange="reversed", gridcolor=BORDER),
        height=380,
        annotations=[dict(
            xref="paper", yref="paper", x=0.99, y=0.02,
            text=f"α = {alpha_pct:.1f}%   t = {result['alpha_tstat']:.1f}   R² = {result['r_squared']:.2f}",
            showarrow=False, font=dict(size=11, color=TXT2),
            align="right",
            bgcolor=CARD2, bordercolor=BORDER, borderwidth=1,
            borderpad=6,
        )],
    )
    return fig


def chart_factor_heatmap(ff_results: dict, tickers: list) -> go.Figure:
    rows = []
    for t in tickers:
        r = ff_results["stocks"][t]
        row = {"Alpha (ann.%)": round(r["alpha_annualized"] * 100, 2)}
        row.update({k: round(v, 3) for k, v in r["betas"].items()})
        rows.append(row)
    df = pd.DataFrame(rows, index=tickers)
    z  = df.values

    fig = go.Figure(go.Heatmap(
        z=z, x=df.columns.tolist(), y=tickers,
        text=[[f"{v:.2f}" for v in row] for row in z],
        texttemplate="%{text}", textfont=dict(size=11, color="white"),
        colorscale=[[0, NEG], [0.5, CARD2], [1, ACCENT]],
        zmid=0, showscale=True,
        hovertemplate="Ticker: %{y}<br>Factor: %{x}<br>Value: %{z:.3f}<extra></extra>",
    ))
    fig.update_layout(
        **_PLOTLY,
        title=dict(text="Per-Stock Factor Loadings", font=dict(size=15, color=TXT)),
        height=max(280, len(tickers) * 50 + 100),
    )
    return fig


def chart_corr_heatmap(corr: pd.DataFrame) -> go.Figure:
    tickers = corr.columns.tolist()
    z       = corr.values
    z_plot  = np.where(np.eye(len(tickers), dtype=bool), np.nan, z)
    fig = go.Figure(go.Heatmap(
        z=z_plot, x=tickers, y=tickers,
        text=[[f"{v:.2f}" for v in row] for row in z],
        texttemplate="%{text}", textfont=dict(size=11, color="white"),
        colorscale=[[0, NEG], [0.5, CARD2], [1, POS]],
        zmid=0, zmin=-1, zmax=1, showscale=True,
        hovertemplate="%{y} / %{x}: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(
        **_PLOTLY,
        title=dict(text="Correlation Matrix", font=dict(size=15, color=TXT)),
        height=max(320, len(tickers) * 60 + 100),
    )
    return fig


def chart_risk_donuts(mrc: pd.Series, weights_norm: np.ndarray, tickers: list) -> go.Figure:
    palette = [ACCENT, PINK, "#818cf8", "#34d399", "#fb923c",
               "#60a5fa", "#a78bfa", "#fbbf24"][:len(tickers)]
    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=tickers, values=[w * 100 for w in weights_norm],
        name="Weight", hole=0.55, domain={"column": 0},
        marker_colors=palette, textinfo="label+percent",
        hovertemplate="%{label}: %{value:.1f}%<extra>Weight</extra>",
        textfont=dict(color="white"),
    ))
    fig.add_trace(go.Pie(
        labels=tickers, values=[v * 100 for v in mrc.values],
        name="Risk", hole=0.55, domain={"column": 1},
        marker_colors=palette, textinfo="label+percent",
        hovertemplate="%{label}: %{value:.1f}%<extra>Risk Contrib.</extra>",
        textfont=dict(color="white"),
    ))
    fig.update_layout(
        **_PLOTLY,
        title=dict(text="Portfolio Weight  vs  Risk Contribution", font=dict(size=15, color=TXT)),
        grid={"rows": 1, "columns": 2},
        height=360, showlegend=False,
        annotations=[
            dict(text="Weight", x=0.20, y=0.5,
                 font=dict(size=13, color=TXT), showarrow=False),
            dict(text="Risk",   x=0.80, y=0.5,
                 font=dict(size=13, color=TXT), showarrow=False),
        ],
    )
    return fig


def factor_table_df(result: dict) -> pd.DataFrame:
    rows = [{"Factor": "Alpha (ann.)",
             "Exposure": f"{result['alpha_annualized']*100:.2f}%",
             "t-stat": f"{result['alpha_tstat']:.2f}",
             "Sig.": _stars(result["alpha_pval"])}]
    for f, beta in result["betas"].items():
        rows.append({"Factor": f,
                     "Exposure": f"{beta:.3f}",
                     "t-stat": f"{result['tstats'][f]:.2f}",
                     "Sig.": _stars(result["pvals"][f])})
    return pd.DataFrame(rows).set_index("Factor")


# ── Sidebar ───────────────────────────────────────────────────────────────────
db = get_db()

with st.sidebar:
    st.markdown(f"""
    <div style='padding:16px 0 8px 0'>
      <div style='font-size:22px;font-weight:800;color:{TXT}'>📊 Portfolio</div>
      <div style='font-size:11px;color:{TXT2};margin-top:4px'>Analyzer</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    source = st.radio(
        "Portfolio source",
        ["Trade log", "Manual entry", "Schwab API"],
        label_visibility="collapsed",
    )

    if source == "Trade log":
        tickers, weights = db.get_portfolio()
        if tickers:
            summary = db.get_positions_summary()
            st.markdown(f'<div class="section-label">Current Holdings</div>', unsafe_allow_html=True)
            st.dataframe(
                summary.assign(**{"Cost Basis": summary["Cost Basis"].map("${:,.0f}".format)}),
                hide_index=True, width="stretch",
            )
        else:
            st.info("No trades logged yet. Go to the **Trade Log** tab to add trades.")

    elif source == "Manual entry":
        st.markdown(f'<div class="section-label">Enter Holdings</div>', unsafe_allow_html=True)
        default_df = pd.DataFrame({
            "Ticker":     ["AAPL", "MSFT", "NVDA"],
            "Amount ($)": [10000.0, 8000.0, 7000.0],
        })
        holdings_df = st.data_editor(
            default_df, num_rows="dynamic", width="stretch",
            column_config={
                "Ticker":     st.column_config.TextColumn("Ticker", width="small"),
                "Amount ($)": st.column_config.NumberColumn("Amount ($)", min_value=0, format="%.0f"),
            },
        )
        holdings_df = holdings_df.dropna()
        holdings_df["Ticker"] = holdings_df["Ticker"].str.upper().str.strip()
        tickers = holdings_df["Ticker"].tolist()
        weights = holdings_df["Amount ($)"].tolist()

    else:  # Schwab API
        st.markdown(f'<div class="section-label">Schwab Credentials</div>', unsafe_allow_html=True)
        st.info("Set callback URL to `https://127.0.0.1:8182` at developer.schwab.com", icon="ℹ️")
        schwab_key    = st.text_input("App Key",    type="password")
        schwab_secret = st.text_input("App Secret", type="password")
        if "schwab_portfolio" not in st.session_state:
            st.session_state.schwab_portfolio = None
        if st.button("Connect & load", use_container_width=True):
            if schwab_key and schwab_secret:
                with st.spinner("Connecting…"):
                    try:
                        from schwab_connector import get_schwab_portfolio
                        tk, wt = get_schwab_portfolio(schwab_key, schwab_secret)
                        st.session_state.schwab_portfolio = {"tickers": tk, "weights": wt}
                        st.success(f"Loaded {len(tk)} positions.")
                    except Exception as e:
                        st.error(str(e))
            else:
                st.error("Enter credentials first.")
        p = st.session_state.get("schwab_portfolio")
        tickers = p["tickers"] if p else []
        weights = p["weights"] if p else []

    st.divider()
    st.markdown(f'<div class="section-label">Date Range</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    start_date = c1.date_input("From", value=date.today() - timedelta(days=5 * 365),
                                label_visibility="collapsed")
    c1.caption("From")
    end_date = c2.date_input("To", value=date.today(), label_visibility="collapsed")
    c2.caption("To")

    include_industry = st.checkbox("Include industry analysis", value=True,
                                   help="Downloads sector ETF data (~10s extra)")
    st.divider()
    analyze_btn = st.button(
        "▶  Run Analysis",
        use_container_width=True,
        type="primary",
        disabled=len(tickers) == 0,
    )
    if db.backend == "sqlite":
        st.caption(f"💾 Local database (SQLite)")
    else:
        st.caption(f"☁️ Cloud database (Supabase)")


# ── Run analysis ──────────────────────────────────────────────────────────────
if analyze_btn and tickers:
    with st.spinner("Fetching data & running regressions…"):
        try:
            res = run_analysis(
                tuple(tickers), tuple(weights),
                str(start_date), str(end_date), include_industry,
            )
            st.session_state.results      = res
            st.session_state.tickers      = tickers
            st.session_state.weights      = weights
            st.session_state.analysis_run = True
        except Exception as e:
            st.error(f"Analysis failed: {e}")

has_results  = st.session_state.get("analysis_run", False)
results      = st.session_state.get("results", {})
res_tickers  = st.session_state.get("tickers", tickers)
res_weights  = np.asarray(st.session_state.get("weights", weights or [1]), float)
weights_norm = res_weights / res_weights.sum() if res_weights.sum() > 0 else res_weights


# ── Tabs ──────────────────────────────────────────────────────────────────────
t_dash, t_factors, t_industry, t_cov, t_analytics, t_hedges, t_trades = st.tabs(
    ["Dashboard", "Factor Analysis", "Industry", "Covariance",
     "Analytics", "Hedges", "Trade Log"]
)


# ══ DASHBOARD ══════════════════════════════════════════════════════════════════
with t_dash:
    if not has_results:
        st.markdown(f"""
        <div style='text-align:center;padding:80px 20px'>
          <div style='font-size:48px'>📊</div>
          <div style='font-size:28px;font-weight:800;color:{TXT};margin:16px 0 8px'>
            Portfolio Analyzer
          </div>
          <div style='color:{TXT2};font-size:15px;max-width:500px;margin:0 auto'>
            Enter your holdings in the sidebar, choose a date range,<br>
            then click <b style='color:{ACCENT}'>Run Analysis</b>.
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="section-label">Portfolio Overview</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Holdings",         len(res_tickers))
        c2.metric("Portfolio Vol.",   f"{results['port_vol']*100:.1f}%")
        c3.metric("FF5 R²",           f"{results['ff']['portfolio']['r_squared']:.2f}")
        c4.metric("Alpha (ann.)",     f"{results['ff']['portfolio']['alpha_annualized']*100:.1f}%")
        st.plotly_chart(
            chart_cumulative(results["port_returns"], results["returns"]),
            width="stretch",
        )


# ══ FACTOR ANALYSIS ════════════════════════════════════════════════════════════
with t_factors:
    if not has_results:
        st.info("Run an analysis from the sidebar first.")
    else:
        st.markdown(f'<span class="accent-bar"></span>'
                    f'<span class="section-header">Fama-French 5-Factor + Momentum</span>',
                    unsafe_allow_html=True)
        col_c, col_t = st.columns([3, 2])
        with col_c:
            st.plotly_chart(
                chart_factor_bar(results["ff"]["portfolio"],
                                 "Portfolio Factor Loadings (95% CI)"),
                width="stretch",
            )
        with col_t:
            st.markdown(f'<div class="section-label">Regression Results</div>',
                        unsafe_allow_html=True)
            st.dataframe(factor_table_df(results["ff"]["portfolio"]), width="stretch")
            st.caption(
                f"{results['ff']['portfolio']['n_obs']} monthly obs.  ·  "
                "HC3 robust SEs  ·  ★★★ p<0.01  ★★ p<0.05  ★ p<0.10"
            )

        if len(res_tickers) > 1 and "stocks" in results["ff"]:
            st.divider()
            st.markdown(f'<span class="accent-bar"></span>'
                        f'<span class="section-header">Per-Stock Factor Loadings</span>',
                        unsafe_allow_html=True)
            st.plotly_chart(
                chart_factor_heatmap(results["ff"], res_tickers), width="stretch"
            )
            with st.expander("Per-stock regression tables"):
                for t in res_tickers:
                    st.markdown(f"**{t}**")
                    st.dataframe(factor_table_df(results["ff"]["stocks"][t]),
                                 width="stretch")


# ══ INDUSTRY ═══════════════════════════════════════════════════════════════════
with t_industry:
    if not has_results:
        st.info("Run an analysis from the sidebar first.")
    elif results["ind"] is None:
        st.info("Enable **Include industry analysis** in the sidebar and re-run.")
    else:
        st.markdown(f'<span class="accent-bar"></span>'
                    f'<span class="section-header">Sector Exposures</span>',
                    unsafe_allow_html=True)
        st.plotly_chart(
            chart_factor_bar(results["ind"],
                             "Industry Exposures — Sector ETF Regression"),
            width="stretch",
        )
        st.dataframe(factor_table_df(results["ind"]), width="stretch")
        st.caption(
            "OLS of portfolio returns on sector ETF returns "
            "(XLK, XLV, XLF, XLY, XLP, XLE, XLU, XLB, XLI, XLRE, XLC).  HC3 robust SEs."
        )


# ══ COVARIANCE ═════════════════════════════════════════════════════════════════
with t_cov:
    if not has_results:
        st.info("Run an analysis from the sidebar first.")
    else:
        st.markdown(f'<span class="accent-bar"></span>'
                    f'<span class="section-header">Correlation & Risk</span>',
                    unsafe_allow_html=True)
        st.plotly_chart(
            chart_risk_donuts(results["mrc"], weights_norm, res_tickers),
            width="stretch",
        )
        if len(res_tickers) > 1:
            col_h, col_s = st.columns([3, 2])
            with col_h:
                st.plotly_chart(chart_corr_heatmap(results["corr"]), width="stretch")
            with col_s:
                st.markdown(f'<div class="section-label">Volatilities & Risk</div>',
                            unsafe_allow_html=True)
                st.dataframe(pd.DataFrame({
                    "Ticker":        res_tickers,
                    "Weight":        [f"{w:.1%}" for w in weights_norm],
                    "Vol (ann.)":    [f"{results['vols'][t]*100:.1f}%" for t in res_tickers],
                    "Risk Contrib.": [f"{results['mrc'][t]*100:.1f}%" for t in res_tickers],
                }), hide_index=True, width="stretch")
                st.markdown(f'<div class="section-label" style="margin-top:16px">Covariance Matrix</div>',
                            unsafe_allow_html=True)
                st.dataframe(results["cov"].round(5), width="stretch")


# ══ ANALYTICS ══════════════════════════════════════════════════════════════════
with t_analytics:
    if not has_results:
        st.info("Run an analysis from the sidebar first.")
    else:
        # ── Performance metrics grid ──────────────────────────────────
        st.markdown(f'<span class="accent-bar"></span>'
                    f'<span class="section-header">Performance Metrics</span>',
                    unsafe_allow_html=True)

        ann_ret = results["ann_return"]
        sharpe  = results["sharpe"]
        sortino = results["sortino"]
        mdd     = results["max_drawdown"]
        calmar  = results["calmar"]
        var95   = results["var95"]
        cvar95  = results["cvar95"]

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Ann. Return",   f"{ann_ret*100:.1f}%")
        c2.metric("Sharpe Ratio",  f"{sharpe:.2f}")
        c3.metric("Sortino Ratio", f"{sortino:.2f}")
        c4.metric("Max Drawdown",  f"{mdd*100:.1f}%")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Calmar Ratio",  f"{calmar:.2f}" if calmar < 99 else "—")
        c2.metric("VaR (95%)",     f"{var95*100:.1f}%")
        c3.metric("CVaR (95%)",    f"{cvar95*100:.1f}%")
        c4.metric("Portfolio Vol", f"{results['port_vol']*100:.1f}%")

        # ── Benchmark comparison ──────────────────────────────────────
        st.divider()
        st.markdown(f'<span class="accent-bar"></span>'
                    f'<span class="section-header">Benchmark Comparison (vs SPY)</span>',
                    unsafe_allow_html=True)

        port_ret  = results["port_returns"]
        bench_ret = results["benchmark"].reindex(port_ret.index).dropna()
        port_cum  = (1 + port_ret.reindex(bench_ret.index)).cumprod()
        bench_cum = (1 + bench_ret).cumprod()

        fig_bench = go.Figure()
        fig_bench.add_trace(go.Scatter(
            x=port_cum.index, y=port_cum.values,
            mode="lines", name="Portfolio",
            line=dict(color=ACCENT, width=2.5),
        ))
        fig_bench.add_trace(go.Scatter(
            x=bench_cum.index, y=bench_cum.values,
            mode="lines", name="SPY",
            line=dict(color=TXT2, width=1.5, dash="dot"),
        ))
        fig_bench.add_hline(y=1, line_dash="dash", line_color=BORDER, line_width=1)
        fig_bench.update_layout(
            **_PLOTLY,
            title=dict(text="Portfolio vs S&P 500", font=dict(size=15, color=TXT)),
            yaxis_title="Growth of $1", height=340,
            legend=dict(orientation="h", y=-0.2, font=dict(color=TXT2)),
            xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER),
        )
        st.plotly_chart(fig_bench, width="stretch")

        # Benchmark stats comparison table
        def _ann(r):
            return (1 + r.mean()) ** 12 - 1
        def _vol(r):
            return r.std() * np.sqrt(12)
        def _sr(r, rf=0):
            ex = r - rf
            return ex.mean() / ex.std() * np.sqrt(12) if ex.std() else 0
        def _mdd(r):
            c = (1+r).cumprod()
            return ((c - c.cummax()) / c.cummax()).min()

        aligned_port  = port_ret.reindex(bench_ret.index).dropna()
        comp_df = pd.DataFrame({
            "Metric":    ["Ann. Return", "Ann. Volatility", "Sharpe", "Max Drawdown"],
            "Portfolio": [f"{_ann(aligned_port)*100:.1f}%",
                          f"{_vol(aligned_port)*100:.1f}%",
                          f"{_sr(aligned_port):.2f}",
                          f"{_mdd(aligned_port)*100:.1f}%"],
            "SPY":       [f"{_ann(bench_ret)*100:.1f}%",
                          f"{_vol(bench_ret)*100:.1f}%",
                          f"{_sr(bench_ret):.2f}",
                          f"{_mdd(bench_ret)*100:.1f}%"],
        })
        st.dataframe(comp_df, hide_index=True, width="stretch")

        # Export benchmark comparison
        st.download_button(
            "⬇ Export comparison CSV",
            comp_df.to_csv(index=False),
            file_name="benchmark_comparison.csv",
            mime="text/csv",
        )

        # ── Rolling factor betas ──────────────────────────────────────
        rolling = results["rolling_betas"]
        if not rolling.empty:
            st.divider()
            st.markdown(f'<span class="accent-bar"></span>'
                        f'<span class="section-header">Rolling Factor Betas (36-month window)</span>',
                        unsafe_allow_html=True)
            palette = [ACCENT, PINK, POS, "#818cf8", "#fb923c", "#fbbf24"]
            fig_roll = go.Figure()
            for i, col in enumerate(rolling.columns):
                fig_roll.add_trace(go.Scatter(
                    x=rolling.index, y=rolling[col],
                    mode="lines", name=col,
                    line=dict(color=palette[i % len(palette)], width=1.8),
                ))
            fig_roll.add_hline(y=0, line_dash="dash", line_color=TXT2, line_width=1)
            fig_roll.update_layout(
                **_PLOTLY,
                title=dict(text="How factor exposures change over time",
                           font=dict(size=15, color=TXT)),
                yaxis_title="Beta", height=370,
                legend=dict(orientation="h", y=-0.2, font=dict(color=TXT2)),
                xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER),
            )
            st.plotly_chart(fig_roll, width="stretch")
            st.download_button(
                "⬇ Export rolling betas CSV",
                rolling.to_csv(),
                file_name="rolling_betas.csv",
                mime="text/csv",
            )

        # ── Returns distribution ──────────────────────────────────────
        st.divider()
        st.markdown(f'<span class="accent-bar"></span>'
                    f'<span class="section-header">Returns Distribution</span>',
                    unsafe_allow_html=True)
        ret_vals = results["port_returns"].dropna() * 100
        fig_dist = go.Figure()
        fig_dist.add_trace(go.Histogram(
            x=ret_vals, nbinsx=40,
            marker_color=ACCENT, opacity=0.75,
            name="Monthly Returns",
        ))
        fig_dist.add_vline(x=float(var95 * 100), line_dash="dash",
                           line_color=NEG, line_width=2,
                           annotation_text=f"VaR 95%: {var95*100:.1f}%",
                           annotation_font_color=NEG)
        fig_dist.update_layout(
            **_PLOTLY,
            title=dict(text="Monthly Return Distribution", font=dict(size=15, color=TXT)),
            xaxis_title="Monthly Return (%)", yaxis_title="Frequency",
            height=320,
            xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER),
        )
        st.plotly_chart(fig_dist, width="stretch")


# ══ HEDGES ═════════════════════════════════════════════════════════════════════
with t_hedges:
    if not has_results:
        st.info("Run an analysis from the sidebar first.")
    else:
        st.markdown(f'<span class="accent-bar"></span>'
                    f'<span class="section-header">Factor-Neutral Hedge Suggestions</span>',
                    unsafe_allow_html=True)
        st.markdown(f"""
        <div style='color:{TXT2};font-size:13px;margin-bottom:16px'>
        Shows positions needed to bring each <b>statistically significant</b> factor beta
        to zero. Only factors with |β| > 0.15 and p &lt; 0.10 are shown.
        </div>
        """, unsafe_allow_html=True)

        port_val = st.number_input(
            "Portfolio value ($) — used to size hedge positions",
            min_value=1000, value=100000, step=5000, format="%d",
        )

        if st.button("Compute Hedges", type="primary"):
            with st.spinner("Running factor regressions on hedge ETFs…"):
                try:
                    analyzer = results["_analyzer"]
                    hedges   = analyzer.hedge_suggestions(
                        results["ff"],
                        industry_results=results["ind"],
                        portfolio_value=float(port_val),
                    )
                    st.session_state.hedges = hedges
                except Exception as e:
                    st.error(f"Hedge computation failed: {e}")

        if "hedges" in st.session_state:
            h = st.session_state.hedges

            # ── Factor hedges ─────────────────────────────────────────
            st.markdown(f'<div class="section-label" style="margin-top:16px">Factor Hedges</div>',
                        unsafe_allow_html=True)
            if h["factor_hedges"]:
                fh_df = pd.DataFrame(h["factor_hedges"])
                fh_display = fh_df.rename(columns={
                    "factor": "Factor", "port_beta": "Portfolio β",
                    "hedge_etf": "Hedge ETF", "direction": "Direction",
                    "notional": "Notional ($)", "current_price": "ETF Price",
                    "approx_shares": "Approx. Shares",
                    "etf_factor_beta": "ETF β to Factor",
                })
                # Colour direction column
                def _dir_color(val):
                    c = POS if val == "BUY" else NEG
                    return f"color: {c}; font-weight: 700"
                st.dataframe(
                    fh_display.style.applymap(_dir_color, subset=["Direction"]),
                    hide_index=True, width="stretch",
                )
                st.caption(
                    "Notional = position size needed to neutralise that factor beta. "
                    "BUY = go long the ETF. SHORT = sell short."
                )
                st.download_button(
                    "⬇ Export factor hedges CSV",
                    fh_display.to_csv(index=False),
                    file_name="factor_hedges.csv", mime="text/csv",
                )
            else:
                st.success("No significant factor exposures to hedge at current thresholds.")

            # ── Industry hedges ───────────────────────────────────────
            st.divider()
            st.markdown(f'<div class="section-label">Industry Hedges</div>',
                        unsafe_allow_html=True)
            if h["industry_hedges"]:
                ih_df = pd.DataFrame(h["industry_hedges"])
                ih_display = ih_df.rename(columns={
                    "sector": "Sector", "port_beta": "Portfolio β",
                    "hedge_etf": "Hedge ETF", "direction": "Direction",
                    "notional": "Notional ($)", "current_price": "ETF Price",
                    "approx_shares": "Approx. Shares",
                })
                st.dataframe(
                    ih_display.style.applymap(_dir_color, subset=["Direction"]),
                    hide_index=True, width="stretch",
                )
                st.download_button(
                    "⬇ Export industry hedges CSV",
                    ih_display.to_csv(index=False),
                    file_name="industry_hedges.csv", mime="text/csv",
                )
            elif results["ind"] is None:
                st.info("Enable industry analysis in the sidebar and re-run to get industry hedges.")
            else:
                st.success("No significant industry exposures to hedge.")


# ══ TRADE LOG ══════════════════════════════════════════════════════════════════
with t_trades:
    st.markdown(f'<span class="accent-bar"></span>'
                f'<span class="section-header">Trade Log</span>',
                unsafe_allow_html=True)

    # ── Add trade form ────────────────────────────────────────────────────
    with st.expander("➕  Add a trade", expanded=True):
        f1, f2, f3, f4, f5, f6 = st.columns([1.2, 1, 0.9, 1.1, 1.2, 1.8])
        tk_in    = f1.text_input("Ticker",    placeholder="AAPL")
        dt_in    = f2.date_input("Date",      value=date.today(), label_visibility="visible")
        act_in   = f3.selectbox("Action",     ["BUY", "SELL"])
        qty_in   = f4.number_input("Quantity", min_value=0.0001, value=1.0, step=0.5)
        price_in = f5.number_input("Price ($)", min_value=0.01, value=100.0, step=1.0)
        notes_in = f6.text_input("Notes (optional)", placeholder="e.g. earnings dip buy")

        _, btn_col = st.columns([5, 1])
        if btn_col.button("Save trade", type="primary", use_container_width=True):
            if tk_in.strip():
                db.add_trade(tk_in, dt_in, act_in, qty_in, price_in, notes_in)
                st.success(f"Saved: {act_in} {qty_in} {tk_in.upper()} @ ${price_in:.2f}")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Enter a ticker symbol.")

    # ── Unrealized P&L ────────────────────────────────────────────────────
    pnl_df = db.get_unrealized_pnl()
    if not pnl_df.empty:
        st.markdown(f'<div class="section-label" style="margin-top:24px">Unrealized P&L (Live Prices)</div>',
                    unsafe_allow_html=True)

        total_val  = pnl_df["Market Value"].sum()
        total_cost = (pnl_df["Net Qty"] * pnl_df["Avg Cost"]).sum()
        total_pnl  = pnl_df["Unrealized P&L"].sum()
        total_pct  = total_pnl / total_cost * 100 if total_cost else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Market Value",    f"${total_val:,.0f}")
        m2.metric("Cost Basis",      f"${total_cost:,.0f}")
        pnl_color = "normal" if total_pnl >= 0 else "inverse"
        m3.metric("Unrealized P&L",  f"${total_pnl:,.0f}",
                  delta=f"{total_pct:.1f}%", delta_color=pnl_color)

        pnl_display = pnl_df.copy()
        pnl_display["Avg Cost"]       = pnl_display["Avg Cost"].map("${:,.2f}".format)
        pnl_display["Current Price"]  = pnl_display["Current Price"].map("${:,.2f}".format)
        pnl_display["Market Value"]   = pnl_display["Market Value"].map("${:,.0f}".format)
        pnl_display["Unrealized P&L"] = pnl_display["Unrealized P&L"].map("${:,.0f}".format)
        pnl_display["P&L %"]          = pnl_display["P&L %"].map("{:+.1f}%".format)
        st.dataframe(pnl_display, hide_index=True, width="stretch")
        st.download_button("⬇ Export P&L CSV", pnl_df.to_csv(index=False),
                           file_name="unrealized_pnl.csv", mime="text/csv")

    # ── Portfolio value history ───────────────────────────────────────────
    all_trades = db.get_trades()
    if not all_trades.empty:
        with st.spinner("Building portfolio value history…"):
            port_hist = db.get_portfolio_value_history()

        if not port_hist.empty:
            st.markdown(f'<div class="section-label" style="margin-top:24px">Portfolio Value Over Time</div>',
                        unsafe_allow_html=True)
            fig_hist = go.Figure(go.Scatter(
                x=port_hist.index, y=port_hist.values,
                mode="lines", fill="tozeroy",
                line=dict(color=ACCENT, width=2),
                fillcolor=f"rgba(217,70,239,0.15)",
            ))
            fig_hist.update_layout(
                **_PLOTLY,
                title=dict(text="Total Portfolio Value", font=dict(size=15, color=TXT)),
                yaxis_title="Value ($)", height=300,
                yaxis=dict(tickprefix="$", gridcolor=BORDER),
                xaxis=dict(gridcolor=BORDER),
            )
            st.plotly_chart(fig_hist, width="stretch")

        # ── Open positions table ──────────────────────────────────────
        positions = db.get_positions_summary()
        if not positions.empty:
            st.markdown(f'<div class="section-label" style="margin-top:24px">Open Positions</div>',
                        unsafe_allow_html=True)
            display = positions.copy()
            display["Avg Cost"]   = display["Avg Cost"].map("${:,.2f}".format)
            display["Cost Basis"] = display["Cost Basis"].map("${:,.0f}".format)
            st.dataframe(display, hide_index=True, width="stretch")

        # ── Full trade history ────────────────────────────────────────
        st.markdown(f'<div class="section-label" style="margin-top:24px">All Trades</div>',
                    unsafe_allow_html=True)
        disp = all_trades[["id","ticker","trade_date","action","quantity","price","notes"]].copy()
        disp.columns = ["ID","Ticker","Date","Action","Qty","Price","Notes"]
        disp["Price"] = disp["Price"].map("${:,.2f}".format)
        st.dataframe(disp, hide_index=True, width="stretch")

        col_dl, col_del, _ = st.columns([1.2, 1, 3])
        col_dl.download_button("⬇ Export trades CSV",
                               all_trades.to_csv(index=False),
                               file_name="trade_log.csv", mime="text/csv")
        del_id = col_del.number_input("Delete ID", min_value=1, step=1,
                                      label_visibility="visible")
        if col_del.button("🗑 Delete", use_container_width=True):
            db.delete_trade(int(del_id))
            st.success(f"Deleted trade #{del_id}")
            st.cache_data.clear()
            st.rerun()
    else:
        st.markdown(f"""
        <div style='text-align:center;padding:40px 0;color:{TXT2}'>
          No trades yet. Use the form above to log your first trade.
        </div>
        """, unsafe_allow_html=True)
