import { useState } from "react";
import { api, HedgeRow } from "../api";
import { AnalysisResult } from "../api";
import { PortfolioParams } from "../App";
import { SectionHeader } from "./Dashboard";

function HedgeTable({ rows, title }: { rows: HedgeRow[]; title: string }) {
  if (!rows.length) return (
    <div className="bg-card border border-border rounded-2xl p-5">
      <div className="text-sm font-semibold text-txt mb-2">{title}</div>
      <p className="text-txt2 text-sm">No significant exposures to hedge.</p>
    </div>
  );
  return (
    <div className="bg-card border border-border rounded-2xl p-5">
      <div className="text-sm font-semibold text-txt mb-3">{title}</div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-txt2 text-xs uppercase tracking-wider border-b border-border">
            <th className="pb-2 text-left">Factor / Sector</th>
            <th className="pb-2 text-right">Port Beta</th>
            <th className="pb-2 text-left">Hedge ETF</th>
            <th className="pb-2 text-center">Dir.</th>
            <th className="pb-2 text-right">Notional</th>
            <th className="pb-2 text-right">~Shares</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-border/40 hover:bg-card2/50">
              <td className="py-2 font-medium text-txt">{r.factor ?? r.sector}</td>
              <td className="py-2 text-right tabular-nums text-txt2">{r.port_beta.toFixed(3)}</td>
              <td className="py-2 font-mono text-accent">{r.hedge_etf}</td>
              <td className={`py-2 text-center font-bold text-xs ${r.direction === "SHORT" ? "text-neg" : "text-pos"}`}>
                {r.direction}
              </td>
              <td className="py-2 text-right tabular-nums text-txt">
                ${Math.abs(r.notional).toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </td>
              <td className="py-2 text-right tabular-nums text-txt2">
                {r.approx_shares != null ? r.approx_shares.toFixed(1) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Hedges({ result, params }: { result: AnalysisResult; params: PortfolioParams }) {
  const [hedges, setHedges] = useState<{ factor_hedges: HedgeRow[]; industry_hedges: HedgeRow[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const portfolioValue = params.weights.reduce((s, w) => s + w, 0);
      const h = await api.hedges({
        tickers: params.tickers,
        weights: params.weights,
        start_date: params.startDate,
        end_date: params.endDate,
        include_industry: params.includeIndustry,
        portfolio_value: portfolioValue,
      });
      setHedges(h);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader>Factor-Neutral Hedge Suggestions</SectionHeader>

      <div className="bg-card border border-border rounded-2xl p-5">
        <p className="text-txt2 text-sm mb-4">
          Computes ETF positions needed to neutralise each significant factor exposure.
          Each hedge ETF is itself regressed on FF5+MOM so the notional is exact.
        </p>
        <button
          onClick={load}
          disabled={loading}
          className="px-6 py-2.5 rounded-xl font-bold text-sm text-white transition-all
            bg-gradient-to-r from-accent to-accent2
            disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 active:scale-95"
        >
          {loading ? "Computing hedges…" : "⚡ Compute Hedges"}
        </button>
        {error && (
          <p className="text-neg text-sm mt-3">{error}</p>
        )}
      </div>

      {loading && (
        <div className="flex items-center gap-3 text-txt2 text-sm p-4">
          <div className="w-5 h-5 rounded-full border-2 border-accent border-t-transparent animate-spin" />
          Downloading ETF data and running regressions…
        </div>
      )}

      {hedges && (
        <>
          <HedgeTable rows={hedges.factor_hedges}   title="Factor Hedges (FF5 + Momentum)" />
          {params.includeIndustry && (
            <HedgeTable rows={hedges.industry_hedges} title="Industry / Sector Hedges" />
          )}
          <div className="bg-card border border-border rounded-2xl p-4">
            <p className="text-xs text-txt2">
              <span className="font-semibold text-txt">How to read this:</span> A SHORT entry means you should
              sell (or short) that ETF to offset the exposure. Notional = dollar amount. Shares are approximate
              based on last close price. This is not financial advice.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
