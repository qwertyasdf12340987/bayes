import { useState } from "react";
import { api, KellyResult, AnalysisResult } from "../api";
import { PortfolioParams } from "../App";
import { SectionHeader } from "./Dashboard";
import Chart, { ACCENT, TXT2, BORDER, PALETTE, NEG } from "./Chart";
import Metric from "./Metric";

const FRACTIONS = [
  { label: "Full Kelly", value: 1.0 },
  { label: "¾ Kelly",    value: 0.75 },
  { label: "½ Kelly",    value: 0.5 },
  { label: "¼ Kelly",    value: 0.25 },
];

function fmt(v: number, decimals = 1) {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(decimals)}%`;
}

export default function Kelly({ result, params }: { result: AnalysisResult; params: PortfolioParams }) {
  const tickers = params.tickers;
  const [er, setEr]           = useState<Record<string, string>>(Object.fromEntries(tickers.map(t => [t, ""])));
  const [rf, setRf]           = useState("5");
  const [fraction, setFraction] = useState(0.5);
  const [shrinkage, setShrinkage] = useState(true);
  const [res, setRes]         = useState<KellyResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  async function run() {
    const missing = tickers.filter(t => !er[t] || isNaN(Number(er[t])));
    if (missing.length) { setError(`Enter expected return for: ${missing.join(", ")}`); return; }
    setLoading(true); setError(null);
    try {
      const r = await api.kelly({
        tickers: params.tickers,
        weights: params.weights,
        start_date: params.startDate,
        end_date: params.endDate,
        expected_returns: Object.fromEntries(tickers.map(t => [t, Number(er[t]) / 100])),
        risk_free_rate: Number(rf) / 100,
        fraction,
        use_shrinkage: shrinkage,
      });
      setRes(r);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const isLeveraged = res && res.kelly_leverage > 1.05;

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader>Kelly Criterion</SectionHeader>

      {/* Theory card */}
      <div className="bg-card border border-border rounded-2xl p-5">
        <p className="text-txt2 text-sm leading-relaxed">
          The <span className="text-txt font-semibold">Kelly Criterion</span> finds the position sizes that maximise
          long-run log-wealth growth. The multi-asset formula is{" "}
          <span className="font-mono text-accent">f* = Σ⁻¹(μ − r_f)</span> where Σ is the covariance matrix
          and μ your expected returns. Full Kelly maximises growth but has extreme drawdowns —
          most practitioners use <span className="text-txt font-semibold">half Kelly</span> as a practical compromise.
        </p>
      </div>

      {/* Inputs */}
      <div className="bg-card border border-border rounded-2xl p-6">
        <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-4">Expected Annualised Returns</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
          {tickers.map(t => (
            <div key={t} className="flex items-center gap-3 bg-card2/40 border border-border/50 rounded-xl px-4 py-3">
              <span className="text-sm font-bold text-txt w-16">{t}</span>
              <input
                type="number" step="any" placeholder="e.g. 15"
                value={er[t] ?? ""}
                onChange={e => setEr(prev => ({ ...prev, [t]: e.target.value }))}
                className="flex-1 bg-transparent border-b border-border/60 text-sm text-txt
                  placeholder:text-txt2/40 focus:border-accent outline-none py-1 tabular-nums text-right"
              />
              <span className="text-xs text-txt2">%</span>
            </div>
          ))}
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-4 mb-5">
          {/* Fraction selector */}
          <div className="flex rounded-lg overflow-hidden border border-border">
            {FRACTIONS.map(f => (
              <button key={f.value} onClick={() => setFraction(f.value)}
                className={`px-3 py-1.5 text-xs font-semibold transition-all ${
                  fraction === f.value ? "bg-accent text-white" : "text-txt2 hover:text-txt"
                }`}>
                {f.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-txt2">Risk-free rate</span>
            <input type="number" step="0.1" value={rf}
              onChange={e => setRf(e.target.value)}
              className="w-16 bg-card2 border border-border rounded-lg px-2 py-1.5 text-sm text-txt text-right" />
            <span className="text-xs text-txt2">%</span>
          </div>
          <label className="flex items-center gap-2 text-sm text-txt2 cursor-pointer select-none">
            <input type="checkbox" checked={shrinkage} onChange={e => setShrinkage(e.target.checked)}
              className="accent-[#d946ef] w-4 h-4 rounded" />
            Ledoit-Wolf shrinkage
          </label>
        </div>

        <button onClick={run} disabled={loading}
          className="px-6 py-2.5 rounded-xl font-bold text-sm text-white transition-all
            bg-gradient-to-r from-accent to-accent2
            disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 active:scale-95">
          {loading ? "Computing…" : "Compute Kelly Sizes"}
        </button>
        {error && <p className="text-neg text-sm mt-3">{error}</p>}
      </div>

      {loading && (
        <div className="flex items-center gap-3 text-txt2 text-sm p-4">
          <div className="w-5 h-5 rounded-full border-2 border-accent border-t-transparent animate-spin" />
          Computing Kelly-optimal positions…
        </div>
      )}

      {res && (
        <>
          {/* Leverage warning */}
          {isLeveraged && (
            <div className="bg-neg/10 border border-neg/30 rounded-2xl p-4 text-sm text-neg">
              <span className="font-bold">Kelly requires {(res.kelly_leverage).toFixed(1)}× leverage.</span>{" "}
              Full Kelly often implies leverage — use fractional Kelly or normalised weights for unleveraged allocation.
            </div>
          )}

          {/* Summary metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Metric label="Kelly Leverage"
              value={`${res.kelly_leverage.toFixed(2)}×`}
              positive={res.kelly_leverage <= 1} />
            <Metric label="Kelly Growth Rate"
              value={`${(res.kelly_growth_rate * 100).toFixed(2)}%`}
              positive={res.kelly_growth_rate > 0} />
            <Metric label="Current Growth Rate"
              value={`${(res.current_growth_rate * 100).toFixed(2)}%`}
              positive={res.current_growth_rate > 0} />
            <Metric label="Growth Uplift"
              value={`${((res.kelly_growth_rate - res.current_growth_rate) * 100).toFixed(2)}%`}
              positive={res.kelly_growth_rate > res.current_growth_rate} />
          </div>

          {/* Weight comparison chart */}
          <div className="bg-card border border-border rounded-2xl p-4">
            <Chart
              data={[
                {
                  x: tickers,
                  y: tickers.map(t => (res.current_weights[t] ?? 0) * 100),
                  name: "Current", type: "bar",
                  marker: { color: TXT2, opacity: 0.5 },
                } as any,
                {
                  x: tickers,
                  y: tickers.map(t => (res.normalised_weights[t] ?? 0) * 100),
                  name: `${fraction === 1 ? "Full" : fraction === 0.5 ? "Half" : fraction === 0.75 ? "¾" : "¼"} Kelly (normalised)`,
                  type: "bar",
                  marker: { color: ACCENT },
                } as any,
                {
                  x: tickers,
                  y: tickers.map(t => (res.fractional_weights[t] ?? 0) * 100),
                  name: "Raw fractional Kelly",
                  type: "bar",
                  marker: { color: "#f59e0b", opacity: 0.7 },
                } as any,
              ]}
              layout={{
                title: { text: "Kelly vs Current Allocation (%)", font: { size: 15, color: "#f0f0ff" } },
                barmode: "group",
                yaxis: { title: { text: "Allocation %" }, gridcolor: BORDER, ticksuffix: "%" },
                xaxis: { gridcolor: BORDER },
                legend: { orientation: "h", y: -0.25, font: { color: TXT2 } },
                shapes: [{ type: "line", x0: -0.5, x1: tickers.length - 0.5, y0: 0, y1: 0,
                  line: { color: "#555", width: 1 } }],
              } as any}
              height={320}
            />
          </div>

          {/* Per-stock detail table */}
          <div className="bg-card border border-border rounded-2xl p-5">
            <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-3">
              Per-Stock Kelly Detail
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-txt2 text-xs uppercase tracking-wider border-b border-border">
                    <th className="pb-2 text-left">Ticker</th>
                    <th className="pb-2 text-right">Expected Return</th>
                    <th className="pb-2 text-right">Standalone Kelly</th>
                    <th className="pb-2 text-right">Full Kelly</th>
                    <th className="pb-2 text-right">{fraction < 1 ? `${fraction * 100}% Kelly` : "Full Kelly"}</th>
                    <th className="pb-2 text-right">Normalised</th>
                    <th className="pb-2 text-right">Current</th>
                  </tr>
                </thead>
                <tbody>
                  {tickers.map((t, i) => {
                    const s = res.per_stock[t];
                    if (!s) return null;
                    const rawCls = s.fractional_kelly < 0 ? "text-neg" : s.fractional_kelly > 0.5 ? "text-yellow-400" : "text-txt";
                    return (
                      <tr key={t} className="border-b border-border/40 hover:bg-card2/50">
                        <td className="py-2.5">
                          <span className="font-bold text-txt">{t}</span>
                        </td>
                        <td className="py-2.5 text-right tabular-nums text-txt2">
                          {(s.expected_return * 100).toFixed(1)}%
                        </td>
                        <td className="py-2.5 text-right tabular-nums text-txt2">
                          {(s.standalone_kelly * 100).toFixed(1)}%
                        </td>
                        <td className={`py-2.5 text-right tabular-nums font-semibold ${s.full_kelly < 0 ? "text-neg" : "text-txt"}`}>
                          {(s.full_kelly * 100).toFixed(1)}%
                        </td>
                        <td className={`py-2.5 text-right tabular-nums font-semibold ${rawCls}`}>
                          {(s.fractional_kelly * 100).toFixed(1)}%
                        </td>
                        <td className="py-2.5 text-right tabular-nums text-accent font-semibold">
                          {(s.normalised_kelly * 100).toFixed(1)}%
                        </td>
                        <td className="py-2.5 text-right tabular-nums text-txt2">
                          {(s.current_weight * 100).toFixed(1)}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="mt-3 text-xs text-txt2 leading-relaxed">
              <span className="text-txt font-semibold">Standalone Kelly</span> = μ/σ² for that stock in isolation (ignores correlations).{" "}
              <span className="text-txt font-semibold">Full Kelly</span> = multi-asset solution using the full covariance matrix.{" "}
              <span className="text-txt font-semibold">Normalised</span> = long-only Kelly rescaled to sum to 100% (negative weights clipped to zero).
            </div>
          </div>

          {/* Growth rate interpretation */}
          <div className="bg-card border border-border rounded-2xl p-5">
            <div className="text-sm font-semibold text-txt mb-2">Log-Growth Rate Interpretation</div>
            <p className="text-xs text-txt2 leading-relaxed mb-4">
              The Kelly growth rate <span className="font-mono text-accent">g = r_f + f'μ − ½f'Σf</span> is the
              expected geometric (compounding) return per year. It accounts for the volatility drag (the ½f'Σf term)
              that reduces arithmetic returns in compounding. Maximising this is equivalent to maximising the
              expected log of terminal wealth.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-card2/50 rounded-xl p-3">
                <div className="text-xs text-txt2 mb-1">Kelly growth rate (fractional)</div>
                <div className={`text-xl font-bold tabular-nums ${res.kelly_growth_rate > 0 ? "text-pos" : "text-neg"}`}>
                  {(res.kelly_growth_rate * 100).toFixed(2)}% / yr
                </div>
              </div>
              <div className="bg-card2/50 rounded-xl p-3">
                <div className="text-xs text-txt2 mb-1">Current portfolio growth rate</div>
                <div className={`text-xl font-bold tabular-nums ${res.current_growth_rate > 0 ? "text-pos" : "text-neg"}`}>
                  {(res.current_growth_rate * 100).toFixed(2)}% / yr
                </div>
              </div>
            </div>
          </div>

          {/* Disclaimer */}
          <div className="bg-card border border-border rounded-2xl p-4">
            <p className="text-xs text-txt2 leading-relaxed">
              Kelly sizing assumes log-normal returns and known parameters. In practice, returns are fat-tailed
              and parameters are estimated with error — making full Kelly dangerous. Half Kelly is a common
              practical heuristic. These are theoretical allocations and not financial advice.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
