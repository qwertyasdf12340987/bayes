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
from fastapi import Depends, FastAPI, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import create_access_token, hash_password, require_user, verify_password
from db import TradeDB
from portfolio_analyzer import PortfolioAnalyzer

app = FastAPI(title="Bayes Portfolio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── DB factory ────────────────────────────────────────────────────────────────
def get_db() -> TradeDB:
    return TradeDB(
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_KEY", "")),
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
    portfolio_id: int
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


class PortfolioReq(BaseModel):
    name: str
    tickers: List[str]
    weights: List[float]
    start_date: str = ""
    end_date: str = ""


class PortfolioUpdateReq(BaseModel):
    name: Optional[str] = None
    tickers: Optional[List[str]] = None
    weights: Optional[List[float]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


def _normalise_tickers(tickers: List[str]) -> List[str]:
    cleaned = [t.upper().strip() for t in tickers if t and t.strip()]
    if not cleaned:
        raise HTTPException(status_code=400, detail="At least one ticker is required")
    return cleaned


def _validate_weights(tickers: List[str], weights: List[float]) -> List[float]:
    if len(tickers) != len(weights):
        raise HTTPException(status_code=400, detail="Tickers and weights must have the same length")
    weights = [float(w) for w in weights]
    if not any(abs(w) > 1e-12 for w in weights):
        raise HTTPException(status_code=400, detail="Weights must not all be zero")
    return weights


def _validate_portfolio_dates(start_date: str, end_date: str) -> None:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date")


def _get_owned_portfolio(db: TradeDB, portfolio_id: int, user_id: int) -> dict:
    portfolio = db.get_portfolio_by_id(portfolio_id, user_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


def _token_payload(user: dict) -> dict:
    return {
        "access_token": create_access_token(
            {"sub": str(user["id"]), "email": user["email"], "name": user.get("name", "")}
        ),
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"], "name": user.get("name", "")},
    }


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/signup")
def signup(req: SignupReq):
    db = get_db()
    email = req.email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if db.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account with that email already exists")

    user = db.create_user(email=email, name=req.name.strip(), password_hash=hash_password(req.password))
    db.create_portfolio(
        user_id=user["id"],
        name="Personal Portfolio",
        tickers=[],
        weights=[],
    )
    return _token_payload(user)


@app.post("/auth/login")
def login(req: LoginReq):
    db = get_db()
    user = db.get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return _token_payload(user)


@app.get("/auth/me")
def me(user: dict = Depends(require_user)):
    return {"id": user["id"], "email": user["email"], "name": user.get("name", "")}


@app.get("/portfolios")
def list_portfolios(user: dict = Depends(require_user)):
    return get_db().get_portfolios(user["id"])


@app.post("/portfolios")
def create_portfolio(req: PortfolioReq, user: dict = Depends(require_user)):
    tickers = _normalise_tickers(req.tickers) if req.tickers else []
    weights = _validate_weights(tickers, req.weights) if tickers or req.weights else []
    _validate_portfolio_dates(req.start_date, req.end_date)
    return get_db().create_portfolio(
        user_id=user["id"],
        name=req.name.strip() or "Untitled Portfolio",
        tickers=tickers,
        weights=weights,
        start_date=req.start_date,
        end_date=req.end_date,
    )


@app.put("/portfolios/{portfolio_id}")
def update_portfolio(portfolio_id: int, req: PortfolioUpdateReq, user: dict = Depends(require_user)):
    db = get_db()
    existing = _get_owned_portfolio(db, portfolio_id, user["id"])

    updates = req.model_dump(exclude_none=True)
    if "tickers" in updates:
        updates["tickers"] = _normalise_tickers(updates["tickers"])
    if "weights" in updates or "tickers" in updates:
        tickers = updates.get("tickers")
        if tickers is None:
            tickers = existing["tickers"]
        weights = updates.get("weights")
        if weights is None:
            weights = existing["weights"]
        updates["weights"] = _validate_weights(tickers, weights)
        updates["tickers"] = tickers

    _validate_portfolio_dates(
        updates.get("start_date", existing.get("start_date", "")),
        updates.get("end_date", existing.get("end_date", "")),
    )

    updated = db.update_portfolio(portfolio_id, user["id"], **updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return updated


@app.delete("/portfolios/{portfolio_id}")
def delete_portfolio(portfolio_id: int, user: dict = Depends(require_user)):
    db = get_db()
    portfolios = db.get_portfolios(user["id"])
    if len(portfolios) <= 1:
        raise HTTPException(status_code=400, detail="At least one portfolio must remain")
    if not db.delete_portfolio(portfolio_id, user["id"]):
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"ok": True}


# ── Analysis ──────────────────────────────────────────────────────────────────
@app.post("/analyze")
def analyze(req: AnalyzeReq):
    try:
        tickers = _normalise_tickers(req.tickers)
        weights = _validate_weights(tickers, req.weights)
        _validate_portfolio_dates(req.start_date, req.end_date)
        a = PortfolioAnalyzer(
            tickers, weights,
            req.start_date, req.end_date, "monthly",
        )
        a.fetch_prices()

        ff  = a.factor_analysis(include_momentum=True, per_stock=True)
        ind = a.industry_analysis() if req.include_industry else None
        mdd = a.max_drawdown()
        rolling = a.rolling_factor_betas(window=36)
        bench   = a.benchmark_returns("SPY")
        oil_exp = a.oil_exposure()
        rates_exp = a.rates_exposure()

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
            "stock_returns": {t: _series(a.returns[t]) for t in tickers},
            "benchmark":     _series(bench),
            "oil_exposure":  oil_exp,
            "rates_exposure": rates_exp,
            "rolling_betas": _df(rolling) if not rolling.empty else [],
            "sharpe":        a.sharpe_ratio(),
            "sortino":       a.sortino_ratio(),
            "max_drawdown":  mdd["max_drawdown"],
            "calmar":        a.calmar_ratio(),
            "var95":         a.var(0.95),
            "cvar95":        a.cvar(0.95),
            "ann_return":    a.annualised_return(),
        }
    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR in /analyze:\n{tb}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


@app.post("/hedges")
def hedges(req: HedgeReq):
    try:
        tickers = _normalise_tickers(req.tickers)
        weights = _validate_weights(tickers, req.weights)
        _validate_portfolio_dates(req.start_date, req.end_date)
        a = PortfolioAnalyzer(
            tickers, weights,
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
        tickers = _normalise_tickers(req.tickers)
        weights = _validate_weights(tickers, req.weights)
        _validate_portfolio_dates(req.start_date, req.end_date)
        a = PortfolioAnalyzer(
            tickers, weights,
            req.start_date, req.end_date, "monthly",
        )
        a.fetch_prices()
        result = a.optimize_weights(
            expected_returns=req.expected_returns,
            risk_free_rate=req.risk_free_rate,
            long_only=req.long_only,
            max_position=req.max_position,
        )
        total = sum(weights)
        adjustments = {}
        for t in tickers:
            cur_d = result["current_weights"][t] * total
            opt_d = result["optimal_weights"][t] * total
            adjustments[t] = {
                "current_pct": result["current_weights"][t],
                "optimal_pct": result["optimal_weights"][t],
                "current_dollars": cur_d,
                "optimal_dollars": opt_d,
                "delta_dollars": opt_d - cur_d,
                "action": "BUY" if opt_d > cur_d + 0.01 else "SELL" if cur_d > opt_d + 0.01 else "HOLD",
            }
        result["adjustments"] = adjustments
        result["portfolio_value"] = total
        return result
    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR in /optimize:\n{tb}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


# ── Monte Carlo ──────────────────────────────────────────────────────────────
@app.post("/simulate")
def simulate(req: SimulateReq):
    try:
        tickers = _normalise_tickers(req.tickers)
        weights = _validate_weights(tickers, req.weights)
        _validate_portfolio_dates(req.start_date, req.end_date)
        a = PortfolioAnalyzer(
            tickers, weights,
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
        tickers = _normalise_tickers(req.tickers)
        weights = _validate_weights(tickers, req.weights)
        _validate_portfolio_dates(req.start_date, req.end_date)
        a = PortfolioAnalyzer(
            tickers, weights,
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
async def import_csv(
    file: UploadFile,
    portfolio_id: int,
    user: dict = Depends(require_user),
):
    """Import trades from a CSV file. Expected columns: ticker, date, action, quantity, price"""
    db = get_db()
    _get_owned_portfolio(db, portfolio_id, user["id"])
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
    # Normalise column names
    df.columns = [c.strip().lower() for c in df.columns]
    col_map = {"symbol": "ticker", "trade_date": "date"}
    df = df.rename(columns=col_map)

    required = {"ticker", "date", "action", "quantity", "price"}
    if not required.issubset(set(df.columns)):
        raise HTTPException(400, f"CSV must have columns: {required}. Got: {list(df.columns)}")

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
                portfolio_id=portfolio_id,
            )
            count += 1
        except Exception:
            continue
    return {"imported": count}


# ── Trades ────────────────────────────────────────────────────────────────────
@app.get("/trades")
def get_trades(portfolio_id: int, user: dict = Depends(require_user)):
    db = get_db()
    _get_owned_portfolio(db, portfolio_id, user["id"])
    return db.get_trades(user_id=user["id"], portfolio_id=portfolio_id).to_dict(orient="records")


@app.post("/trades")
def add_trade(t: TradeReq, user: dict = Depends(require_user)):
    db = get_db()
    _get_owned_portfolio(db, t.portfolio_id, user["id"])
    db.add_trade(
        t.ticker,
        t.trade_date,
        t.action,
        t.quantity,
        t.price,
        t.notes,
        portfolio_id=t.portfolio_id,
    )
    return {"ok": True}


@app.delete("/trades/{trade_id}")
def delete_trade(trade_id: int, user: dict = Depends(require_user)):
    deleted = get_db().delete_trade(trade_id, user_id=user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"ok": True}


@app.get("/portfolio")
def get_portfolio(portfolio_id: int, user: dict = Depends(require_user)):
    db = get_db()
    portfolio = _get_owned_portfolio(db, portfolio_id, user["id"])
    tickers, weights = db.get_portfolio(user_id=user["id"], portfolio_id=portfolio_id)
    return {
        "portfolio": portfolio,
        "tickers":   tickers,
        "weights":   weights,
        "positions": db.get_positions_summary(user_id=user["id"], portfolio_id=portfolio_id).to_dict(orient="records"),
    }


@app.get("/pnl")
def get_pnl(portfolio_id: int, user: dict = Depends(require_user)):
    db = get_db()
    _get_owned_portfolio(db, portfolio_id, user["id"])
    pnl = db.get_unrealized_pnl(user_id=user["id"], portfolio_id=portfolio_id)
    return pnl.to_dict(orient="records") if not pnl.empty else []


@app.get("/portfolio-value")
def get_portfolio_value(portfolio_id: int, user: dict = Depends(require_user)):
    db = get_db()
    _get_owned_portfolio(db, portfolio_id, user["id"])
    return _series(db.get_portfolio_value_history(user_id=user["id"], portfolio_id=portfolio_id))
