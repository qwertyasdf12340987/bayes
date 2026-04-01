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

    @property
    def backend(self) -> str:
        return self._backend
