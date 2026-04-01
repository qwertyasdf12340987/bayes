"""
backend_main.py — FastAPI REST API
Start locally: uvicorn backend_main:app --reload
"""

import os
import traceback
from typing import List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


class TradeReq(BaseModel):
    ticker: str
    trade_date: str
    action: str
    quantity: float
    price: float
    notes: str = ""


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


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
