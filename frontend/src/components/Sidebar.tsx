import { useState, useEffect } from "react";
import { api, AnalysisResult } from "../api";
import { PortfolioParams } from "../App";

type Props = {
  loading: boolean;
  setLoading: (v: boolean) => void;
  setResult: (v: AnalysisResult | null) => void;
  setParams: (v: PortfolioParams) => void;
  setError: (v: string | null) => void;
  setTab: (v: number) => void;
};

const fiveYearsAgo = () => {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 5);
  return d.toISOString().split("T")[0];
};
const today = () => new Date().toISOString().split("T")[0];

export default function Sidebar({ loading, setLoading, setResult, setParams, setError, setTab }: Props) {
  const [source, setSource] = useState<"manual" | "tradelog">("manual");
  const [rows, setRows]     = useState([{ ticker: "AAPL", amount: 10000 }, { ticker: "MSFT", amount: 8000 }, { ticker: "NVDA", amount: 7000 }]);
  const [startDate, setStart] = useState(fiveYearsAgo());
  const [endDate, setEnd]     = useState(today());
  const [industry, setIndustry] = useState(true);
  const [tlTickers, setTlTickers] = useState<string[]>([]);
  const [tlWeights, setTlWeights] = useState<number[]>([]);

  useEffect(() => {
    if (source === "tradelog") {
      api.getPortfolio().then(p => { setTlTickers(p.tickers); setTlWeights(p.weights); }).catch(() => {});
    }
  }, [source]);

  const tickers = source === "manual"
    ? rows.map(r => r.ticker.toUpperCase().trim()).filter(Boolean)
    : tlTickers;
  const weights = source === "manual"
    ? rows.map(r => r.amount).filter((_, i) => rows[i].ticker.trim())
    : tlWeights;

  async function run() {
    if (!tickers.length) return;
    setError(null);
    setLoading(true);
    try {
      const p: PortfolioParams = { tickers, weights, startDate, endDate, includeIndustry: industry };
      setParams(p);
      const res = await api.analyze({ tickers, weights, start_date: startDate, end_date: endDate, include_industry: industry });
      setResult(res);
      setTab(0);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-64 shrink-0 bg-[#0d0d16] border-r border-border flex flex-col h-full overflow-y-auto">
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-2">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-accent">
            <path d="M2 20 C6 20, 6 4, 12 4 S18 20, 22 20" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" fill="none"/>
            <path d="M2 20 C6 20, 8 10, 12 10 S18 20, 22 20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.4"/>
          </svg>
          <span className="text-xl font-extrabold text-txt">Bayes</span>
        </div>
      </div>

      <div className="p-4 flex-1 flex flex-col gap-4">
        {/* Source toggle */}
        <div className="flex rounded-lg overflow-hidden border border-border text-xs font-semibold">
          {(["manual", "tradelog"] as const).map(s => (
            <button key={s} onClick={() => setSource(s)}
              className={`flex-1 py-2 transition-all ${source === s ? "bg-accent text-white" : "text-txt2 hover:text-txt"}`}>
              {s === "manual" ? "Manual" : "Trade Log"}
            </button>
          ))}
        </div>

        {source === "manual" ? (
          <div className="flex flex-col gap-2">
            <div className="text-xs text-txt2 font-semibold uppercase tracking-wider">Holdings</div>
            <div className="grid grid-cols-2 gap-1 text-xs text-txt2 font-semibold px-1">
              <span>Ticker</span><span>Amount ($)</span>
            </div>
            {rows.map((row, i) => (
              <div key={i} className="grid grid-cols-2 gap-1">
                <input value={row.ticker} placeholder="AAPL"
                  onChange={e => setRows(r => r.map((x, j) => j === i ? { ...x, ticker: e.target.value } : x))}
                  className="text-sm" />
                <input type="number" value={row.amount} min={0}
                  onChange={e => setRows(r => r.map((x, j) => j === i ? { ...x, amount: +e.target.value } : x))}
                  className="text-sm" />
              </div>
            ))}
            <div className="flex gap-2">
              <button onClick={() => setRows(r => [...r, { ticker: "", amount: 0 }])}
                className="flex-1 py-1.5 rounded-lg border border-border text-xs text-txt2 hover:border-accent hover:text-accent transition-all">
                + Add row
              </button>
              {rows.length > 1 && (
                <button onClick={() => setRows(r => r.slice(0, -1))}
                  className="px-3 py-1.5 rounded-lg border border-border text-xs text-neg hover:border-neg transition-all">
                  −
                </button>
              )}
            </div>
          </div>
        ) : (
          <div>
            <div className="text-xs text-txt2 font-semibold uppercase tracking-wider mb-2">From Trade Log</div>
            {tlTickers.length ? (
              <div className="flex flex-col gap-1">
                {tlTickers.map((t, i) => (
                  <div key={t} className="flex justify-between text-sm">
                    <span className="font-semibold text-txt">{t}</span>
                    <span className="text-txt2">{tlWeights[i]?.toFixed(1)} shares</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-txt2">No trades logged yet. Go to Trade Log tab.</p>
            )}
          </div>
        )}

        <div className="border-t border-border pt-4 flex flex-col gap-2">
          <div className="text-xs text-txt2 font-semibold uppercase tracking-wider">Date Range</div>
          <div className="flex flex-col gap-1.5">
            <div className="text-xs text-txt2">From</div>
            <input type="date" value={startDate} onChange={e => setStart(e.target.value)} className="text-sm w-full" />
            <div className="text-xs text-txt2 mt-1">To</div>
            <input type="date" value={endDate} onChange={e => setEnd(e.target.value)} className="text-sm w-full" />
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-txt2 cursor-pointer">
          <input type="checkbox" checked={industry} onChange={e => setIndustry(e.target.checked)}
            className="accent-accent w-4 h-4" />
          Industry analysis
        </label>
      </div>

      <div className="p-4 border-t border-border">
        <button onClick={run} disabled={loading || !tickers.length}
          className="w-full py-3 rounded-xl font-bold text-sm text-white transition-all
            bg-gradient-to-r from-accent to-accent2
            disabled:opacity-40 disabled:cursor-not-allowed
            hover:opacity-90 active:scale-95">
          {loading ? "Running…" : "▶  Run Analysis"}
        </button>
      </div>
    </div>
  );
}
