import { useState, useEffect } from "react";
import { api, Trade, PnLRow } from "../api";
import { SectionHeader } from "./Dashboard";
import Chart, { ACCENT, NEG, TXT2, BORDER } from "./Chart";

type Props = { onLoad: (tickers: string[], weights: number[]) => void };

const EMPTY = { ticker: "", trade_date: new Date().toISOString().split("T")[0], action: "BUY", quantity: "", price: "", notes: "" };

export default function TradeLog({ onLoad }: Props) {
  const [trades, setTrades]   = useState<Trade[]>([]);
  const [pnl, setPnl]         = useState<PnLRow[]>([]);
  const [portVal, setPortVal] = useState<{ date: string; value: number }[]>([]);
  const [form, setForm]       = useState({ ...EMPTY });
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState<string | null>(null);

  async function refresh() {
    const [t, p, v] = await Promise.all([api.getTrades(), api.getPnl(), api.getPortfolioValue()]);
    setTrades(t);
    setPnl(p);
    setPortVal(v);
    const portfolio = await api.getPortfolio();
    onLoad(portfolio.tickers, portfolio.weights);
  }

  useEffect(() => { refresh().catch(() => {}); }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.addTrade({
        ticker: form.ticker.toUpperCase().trim(),
        trade_date: form.trade_date,
        action: form.action,
        quantity: Number(form.quantity),
        price: Number(form.price),
        notes: form.notes,
      });
      setForm({ ...EMPTY });
      await refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function del(id: number) {
    await api.deleteTrade(id);
    await refresh();
  }

  const totalPnl = pnl.reduce((s, r) => s + r["Unrealized P&L"], 0);

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader>Trade Log &amp; P&amp;L</SectionHeader>

      {/* Summary cards */}
      {pnl.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-card border border-border rounded-2xl p-5">
            <div className="text-xs text-txt2 font-semibold uppercase tracking-widest mb-2">Total Unrealized P&L</div>
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

      {/* Portfolio value chart */}
      {portVal.length > 1 && (
        <div className="bg-card border border-border rounded-2xl p-4">
          <Chart
            data={[{
              x: portVal.map(p => p.date),
              y: portVal.map(p => p.value),
              mode: "lines", name: "Portfolio Value", fill: "tozeroy",
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

      {/* P&L table */}
      {pnl.length > 0 && (
        <div className="bg-card border border-border rounded-2xl p-5">
          <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-3">Open Positions</div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-txt2 text-xs uppercase tracking-wider border-b border-border">
                {["Ticker", "Qty", "Avg Cost", "Price", "Mkt Value", "P&L", "P&L %"].map(h => (
                  <th key={h} className={`pb-2 ${h === "Ticker" ? "text-left" : "text-right"}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pnl.map(r => {
                const pnlVal = r["Unrealized P&L"];
                const pnlPct = r["P&L %"];
                const cls = pnlVal >= 0 ? "text-pos" : "text-neg";
                return (
                  <tr key={r.Ticker} className="border-b border-border/40 hover:bg-card2/50">
                    <td className="py-2 font-bold text-txt">{r.Ticker}</td>
                    <td className="py-2 text-right tabular-nums text-txt2">{r["Net Qty"]}</td>
                    <td className="py-2 text-right tabular-nums text-txt2">${r["Avg Cost"].toFixed(2)}</td>
                    <td className="py-2 text-right tabular-nums text-txt">${r["Current Price"].toFixed(2)}</td>
                    <td className="py-2 text-right tabular-nums text-txt">${r["Market Value"].toLocaleString("en-US", { maximumFractionDigits: 0 })}</td>
                    <td className={`py-2 text-right tabular-nums font-semibold ${cls}`}>
                      {pnlVal >= 0 ? "+" : ""}${pnlVal.toLocaleString("en-US", { maximumFractionDigits: 0 })}
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

      {/* Add trade form */}
      <div className="bg-card border border-border rounded-2xl p-5">
        <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-4">Log a Trade</div>
        <form onSubmit={submit} className="grid grid-cols-3 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-txt2">Ticker</label>
            <input required value={form.ticker} placeholder="AAPL"
              onChange={e => setForm(f => ({ ...f, ticker: e.target.value }))} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-txt2">Date</label>
            <input type="date" required value={form.trade_date}
              onChange={e => setForm(f => ({ ...f, trade_date: e.target.value }))} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-txt2">Action</label>
            <select value={form.action} onChange={e => setForm(f => ({ ...f, action: e.target.value }))}
              className="bg-card2 border border-border rounded-lg px-3 py-2 text-sm text-txt">
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-txt2">Quantity</label>
            <input type="number" required min="0.001" step="any" value={form.quantity} placeholder="10"
              onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-txt2">Price ($)</label>
            <input type="number" required min="0.01" step="any" value={form.price} placeholder="150.00"
              onChange={e => setForm(f => ({ ...f, price: e.target.value }))} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-txt2">Notes (optional)</label>
            <input value={form.notes} placeholder="e.g. earnings play"
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
          </div>
          <div className="col-span-3 flex items-center gap-3">
            <button type="submit" disabled={saving}
              className="px-6 py-2.5 rounded-xl font-bold text-sm text-white transition-all
                bg-gradient-to-r from-accent to-accent2
                disabled:opacity-40 hover:opacity-90 active:scale-95">
              {saving ? "Saving…" : "+ Add Trade"}
            </button>
            {error && <p className="text-neg text-sm">{error}</p>}
          </div>
        </form>
      </div>

      {/* Trade history */}
      {trades.length > 0 && (
        <div className="bg-card border border-border rounded-2xl p-5">
          <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-3">Trade History</div>
          <div className="flex flex-col gap-1 max-h-72 overflow-y-auto">
            {[...trades].reverse().map(t => (
              <div key={t.id} className="flex items-center justify-between gap-2 py-2 border-b border-border/30 hover:bg-card2/40 px-2 rounded">
                <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${t.action === "BUY" ? "bg-accent/20 text-accent" : "bg-neg/20 text-neg"}`}>
                  {t.action}
                </span>
                <span className="font-semibold text-txt text-sm">{t.ticker}</span>
                <span className="text-txt2 text-xs tabular-nums">{t.quantity} @ ${t.price}</span>
                <span className="text-txt2 text-xs">{t.trade_date}</span>
                <span className="text-txt2 text-xs flex-1 truncate">{t.notes}</span>
                <button onClick={() => del(t.id)}
                  className="text-xs text-neg/50 hover:text-neg transition-colors px-1">✕</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
