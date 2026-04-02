import { useEffect, useState } from "react";
import { api, PnLRow, Trade } from "../api";
import { SectionHeader } from "./Dashboard";
import Chart, { ACCENT, BORDER } from "./Chart";

type Props = {
  portfolioId: number;
  portfolioName: string;
  onLoad: (tickers: string[], weights: number[]) => void;
};

const EMPTY = {
  ticker: "",
  trade_date: new Date().toISOString().split("T")[0],
  action: "BUY",
  quantity: "",
  price: "",
  notes: "",
};

export default function TradeLog({ portfolioId, portfolioName, onLoad }: Props) {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [pnl, setPnl] = useState<PnLRow[]>([]);
  const [portVal, setPortVal] = useState<{ date: string; value: number }[]>([]);
  const [form, setForm] = useState({ ...EMPTY });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const [tradeData, pnlData, valueData, portfolio] = await Promise.all([
        api.getTrades(portfolioId),
        api.getPnl(portfolioId),
        api.getPortfolioValue(portfolioId),
        api.getPortfolio(portfolioId),
      ]);
      setTrades(tradeData);
      setPnl(pnlData);
      setPortVal(valueData);
      onLoad(portfolio.tickers, portfolio.weights);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh().catch((err: any) => setError(err.message));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [portfolioId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.addTrade({
        portfolio_id: portfolioId,
        ticker: form.ticker.toUpperCase().trim(),
        trade_date: form.trade_date,
        action: form.action,
        quantity: Number(form.quantity),
        price: Number(form.price),
        notes: form.notes,
      });
      setForm({ ...EMPTY });
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function removeTrade(id: number) {
    setError(null);
    try {
      await api.deleteTrade(id);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  const totalPnl = pnl.reduce((sum, row) => sum + row["Unrealized P&L"], 0);

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader>{portfolioName} Trade Log</SectionHeader>

      {error && <div className="rounded-xl border border-neg/30 bg-neg/10 px-4 py-3 text-sm text-neg">{error}</div>}
      {loading && (
        <div className="flex items-center gap-3 text-txt2 text-sm p-4">
          <div className="w-5 h-5 rounded-full border-2 border-accent border-t-transparent animate-spin" />
          Refreshing portfolio trades...
        </div>
      )}

      {pnl.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-card border border-border rounded-2xl p-5">
            <div className="text-xs text-txt2 font-semibold uppercase tracking-widest mb-2">Total Unrealized P&amp;L</div>
            <div className={`text-2xl font-extrabold ${totalPnl >= 0 ? "text-pos" : "text-neg"}`}>
              {totalPnl >= 0 ? "+" : ""}${totalPnl.toLocaleString("en-US", { maximumFractionDigits: 0 })}
            </div>
          </div>
          <div className="bg-card border border-border rounded-2xl p-5">
            <div className="text-xs text-txt2 font-semibold uppercase tracking-widest mb-2">Positions</div>
            <div className="text-2xl font-extrabold text-txt">{pnl.length}</div>
          </div>
          <div className="bg-card border border-border rounded-2xl p-5">
            <div className="text-xs text-txt2 font-semibold uppercase tracking-widest mb-2">Total Trades</div>
            <div className="text-2xl font-extrabold text-txt">{trades.length}</div>
          </div>
        </div>
      )}

      {portVal.length > 1 && (
        <div className="bg-card border border-border rounded-2xl p-4">
          <Chart
            data={[{
              x: portVal.map((point) => point.date),
              y: portVal.map((point) => point.value),
              mode: "lines",
              name: "Portfolio Value",
              fill: "tozeroy",
              line: { color: ACCENT, width: 2.5 },
              fillcolor: "rgba(217,70,239,0.10)",
            } as any]}
            layout={{
              title: { text: "Portfolio Value History", font: { size: 15, color: "#f0f0ff" } },
              yaxis: { title: { text: "Value ($)" }, gridcolor: BORDER, tickprefix: "$" },
              xaxis: { gridcolor: BORDER },
            } as any}
            height={260}
          />
        </div>
      )}

      {pnl.length > 0 && (
        <div className="bg-card border border-border rounded-2xl p-5">
          <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-3">Open Positions</div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-txt2 text-xs uppercase tracking-wider border-b border-border">
                {["Ticker", "Qty", "Avg Cost", "Price", "Mkt Value", "P&L", "P&L %"].map((heading) => (
                  <th key={heading} className={`pb-2 ${heading === "Ticker" ? "text-left" : "text-right"}`}>{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pnl.map((row) => {
                const pnlValue = row["Unrealized P&L"];
                const pnlPct = row["P&L %"];
                const cls = pnlValue >= 0 ? "text-pos" : "text-neg";
                return (
                  <tr key={row.Ticker} className="border-b border-border/40 hover:bg-card2/50">
                    <td className="py-2 font-bold text-txt">{row.Ticker}</td>
                    <td className="py-2 text-right tabular-nums text-txt2">{row["Net Qty"]}</td>
                    <td className="py-2 text-right tabular-nums text-txt2">${row["Avg Cost"].toFixed(2)}</td>
                    <td className="py-2 text-right tabular-nums text-txt">${row["Current Price"].toFixed(2)}</td>
                    <td className="py-2 text-right tabular-nums text-txt">${row["Market Value"].toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                    <td className={`py-2 text-right tabular-nums font-semibold ${cls}`}>
                      {pnlValue >= 0 ? "+" : ""}${pnlValue.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </td>
                    <td className={`py-2 text-right tabular-nums font-semibold ${cls}`}>
                      {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(1)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="bg-card border border-border rounded-2xl p-5">
        <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-4">Log a Trade</div>
        <form onSubmit={submit} className="grid grid-cols-3 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-txt2">Ticker</label>
            <input required value={form.ticker} placeholder="AAPL" onChange={(e) => setForm((current) => ({ ...current, ticker: e.target.value }))} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-txt2">Date</label>
            <input type="date" required value={form.trade_date} onChange={(e) => setForm((current) => ({ ...current, trade_date: e.target.value }))} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-txt2">Action</label>
            <select
              value={form.action}
              onChange={(e) => setForm((current) => ({ ...current, action: e.target.value }))}
              className="bg-card2 border border-border rounded-lg px-3 py-2 text-sm text-txt"
            >
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-txt2">Quantity</label>
            <input type="number" required min="0.001" step="any" value={form.quantity} placeholder="10" onChange={(e) => setForm((current) => ({ ...current, quantity: e.target.value }))} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-txt2">Price ($)</label>
            <input type="number" required min="0.01" step="any" value={form.price} placeholder="150.00" onChange={(e) => setForm((current) => ({ ...current, price: e.target.value }))} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-txt2">Notes (optional)</label>
            <input value={form.notes} placeholder="e.g. earnings play" onChange={(e) => setForm((current) => ({ ...current, notes: e.target.value }))} />
          </div>
          <div className="col-span-3 flex items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 rounded-xl font-bold text-sm text-white transition-all bg-gradient-to-r from-accent to-accent2 disabled:opacity-40 hover:opacity-90 active:scale-95"
            >
              {saving ? "Saving…" : "+ Add Trade"}
            </button>
          </div>
        </form>
      </div>

      {trades.length > 0 && (
        <div className="bg-card border border-border rounded-2xl p-5">
          <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-3">Trade History</div>
          <div className="flex flex-col gap-1 max-h-72 overflow-y-auto">
            {trades.map((trade) => (
              <div key={trade.id} className="flex items-center justify-between gap-2 py-2 border-b border-border/30 hover:bg-card2/40 px-2 rounded">
                <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${trade.action === "BUY" ? "bg-accent/20 text-accent" : "bg-neg/20 text-neg"}`}>
                  {trade.action}
                </span>
                <span className="font-semibold text-txt text-sm">{trade.ticker}</span>
                <span className="text-txt2 text-xs tabular-nums">{trade.quantity} @ ${trade.price}</span>
                <span className="text-txt2 text-xs">{trade.trade_date}</span>
                <span className="text-txt2 text-xs flex-1 truncate">{trade.notes}</span>
                <button onClick={() => removeTrade(trade.id)} className="text-xs text-neg/50 hover:text-neg transition-colors px-1">
                  x
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
