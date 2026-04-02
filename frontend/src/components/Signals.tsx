import { useState, useEffect } from "react";
import { api, SignalData, MacroData } from "../api";
import { PortfolioParams } from "../App";
import { SectionHeader } from "./Dashboard";
import Metric from "./Metric";

function fmt(v: number | null | undefined, opts?: { prefix?: string; suffix?: string; decimals?: number }) {
  if (v == null) return "—";
  const d = opts?.decimals ?? 1;
  const s = v.toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d });
  return `${opts?.prefix ?? ""}${s}${opts?.suffix ?? ""}`;
}

function fmtBig(v: number | null | undefined) {
  if (v == null) return "—";
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v.toLocaleString()}`;
}

function recColor(rec: string | null) {
  if (!rec) return "text-txt2";
  if (rec.includes("buy") || rec.includes("strong")) return "text-pos";
  if (rec.includes("sell") || rec.includes("under")) return "text-neg";
  return "text-txt2";
}

function SignalCard({ signal }: { signal: SignalData }) {
  return (
    <div className="bg-card border border-border rounded-2xl p-5">
      <div className="flex items-center justify-between mb-3">
        <div>
          <span className="text-lg font-bold text-txt">{signal.ticker}</span>
          <span className="text-xs text-txt2 ml-2">{signal.name}</span>
        </div>
        {signal.recommendation && (
          <span className={`text-xs font-bold uppercase px-2 py-0.5 rounded ${recColor(signal.recommendation)} bg-card2`}>
            {signal.recommendation}
          </span>
        )}
      </div>
      <div className="text-xs text-txt2 mb-3">{signal.sector}</div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-txt2">Mkt Cap</span>
          <span className="text-txt tabular-nums">{fmtBig(signal.market_cap)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-txt2">P/E</span>
          <span className="text-txt tabular-nums">{fmt(signal.pe_ratio, { decimals: 1 })}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-txt2">Fwd P/E</span>
          <span className="text-txt tabular-nums">{fmt(signal.forward_pe, { decimals: 1 })}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-txt2">Beta</span>
          <span className="text-txt tabular-nums">{fmt(signal.beta, { decimals: 2 })}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-txt2">Div Yield</span>
          <span className="text-txt tabular-nums">{signal.dividend_yield != null ? fmt(signal.dividend_yield * 100, { suffix: "%" }) : "—"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-txt2">52W Range</span>
          <span className="text-txt tabular-nums text-xs">
            {fmt(signal.fifty_two_week_low, { prefix: "$", decimals: 0 })}–{fmt(signal.fifty_two_week_high, { prefix: "$", decimals: 0 })}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-txt2">Target</span>
          <span className="text-txt tabular-nums">{fmt(signal.target_price, { prefix: "$", decimals: 0 })}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-txt2">Analysts</span>
          <span className="text-txt tabular-nums">{signal.analyst_count ?? "—"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-txt2">P/C Ratio</span>
          <span className={`tabular-nums ${signal.put_call_ratio != null && signal.put_call_ratio > 1.0 ? "text-neg" : "text-txt"}`}>
            {fmt(signal.put_call_ratio, { decimals: 2 })}
          </span>
        </div>
        {signal.short_percent != null && (
          <div className="flex justify-between">
            <span className="text-txt2">Short %</span>
            <span className={`tabular-nums ${signal.short_percent > 0.1 ? "text-neg" : "text-txt"}`}>
              {fmt(signal.short_percent * 100, { suffix: "%", decimals: 1 })}
            </span>
          </div>
        )}
        {signal.earnings_date && (
          <div className="flex justify-between col-span-2 sm:col-span-1">
            <span className="text-txt2">Earnings</span>
            <span className="text-accent text-xs">{signal.earnings_date}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function Signals({ params }: { params: PortfolioParams }) {
  const [signals, setSignals] = useState<Record<string, SignalData>>({});
  const [macro, setMacro]     = useState<MacroData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [macroRes, ...sigRes] = await Promise.all([
        api.getMacro(),
        ...params.tickers.map(t => api.getSignals(t)),
      ]);
      setMacro(macroRes);
      const sigs: Record<string, SignalData> = {};
      params.tickers.forEach((t, i) => { sigs[t] = sigRes[i]; });
      setSignals(sigs);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader>Market Signals</SectionHeader>

      <div className="bg-card border border-border rounded-2xl p-6">
        <p className="text-txt2 text-sm mb-5">
          Fundamental data, analyst consensus, options flow, and macro indicators for your holdings.
          Data is cached for 1 hour.
        </p>
        <button onClick={load} disabled={loading}
          className="px-6 py-2.5 rounded-xl font-bold text-sm text-white transition-all
            bg-gradient-to-r from-accent to-accent2
            disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 active:scale-95">
          {loading ? "Loading signals..." : "Load Signals"}
        </button>
        {error && <p className="text-neg text-sm mt-3">{error}</p>}
      </div>

      {loading && (
        <div className="flex items-center gap-3 text-txt2 text-sm p-4">
          <div className="w-5 h-5 rounded-full border-2 border-accent border-t-transparent animate-spin" />
          Fetching market data for {params.tickers.length} holdings...
        </div>
      )}

      {macro && (
        <>
          <div className="text-xs text-txt2 uppercase tracking-wider font-semibold">Macro Environment</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <Metric label="VIX" value={fmt(macro.vix, { decimals: 1 })}
              positive={macro.vix != null ? macro.vix < 20 : undefined} />
            <Metric label="US 10Y Yield" value={fmt(macro.us10y, { suffix: "%", decimals: 2 })} />
            <Metric label="US 3M Yield" value={fmt(macro.us3m, { suffix: "%", decimals: 2 })} />
            <Metric label="SPY" value={fmt(macro.spy_price, { prefix: "$", decimals: 0 })} />
            <Metric label="SPY P/E" value={fmt(macro.spy_pe, { decimals: 1 })} />
          </div>
        </>
      )}

      {Object.keys(signals).length > 0 && (
        <>
          <div className="text-xs text-txt2 uppercase tracking-wider font-semibold">Holdings</div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {params.tickers.map(t => signals[t] && <SignalCard key={t} signal={signals[t]} />)}
          </div>
        </>
      )}
    </div>
  );
}
