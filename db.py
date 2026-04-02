"""
db.py — Persistent trade log
Automatically uses:
  - Supabase  when SUPABASE_URL + SUPABASE_KEY are available (web deployment)
  - SQLite    otherwise (local development, stored in trades.db)
"""

import sqlite3
from pathlib import Path
from typing import List, Tuple

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

# Supabase SQL to create the table (paste into Supabase SQL Editor):
SUPABASE_DDL = """
CREATE TABLE public.trades (
    id      bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    ticker  text   NOT NULL,
    trade_date date NOT NULL,
    action  text   NOT NULL CHECK (action IN ('BUY', 'SELL')),
    quantity numeric NOT NULL,
    price   numeric NOT NULL,
    notes   text    DEFAULT '',
    created_at timestamptz DEFAULT now()
);
ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all" ON public.trades FOR ALL USING (true);
"""

_EMPTY_COLS = ["id", "ticker", "trade_date", "action", "quantity", "price", "notes"]


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
                CREATE TABLE IF NOT EXISTS trades (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker     TEXT    NOT NULL,
                    trade_date TEXT    NOT NULL,
                    action     TEXT    NOT NULL,
                    quantity   REAL    NOT NULL,
                    price      REAL    NOT NULL,
                    notes      TEXT    DEFAULT '',
                    created_at TEXT    DEFAULT (datetime('now'))
                )
            """)

    # ── Public API ────────────────────────────────────────────────────────
    def add_trade(
        self,
        ticker: str,
        trade_date,   # date or str
        action: str,  # 'BUY' or 'SELL'
        quantity: float,
        price: float,
        notes: str = "",
    ) -> None:
        ticker = ticker.upper().strip()
        action = action.upper()
        if action not in ("BUY", "SELL"):
            raise ValueError("action must be BUY or SELL")

        if self._backend == "sqlite":
            with sqlite3.connect(SQLITE_PATH) as conn:
                conn.execute(
                    "INSERT INTO trades (ticker, trade_date, action, quantity, price, notes) "
                    "VALUES (?,?,?,?,?,?)",
                    (ticker, str(trade_date), action, float(quantity), float(price), notes),
                )
        else:
            self._sb.table("trades").insert({
                "ticker":     ticker,
                "trade_date": str(trade_date),
                "action":     action,
                "quantity":   float(quantity),
                "price":      float(price),
                "notes":      notes,
            }).execute()

    def get_trades(self) -> pd.DataFrame:
        if self._backend == "sqlite":
            with sqlite3.connect(SQLITE_PATH) as conn:
                df = pd.read_sql(
                    "SELECT * FROM trades ORDER BY trade_date DESC, id DESC", conn
                )
        else:
            resp = (
                self._sb.table("trades")
                .select("*")
                .order("trade_date", desc=True)
                .execute()
            )
            df = pd.DataFrame(resp.data)

        if df.empty:
            return pd.DataFrame(columns=_EMPTY_COLS)

        df["quantity"] = df["quantity"].astype(float)
        df["price"]    = df["price"].astype(float)
        return df

    def delete_trade(self, trade_id: int) -> None:
        if self._backend == "sqlite":
            with sqlite3.connect(SQLITE_PATH) as conn:
                conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        else:
            self._sb.table("trades").delete().eq("id", trade_id).execute()

    def get_portfolio(self) -> Tuple[List[str], List[float]]:
        """
        Derive current open positions from trade history.
        Returns (tickers, net_quantities) for positions whose net qty > 0.
        Weights are net quantities; PortfolioAnalyzer normalises them.
        """
        df = self.get_trades()
        if df.empty:
            return [], []

        df["signed"] = df.apply(
            lambda r: r["quantity"] if r["action"] == "BUY" else -r["quantity"],
            axis=1,
        )
        net = df.groupby("ticker")["signed"].sum()
        open_pos = net[net > 0.0001].sort_index()

        return open_pos.index.tolist(), open_pos.values.tolist()

    def get_positions_summary(self) -> pd.DataFrame:
        """
        Return a table with ticker, net_qty, avg_cost, total_cost_basis.
        Useful for the Trade Log tab display.
        """
        df = self.get_trades()
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

    def get_unrealized_pnl(self) -> pd.DataFrame:
        """
        Fetch live prices via yfinance and compute unrealized P&L for each
        open position.

        Returns a DataFrame with columns:
          Ticker, Net Qty, Avg Cost, Current Price, Market Value,
          Unrealized P&L, Unrealized P&L %
        """
        positions = self.get_positions_summary()
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

    def get_portfolio_value_history(self) -> pd.Series:
        """
        Reconstruct daily portfolio value from the trade log.
        Downloads price history for all ever-held tickers.
        Returns a Series of total portfolio value indexed by date.
        """
        trades = self.get_trades()
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

    @property
    def backend(self) -> str:
        return self._backend
