"""
backend_main.py — FastAPI REST API
Start locally: uvicorn backend_main:app --reload
"""

import io
import os
import traceback
from typing import List, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from auth import create_token, hash_password, require_user, verify_password
    _AUTH_AVAILABLE = True
except ImportError:
    _AUTH_AVAILABLE = False
    def require_user(*a, **kw): raise HTTPException(503, "Auth not available — install python-jose and passlib")
    def create_token(*a, **kw): return ""
    def hash_password(p): return p
    def verify_password(p, h): return p == h

from db import TradeDB
from portfolio_analyzer import PortfolioAnalyzer

app = FastAPI(title="Bayes Portfolio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── DB factory ────────────────────────────────────────────────────────────────
def get_db() -> TradeDB:
    return TradeDB(
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_key=os.getenv("SUPABASE_KEY", ""),
    )


# ── Serialisation helpers ─────────────────────────────────────────────────────
def _ser(r: dict) -> dict:
    """Strip non-serialisable fields from a regression result dict."""
    return {k: v for k, v in r.items() if k != "model"}


def _series(s: pd.Series) -> list:
    return [{"date": str(i.date() if hasattr(i, "date") else i), "value": float(v)}
            for i, v in s.items() if pd.notna(v)]


def _df(df: pd.DataFrame) -> list:
    out = []
    for idx, row in df.iterrows():
        rec = {"date": str(idx.date() if hasattr(idx, "date") else idx)}
        rec.update({c: float(v) for c, v in row.items() if pd.notna(v)})
        out.append(rec)
    return out


# ── Request models ────────────────────────────────────────────────────────────
class AnalyzeReq(BaseModel):
    tickers: List[str]
    weights: List[float]
    start_date: str
    end_date: str
    include_industry: bool = True


class HedgeReq(BaseModel):
    tickers: List[str]
    weights: List[float]
    start_date: str
    end_date: str
    portfolio_value: float = 100_000
    include_industry: bool = True


class OptimizeReq(BaseModel):
    tickers: List[str]
    weights: List[float]
    start_date: str
    end_date: str
    expected_returns: dict
    risk_free_rate: float = 0.0
    long_only: bool = True
    max_position: float = 0.40
    use_shrinkage: bool = True
    max_risk_contribution: Optional[float] = None


class KellyReq(BaseModel):
    tickers: List[str]
    weights: List[float]
    start_date: str
    end_date: str
    expected_returns: dict
    risk_free_rate: float = 0.0
    fraction: float = 0.5
    use_shrinkage: bool = True


class SimulateReq(BaseModel):
    tickers: List[str]
    weights: List[float]
    start_date: str
    end_date: str
    n_simulations: int = 5000
    horizon_months: int = 12
    expected_returns: Optional[dict] = None


class BacktestReq(BaseModel):
    tickers: List[str]
    weights: List[float]
    start_date: str
    end_date: str
    rebalance_freq: str = "quarterly"
    target_weights: Optional[List[float]] = None


class TradeReq(BaseModel):
    ticker: str
    trade_date: str
    action: str
    quantity: float
    price: float
    notes: str = ""


class SignupReq(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginReq(BaseModel):
    email: str
    password: str


class PortfolioSaveReq(BaseModel):
    name: str
    tickers: List[str]
    weights: List[float]
    start_date: str
    end_date: str


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


# ── Auth ──────────────────────────────────────────────────────────────────────
@app.post("/auth/signup")
def signup(req: SignupReq):
    db = get_db()
    if db.get_user_by_email(req.email):
        raise HTTPException(400, "Email already registered")
    hashed = hash_password(req.password)
    user = db.create_user(req.email, req.name or req.email.split("@")[0], hashed)
    token = create_token(user["id"], user["email"], user["name"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}


@app.post("/auth/login")
def login(req: LoginReq):
    db = get_db()
    user = db.get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user["id"], user["email"], user["name"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}


@app.get("/auth/me")
def me(current_user: dict = Depends(require_user)):
    return {"id": int(current_user["sub"]), "email": current_user["email"], "name": current_user["name"]}


# ── Portfolios ────────────────────────────────────────────────────────────────
@app.get("/portfolios")
def list_portfolios(current_user: dict = Depends(require_user)):
    return get_db().get_portfolios(int(current_user["sub"]))


@app.post("/portfolios")
def create_portfolio(req: PortfolioSaveReq, current_user: dict = Depends(require_user)):
    return get_db().create_portfolio(
        int(current_user["sub"]), req.name,
        req.tickers, req.weights, req.start_date, req.end_date,
    )


@app.put("/portfolios/{portfolio_id}")
def update_portfolio(portfolio_id: int, req: PortfolioSaveReq, current_user: dict = Depends(require_user)):
    return get_db().update_portfolio(
        portfolio_id, int(current_user["sub"]), req.name,
        req.tickers, req.weights, req.start_date, req.end_date,
    )


@app.delete("/portfolios/{portfolio_id}")
def delete_portfolio(portfolio_id: int, current_user: dict = Depends(require_user)):
    get_db().delete_portfolio(portfolio_id, int(current_user["sub"]))
    return {"ok": True}


# ── Analysis ──────────────────────────────────────────────────────────────────
@app.post("/analyze")
def analyze(req: AnalyzeReq):
    try:
        a = PortfolioAnalyzer(
            req.tickers, req.weights,
            req.start_date, req.end_date, "monthly",
        )
        a.fetch_prices()

        ff  = a.factor_analysis(include_momentum=True, per_stock=True)
        ind = a.industry_analysis() if req.include_industry else None
        mdd = a.max_drawdown()
        rolling = a.rolling_factor_betas(window=36)
        bench   = a.benchmark_returns("SPY")

        return {
            "ff": {
                "portfolio": _ser(ff["portfolio"]),
                "stocks":    {t: _ser(v) for t, v in ff.get("stocks", {}).items()},
            },
            "ind":           _ser(ind) if ind else None,
            "cov":           a.covariance_matrix().to_dict(),
            "corr":          a.correlation_matrix().to_dict(),
            "vols":          a.stock_volatilities().to_dict(),
            "mrc":           a.marginal_risk_contributions().to_dict(),
            "port_vol":      a.portfolio_volatility(),
            "port_returns":  _series(a.portfolio_returns),
            "stock_returns": {t: _series(a.returns[t]) for t in req.tickers},
            "benchmark":     _series(bench),
            "rolling_betas": _df(rolling) if not rolling.empty else [],
            "sharpe":           a.sharpe_ratio(),
            "sortino":          a.sortino_ratio(),
            "max_drawdown":     mdd["max_drawdown"],
            "calmar":           a.calmar_ratio(),
            "var95":            a.var(0.95),
            "cvar95":           a.cvar(0.95),
            "ann_return":       a.annualised_return(),
            "active_return":    a.active_return("SPY"),
            "tracking_error":   a.tracking_error("SPY"),
            "information_ratio": a.information_ratio("SPY"),
            "risk_decomp":      a.risk_decomposition(),
        }
    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR in /analyze:\n{tb}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


@app.post("/hedges")
def hedges(req: HedgeReq):
    try:
        a = PortfolioAnalyzer(
            req.tickers, req.weights,
            req.start_date, req.end_date, "monthly",
        )
        a.fetch_prices()
        ff  = a.factor_analysis(include_momentum=True, per_stock=False)
        ind = a.industry_analysis() if req.include_industry else None
        return a.hedge_suggestions(ff, ind, req.portfolio_value)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR in /hedges:\n{tb}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


# ── Optimiser ─────────────────────────────────────────────────────────────────
@app.post("/optimize")
def optimize(req: OptimizeReq):
    try:
        a = PortfolioAnalyzer(
            req.tickers, req.weights,
            req.start_date, req.end_date, "monthly",
        )
        a.fetch_prices()
        result = a.optimize_weights(
            expected_returns=req.expected_returns,
            risk_free_rate=req.risk_free_rate,
            long_only=req.long_only,
            max_position=req.max_position,
            use_shrinkage=req.use_shrinkage,
            max_risk_contribution=req.max_risk_contribution,
        )
        total = sum(req.weights)
        adjustments = {}
        for t in req.tickers:
            cur_d = result["current_weights"][t] * total
            opt_d = result["optimal_weights"][t] * total
            adjustments[t] = {
                "current_pct":    result["current_weights"][t],
                "optimal_pct":    result["optimal_weights"][t],
                "current_dollars": cur_d,
                "optimal_dollars": opt_d,
                "delta_dollars":   opt_d - cur_d,
                "action": "BUY" if opt_d > cur_d + 0.01 else "SELL" if cur_d > opt_d + 0.01 else "HOLD",
            }
        result["adjustments"]    = adjustments
        result["portfolio_value"] = total

        # ── FLAM: Grinold-Kahn Fundamental Law (Paleologo Ch. 6) ─────
        ppy = 12
        realized = {
            t: float((1 + a.returns[t].mean()) ** ppy - 1)
            for t in req.tickers
        }
        pred_vals     = np.array([req.expected_returns[t] for t in req.tickers])
        realized_vals = np.array([realized[t]             for t in req.tickers])
        if len(req.tickers) >= 2 and pred_vals.std() > 0 and realized_vals.std() > 0:
            ic = float(np.corrcoef(pred_vals, realized_vals)[0, 1])
        else:
            ic = 0.0
        breadth    = len(req.tickers) * ppy   # independent bets / year
        ir_implied = ic * np.sqrt(breadth)
        result["flam"] = {
            "ic":               ic,
            "breadth":          breadth,
            "ir_implied":       ir_implied,
            "realized_returns": realized,
        }
        return result
    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR in /optimize:\n{tb}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


# ── Kelly Criterion ──────────────────────────────────────────────────────────
@app.post("/kelly")
def kelly(req: KellyReq):
    try:
        a = PortfolioAnalyzer(
            req.tickers, req.weights,
            req.start_date, req.end_date, "monthly",
        )
        a.fetch_prices()
        return a.kelly_criterion(
            expected_returns=req.expected_returns,
            risk_free_rate=req.risk_free_rate,
            fraction=req.fraction,
            use_shrinkage=req.use_shrinkage,
        )
    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR in /kelly:\n{tb}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


# ── Monte Carlo ──────────────────────────────────────────────────────────────
@app.post("/simulate")
def simulate(req: SimulateReq):
    try:
        a = PortfolioAnalyzer(
            req.tickers, req.weights,
            req.start_date, req.end_date, "monthly",
        )
        a.fetch_prices()
        return a.monte_carlo(
            n_simulations=req.n_simulations,
            horizon_months=req.horizon_months,
            expected_returns=req.expected_returns,
        )
    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR in /simulate:\n{tb}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


# ── Backtest ─────────────────────────────────────────────────────────────────
@app.post("/backtest")
def backtest(req: BacktestReq):
    try:
        a = PortfolioAnalyzer(
            req.tickers, req.weights,
            req.start_date, req.end_date, "monthly",
        )
        a.fetch_prices()
        return a.backtest(
            rebalance_freq=req.rebalance_freq,
            target_weights=req.target_weights,
        )
    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR in /backtest:\n{tb}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


# ── Signals / Alt Data ───────────────────────────────────────────────────────
_signals_cache: dict = {}

@app.get("/signals/{ticker}")
def get_signals(ticker: str):
    import time
    ticker = ticker.upper()
    cached = _signals_cache.get(ticker)
    if cached and time.time() - cached["_ts"] < 3600:
        return cached

    try:
        info = yf.Ticker(ticker).info
    except Exception:
        info = {}

    try:
        options = yf.Ticker(ticker).options
        if options:
            chain = yf.Ticker(ticker).option_chain(options[0])
            pc_ratio = round(chain.puts["openInterest"].sum() / max(chain.calls["openInterest"].sum(), 1), 2)
        else:
            pc_ratio = None
    except Exception:
        pc_ratio = None

    result = {
        "ticker": ticker,
        "name": info.get("shortName", ticker),
        "sector": info.get("sector", "—"),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "avg_volume": info.get("averageVolume"),
        "earnings_date": str(info.get("earningsDate", "")) if info.get("earningsDate") else None,
        "recommendation": info.get("recommendationKey"),
        "target_price": info.get("targetMeanPrice"),
        "analyst_count": info.get("numberOfAnalystOpinions"),
        "put_call_ratio": pc_ratio,
        "short_percent": info.get("shortPercentOfFloat"),
        "_ts": time.time(),
    }
    _signals_cache[ticker] = result
    return result


@app.get("/macro")
def get_macro():
    """Basic macro indicators from yfinance."""
    import time
    cached = _signals_cache.get("__macro__")
    if cached and time.time() - cached["_ts"] < 3600:
        return cached

    indicators = {}
    try:
        vix = yf.Ticker("^VIX").info
        indicators["vix"] = vix.get("regularMarketPrice") or vix.get("previousClose")
    except Exception:
        indicators["vix"] = None

    try:
        tnx = yf.Ticker("^TNX").info
        indicators["us10y"] = tnx.get("regularMarketPrice") or tnx.get("previousClose")
    except Exception:
        indicators["us10y"] = None

    try:
        irx = yf.Ticker("^IRX").info
        indicators["us3m"] = irx.get("regularMarketPrice") or irx.get("previousClose")
    except Exception:
        indicators["us3m"] = None

    try:
        spy_info = yf.Ticker("SPY").info
        indicators["spy_price"] = spy_info.get("regularMarketPrice") or spy_info.get("previousClose")
        indicators["spy_pe"] = spy_info.get("trailingPE")
    except Exception:
        indicators["spy_price"] = None

    indicators["_ts"] = time.time()
    _signals_cache["__macro__"] = indicators
    return indicators


# ── CSV Import ───────────────────────────────────────────────────────────────
@app.post("/import/csv")
async def import_csv(file: UploadFile):
    """Import trades from a CSV file. Expected columns: ticker, date, action, quantity, price"""
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
    # Normalise column names
    df.columns = [c.strip().lower() for c in df.columns]
    col_map = {"symbol": "ticker", "trade_date": "date"}
    df = df.rename(columns=col_map)

    required = {"ticker", "date", "action", "quantity", "price"}
    if not required.issubset(set(df.columns)):
        raise HTTPException(400, f"CSV must have columns: {required}. Got: {list(df.columns)}")

    db = get_db()
    count = 0
    for _, row in df.iterrows():
        try:
            db.add_trade(
                ticker=str(row["ticker"]).upper().strip(),
                trade_date=str(row["date"]),
                action=str(row["action"]).upper().strip(),
                quantity=float(row["quantity"]),
                price=float(row["price"]),
                notes=str(row.get("notes", "")),
            )
            count += 1
        except Exception:
            continue
    return {"imported": count}


# ── Trades ────────────────────────────────────────────────────────────────────
@app.get("/trades")
def get_trades():
    return get_db().get_trades().to_dict(orient="records")


@app.post("/trades")
def add_trade(t: TradeReq):
    get_db().add_trade(t.ticker, t.trade_date, t.action, t.quantity, t.price, t.notes)
    return {"ok": True}


@app.delete("/trades/{trade_id}")
def delete_trade(trade_id: int):
    get_db().delete_trade(trade_id)
    return {"ok": True}


@app.get("/portfolio")
def get_portfolio():
    db = get_db()
    tickers, weights = db.get_portfolio()
    return {
        "tickers":   tickers,
        "weights":   weights,
        "positions": db.get_positions_summary().to_dict(orient="records"),
    }


@app.get("/pnl")
def get_pnl():
    pnl = get_db().get_unrealized_pnl()
    return pnl.to_dict(orient="records") if not pnl.empty else []


@app.get("/portfolio-value")
def get_portfolio_value():
    return _series(get_db().get_portfolio_value_history())
