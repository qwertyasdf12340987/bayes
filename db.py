"""
db.py — Persistent trade log + user/portfolio storage
Automatically uses:
  - Supabase  when SUPABASE_URL + SUPABASE_KEY are available (web deployment)
  - SQLite    otherwise (local development, stored in trades.db)
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf


def _yf_download(*args, **kwargs) -> pd.DataFrame:
    """Wrapper that flattens MultiIndex columns from newer yfinance versions."""
    df = yf.download(*args, **kwargs)
    if isinstance(df.columns, pd.MultiIndex):
        if df.columns.get_level_values(1).nunique() == 1:
            df.columns = df.columns.droplevel(1)
    return df

SQLITE_PATH = Path(__file__).parent / "trades.db"

# Supabase SQL to create the tables (paste into Supabase SQL Editor):
SUPABASE_DDL = """
-- Users table
CREATE TABLE public.users (
    id            bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    email         text   UNIQUE NOT NULL,
    name          text   NOT NULL DEFAULT '',
    password_hash text   NOT NULL,
    created_at    timestamptz DEFAULT now()
);
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all on users" ON public.users FOR ALL USING (true);

-- Portfolios table
CREATE TABLE public.portfolios (
    id          bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id     bigint NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name        text   NOT NULL DEFAULT 'My Portfolio',
    tickers     jsonb  NOT NULL DEFAULT '[]',
    weights     jsonb  NOT NULL DEFAULT '[]',
    start_date  text   DEFAULT '',
    end_date    text   DEFAULT '',
    created_at  timestamptz DEFAULT now(),
    updated_at  timestamptz DEFAULT now()
);
ALTER TABLE public.portfolios ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all on portfolios" ON public.portfolios FOR ALL USING (true);

-- Trades table
CREATE TABLE public.trades (
    id           bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    ticker       text   NOT NULL,
    trade_date   date   NOT NULL,
    action       text   NOT NULL CHECK (action IN ('BUY', 'SELL')),
    quantity     numeric NOT NULL,
    price        numeric NOT NULL,
    notes        text    DEFAULT '',
    portfolio_id bigint  REFERENCES public.portfolios(id) ON DELETE SET NULL,
    created_at   timestamptz DEFAULT now()
);
ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all on trades" ON public.trades FOR ALL USING (true);
"""

_EMPTY_COLS = ["id", "ticker", "trade_date", "action", "quantity", "price", "notes", "portfolio_id"]


class TradeDB:
    """
    CRUD interface for the trade log.

    Parameters
    ----------
    supabase_url : str  — project URL from Supabase dashboard
    supabase_key : str  — anon/public key from Supabase dashboard
    If both are empty the class falls back to SQLite.
    """

    def __init__(self, supabase_url: str = "", supabase_key: str = "") -> None:
        if supabase_url and supabase_key:
            self._backend = "supabase"
            try:
                from supabase import create_client
                self._sb = create_client(supabase_url, supabase_key)
            except ImportError:
                raise ImportError("Run: python3 -m pip install supabase")
        else:
            self._backend = "sqlite"
            self._init_sqlite()

    # ── SQLite init ───────────────────────────────────────────────────────
    def _init_sqlite(self) -> None:
        with sqlite3.connect(SQLITE_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    email         TEXT    UNIQUE NOT NULL,
                    name          TEXT    NOT NULL DEFAULT '',
                    password_hash TEXT    NOT NULL,
                    created_at    TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS portfolios (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name        TEXT    NOT NULL DEFAULT 'My Portfolio',
                    tickers     TEXT    NOT NULL DEFAULT '[]',
                    weights     TEXT    NOT NULL DEFAULT '[]',
                    start_date  TEXT    DEFAULT '',
                    end_date    TEXT    DEFAULT '',
                    created_at  TEXT    DEFAULT (datetime('now')),
                    updated_at  TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker       TEXT    NOT NULL,
                    trade_date   TEXT    NOT NULL,
                    action       TEXT    NOT NULL,
                    quantity     REAL    NOT NULL,
                    price        REAL    NOT NULL,
                    notes        TEXT    DEFAULT '',
                    portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE SET NULL,
                    created_at   TEXT    DEFAULT (datetime('now'))
                )
            """)
            # Migration: add portfolio_id to existing trades table if missing
            try:
                conn.execute("SELECT portfolio_id FROM trades LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE trades ADD COLUMN portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE SET NULL")

    # ── Public API ────────────────────────────────────────────────────────
    def add_trade(
        self,
        ticker: str,
        trade_date,   # date or str
        action: str,  # 'BUY' or 'SELL'
        quantity: float,
        price: float,
        notes: str = "",
        portfolio_id: Optional[int] = None,
    ) -> None:
        ticker = ticker.upper().strip()
        action = action.upper()
        if action not in ("BUY", "SELL"):
            raise ValueError("action must be BUY or SELL")

        if self._backend == "sqlite":
            with sqlite3.connect(SQLITE_PATH) as conn:
                conn.execute(
                    "INSERT INTO trades (ticker, trade_date, action, quantity, price, notes, portfolio_id) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (ticker, str(trade_date), action, float(quantity), float(price), notes, portfolio_id),
                )
        else:
            self._sb.table("trades").insert({
                "ticker":     ticker,
                "trade_date": str(trade_date),
                "action":     action,
                "quantity":   float(quantity),
                "price":      float(price),
                "notes":      notes,
                "portfolio_id": portfolio_id,
            }).execute()

    def get_trades(
        self,
        user_id: Optional[int] = None,
        portfolio_id: Optional[int] = None,
    ) -> pd.DataFrame:
        if self._backend == "sqlite":
            with sqlite3.connect(SQLITE_PATH) as conn:
                if user_id is not None:
                    query = """
                        SELECT t.*
                        FROM trades t
                        JOIN portfolios p ON p.id = t.portfolio_id
                        WHERE p.user_id = ?
                    """
                    params: list = [user_id]
                    if portfolio_id is not None:
                        query += " AND t.portfolio_id = ?"
                        params.append(portfolio_id)
                    query += " ORDER BY t.trade_date DESC, t.id DESC"
                    df = pd.read_sql(query, conn, params=params)
                elif portfolio_id is not None:
                    df = pd.read_sql(
                        "SELECT * FROM trades WHERE portfolio_id = ? ORDER BY trade_date DESC, id DESC",
                        conn,
                        params=[portfolio_id],
                    )
                else:
                    df = pd.read_sql(
                        "SELECT * FROM trades ORDER BY trade_date DESC, id DESC", conn
                    )
        else:
            query = self._sb.table("trades").select("*")
            if portfolio_id is not None:
                query = query.eq("portfolio_id", portfolio_id)
            elif user_id is not None:
                portfolio_ids = [p["id"] for p in self.get_portfolios(user_id)]
                if not portfolio_ids:
                    return pd.DataFrame(columns=_EMPTY_COLS)
                query = query.in_("portfolio_id", portfolio_ids)
            resp = query.order("trade_date", desc=True).execute()
            df = pd.DataFrame(resp.data)

        if df.empty:
            return pd.DataFrame(columns=_EMPTY_COLS)

        df["quantity"] = df["quantity"].astype(float)
        df["price"]    = df["price"].astype(float)
        return df

    def delete_trade(
        self,
        trade_id: int,
        user_id: Optional[int] = None,
        portfolio_id: Optional[int] = None,
    ) -> bool:
        if self._backend == "sqlite":
            with sqlite3.connect(SQLITE_PATH) as conn:
                if user_id is not None:
                    cur = conn.execute(
                        """
                        DELETE FROM trades
                        WHERE id = ? AND portfolio_id IN (
                            SELECT id FROM portfolios WHERE user_id = ?
                        )
                        """,
                        (trade_id, user_id),
                    )
                elif portfolio_id is not None:
                    cur = conn.execute(
                        "DELETE FROM trades WHERE id = ? AND portfolio_id = ?",
                        (trade_id, portfolio_id),
                    )
                else:
                    cur = conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
                return cur.rowcount > 0
        else:
            query = self._sb.table("trades").delete().eq("id", trade_id)
            if portfolio_id is not None:
                query = query.eq("portfolio_id", portfolio_id)
            elif user_id is not None:
                portfolio_ids = [p["id"] for p in self.get_portfolios(user_id)]
                if not portfolio_ids:
                    return False
                query = query.in_("portfolio_id", portfolio_ids)
            resp = query.execute()
            return bool(resp.data)

    def get_portfolio(
        self,
        user_id: Optional[int] = None,
        portfolio_id: Optional[int] = None,
    ) -> Tuple[List[str], List[float]]:
        """
        Derive current open positions from trade history.
        Returns (tickers, net_quantities) for positions whose net qty > 0.
        Weights are net quantities; PortfolioAnalyzer normalises them.
        """
        df = self.get_trades(user_id=user_id, portfolio_id=portfolio_id)
        if df.empty:
            return [], []

        df["signed"] = df.apply(
            lambda r: r["quantity"] if r["action"] == "BUY" else -r["quantity"],
            axis=1,
        )
        net = df.groupby("ticker")["signed"].sum()
        open_pos = net[net > 0.0001].sort_index()

        return open_pos.index.tolist(), open_pos.values.tolist()

    def get_positions_summary(
        self,
        user_id: Optional[int] = None,
        portfolio_id: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Return a table with ticker, net_qty, avg_cost, total_cost_basis.
        Useful for the Trade Log tab display.
        """
        df = self.get_trades(user_id=user_id, portfolio_id=portfolio_id)
        if df.empty:
            return pd.DataFrame(columns=["Ticker", "Net Qty", "Avg Cost", "Cost Basis"])

        rows = []
        for ticker, group in df.groupby("ticker"):
            buys  = group[group["action"] == "BUY"]
            sells = group[group["action"] == "SELL"]
            net_qty = buys["quantity"].sum() - sells["quantity"].sum()
            if net_qty <= 0:
                continue
            avg_cost = (
                (buys["quantity"] * buys["price"]).sum() / buys["quantity"].sum()
                if len(buys) else 0.0
            )
            rows.append({
                "Ticker":      ticker,
                "Net Qty":     round(net_qty, 4),
                "Avg Cost":    round(avg_cost, 2),
                "Cost Basis":  round(avg_cost * net_qty, 2),
            })

        return pd.DataFrame(rows).sort_values("Ticker").reset_index(drop=True)

    def get_unrealized_pnl(
        self,
        user_id: Optional[int] = None,
        portfolio_id: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Fetch live prices via yfinance and compute unrealized P&L for each
        open position.

        Returns a DataFrame with columns:
          Ticker, Net Qty, Avg Cost, Current Price, Market Value,
          Unrealized P&L, Unrealized P&L %
        """
        positions = self.get_positions_summary(user_id=user_id, portfolio_id=portfolio_id)
        if positions.empty:
            return pd.DataFrame()

        tickers = positions["Ticker"].tolist()
        try:
            raw = _yf_download(tickers, period="1d", auto_adjust=True, progress=False)
            if len(tickers) == 1:
                prices = {tickers[0]: float(raw["Close"].iloc[-1])}
            else:
                prices = {t: float(raw["Close"][t].iloc[-1]) for t in tickers
                          if t in raw["Close"].columns}
        except Exception:
            prices = {}

        rows = []
        for _, row in positions.iterrows():
            t       = row["Ticker"]
            net_qty = float(row["Net Qty"])
            avg_cost = float(row["Avg Cost"])
            cur_px  = prices.get(t)
            if cur_px is None:
                continue
            mkt_val  = net_qty * cur_px
            cost_bas = net_qty * avg_cost
            pnl      = mkt_val - cost_bas
            pnl_pct  = pnl / cost_bas * 100 if cost_bas else 0
            rows.append({
                "Ticker":          t,
                "Net Qty":         net_qty,
                "Avg Cost":        avg_cost,
                "Current Price":   cur_px,
                "Market Value":    mkt_val,
                "Unrealized P&L":  pnl,
                "P&L %":           pnl_pct,
            })

        return pd.DataFrame(rows)

    def get_portfolio_value_history(
        self,
        user_id: Optional[int] = None,
        portfolio_id: Optional[int] = None,
    ) -> pd.Series:
        """
        Reconstruct daily portfolio value from the trade log.
        Downloads price history for all ever-held tickers.
        Returns a Series of total portfolio value indexed by date.
        """
        trades = self.get_trades(user_id=user_id, portfolio_id=portfolio_id)
        if trades.empty:
            return pd.Series(dtype=float, name="Portfolio Value")

        trades["trade_date"] = pd.to_datetime(trades["trade_date"])
        all_tickers = trades["ticker"].unique().tolist()
        start = trades["trade_date"].min().strftime("%Y-%m-%d")

        # Download daily prices for all tickers
        raw = _yf_download(all_tickers, start=start, auto_adjust=True, progress=False)
        if len(all_tickers) == 1:
            prices = raw[["Close"]].rename(columns={"Close": all_tickers[0]})
        else:
            prices = raw["Close"]
        prices = prices.ffill()

        # Walk forward day by day: maintain running holdings dict
        trades_sorted = trades.sort_values("trade_date")
        holdings: dict = {}
        trade_idx = 0
        n_trades  = len(trades_sorted)
        port_values = {}

        for day in prices.index:
            # Apply all trades on or before this day
            while trade_idx < n_trades:
                row = trades_sorted.iloc[trade_idx]
                # Safely compare dates, handling timezone-aware/naive
                trade_ts = pd.Timestamp(row["trade_date"])
                day_cmp = day.tz_localize(None) if day.tzinfo else day
                if trade_ts <= day_cmp:
                    t  = row["ticker"]
                    dq = row["quantity"] if row["action"] == "BUY" else -row["quantity"]
                    holdings[t] = holdings.get(t, 0) + dq
                    trade_idx += 1
                else:
                    break

            # Compute portfolio value
            val = 0.0
            for t, qty in holdings.items():
                if qty > 0 and t in prices.columns:
                    px = prices[t].get(day, float("nan"))
                    if not pd.isna(px):
                        val += qty * px
            if val > 0:
                port_values[day] = val

        return pd.Series(port_values, name="Portfolio Value")

    # ── User methods ─────────────────────────────────────────────────────
    def create_user(self, email: str, name: str, password_hash: str) -> Dict[str, Any]:
        email = email.lower().strip()
        if self._backend == "sqlite":
            with sqlite3.connect(SQLITE_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
                    (email, name, password_hash),
                )
                row = conn.execute(
                    "SELECT id, email, name, created_at FROM users WHERE id = ?",
                    (cur.lastrowid,),
                ).fetchone()
                return dict(row)
        else:
            resp = self._sb.table("users").insert({
                "email": email, "name": name, "password_hash": password_hash,
            }).execute()
            u = resp.data[0]
            return {"id": u["id"], "email": u["email"], "name": u["name"], "created_at": u["created_at"]}

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        email = email.lower().strip()
        if self._backend == "sqlite":
            with sqlite3.connect(SQLITE_PATH) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT id, email, name, password_hash, created_at FROM users WHERE email = ?",
                    (email,),
                ).fetchone()
                return dict(row) if row else None
        else:
            resp = self._sb.table("users").select("*").eq("email", email).execute()
            if not resp.data:
                return None
            u = resp.data[0]
            return {"id": u["id"], "email": u["email"], "name": u["name"],
                    "password_hash": u["password_hash"], "created_at": u["created_at"]}

    # ── Portfolio methods ──────────────────────────────────────────────────
    def create_portfolio(
        self, user_id: int, name: str, tickers: List[str],
        weights: List[float], start_date: str = "", end_date: str = "",
    ) -> Dict[str, Any]:
        if self._backend == "sqlite":
            with sqlite3.connect(SQLITE_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "INSERT INTO portfolios (user_id, name, tickers, weights, start_date, end_date) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, name, json.dumps(tickers), json.dumps(weights), start_date, end_date),
                )
                row = conn.execute(
                    "SELECT * FROM portfolios WHERE id = ?", (cur.lastrowid,)
                ).fetchone()
                return self._portfolio_row_to_dict(dict(row))
        else:
            resp = self._sb.table("portfolios").insert({
                "user_id": user_id, "name": name,
                "tickers": tickers, "weights": weights,
                "start_date": start_date, "end_date": end_date,
            }).execute()
            return self._portfolio_row_to_dict(resp.data[0])

    def get_portfolios(self, user_id: int) -> List[Dict[str, Any]]:
        if self._backend == "sqlite":
            with sqlite3.connect(SQLITE_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM portfolios WHERE user_id = ? ORDER BY updated_at DESC",
                    (user_id,),
                ).fetchall()
                return [self._portfolio_row_to_dict(dict(r)) for r in rows]
        else:
            resp = (
                self._sb.table("portfolios")
                .select("*")
                .eq("user_id", user_id)
                .order("updated_at", desc=True)
                .execute()
            )
            return [self._portfolio_row_to_dict(r) for r in resp.data]

    def get_portfolio_by_id(self, portfolio_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        if self._backend == "sqlite":
            with sqlite3.connect(SQLITE_PATH) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM portfolios WHERE id = ? AND user_id = ?",
                    (portfolio_id, user_id),
                ).fetchone()
                return self._portfolio_row_to_dict(dict(row)) if row else None
        else:
            resp = (
                self._sb.table("portfolios")
                .select("*")
                .eq("id", portfolio_id)
                .eq("user_id", user_id)
                .execute()
            )
            if not resp.data:
                return None
            return self._portfolio_row_to_dict(resp.data[0])

    def update_portfolio(
        self, portfolio_id: int, user_id: int, **fields,
    ) -> Optional[Dict[str, Any]]:
        # Only allow updating known fields
        allowed = {"name", "tickers", "weights", "start_date", "end_date"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return self.get_portfolio_by_id(portfolio_id, user_id)

        if self._backend == "sqlite":
            # Serialise lists to JSON for SQLite
            for k in ("tickers", "weights"):
                if k in updates and isinstance(updates[k], list):
                    updates[k] = json.dumps(updates[k])
            updates["updated_at"] = datetime.utcnow().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [portfolio_id, user_id]
            with sqlite3.connect(SQLITE_PATH) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute(
                    f"UPDATE portfolios SET {set_clause} WHERE id = ? AND user_id = ?",
                    vals,
                )
                row = conn.execute(
                    "SELECT * FROM portfolios WHERE id = ? AND user_id = ?",
                    (portfolio_id, user_id),
                ).fetchone()
                return self._portfolio_row_to_dict(dict(row)) if row else None
        else:
            updates["updated_at"] = datetime.utcnow().isoformat()
            resp = (
                self._sb.table("portfolios")
                .update(updates)
                .eq("id", portfolio_id)
                .eq("user_id", user_id)
                .execute()
            )
            if not resp.data:
                return None
            return self._portfolio_row_to_dict(resp.data[0])

    def delete_portfolio(self, portfolio_id: int, user_id: int) -> bool:
        if self._backend == "sqlite":
            with sqlite3.connect(SQLITE_PATH) as conn:
                cur = conn.execute(
                    "DELETE FROM portfolios WHERE id = ? AND user_id = ?",
                    (portfolio_id, user_id),
                )
                return cur.rowcount > 0
        else:
            resp = (
                self._sb.table("portfolios")
                .delete()
                .eq("id", portfolio_id)
                .eq("user_id", user_id)
                .execute()
            )
            return bool(resp.data)

    @staticmethod
    def _portfolio_row_to_dict(row: dict) -> Dict[str, Any]:
        """Normalise a portfolio row — parse JSON strings for SQLite backend."""
        result = dict(row)
        for key in ("tickers", "weights"):
            val = result.get(key, "[]")
            if isinstance(val, str):
                result[key] = json.loads(val)
        return result

    @property
    def backend(self) -> str:
        return self._backend
