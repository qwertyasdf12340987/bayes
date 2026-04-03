import { useState } from "react";
import { api, OptimizeResult } from "../api";
import { AnalysisResult } from "../api";
import { PortfolioParams } from "../App";
import { SectionHeader } from "./Dashboard";
import Chart, { ACCENT, NEG, BORDER, TXT2 } from "./Chart";
import Metric from "./Metric";

export default function Optimizer({ result, params }: { result: AnalysisResult; params: PortfolioParams }) {
  const tickers = params.tickers;
  const [er, setEr] = useState<Record<string, string>>(
    Object.fromEntries(tickers.map(t => [t, ""]))
  );
  const [longOnly, setLongOnly]       = useState(true);
  const [maxPos, setMaxPos]           = useState("40");
  const [rf, setRf]                   = useState("5");
  const [useShrinkage, setUseShrinkage] = useState(true);
  const [maxRiskContrib, setMaxRiskContrib] = useState("");
  const [opt, setOpt]           = useState<OptimizeResult | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  async function run() {
    const missing = tickers.filter(t => !er[t] || isNaN(Number(er[t])));
    if (missing.length) { setError(`Enter predicted return for: ${missing.join(", ")}`); return; }

    setLoading(true);
    setError(null);
    try {
      const res = await api.optimize({
        tickers: params.tickers,
        weights: params.weights,
        start_date: params.startDate,
        end_date: params.endDate,
        expected_returns: Object.fromEntries(tickers.map(t => [t, Number(er[t]) / 100])),
        risk_free_rate: Number(rf) / 100,
        long_only: longOnly,
        max_position: Number(maxPos) / 100,
        use_shrinkage: useShrinkage,
        max_risk_contribution: maxRiskContrib ? Number(maxRiskContrib) / 100 : null,
      });
      setOpt(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader>Portfolio Optimizer</SectionHeader>

      {/* Input card */}
      <div className="bg-card border border-border rounded-2xl p-6">
        <p className="text-txt2 text-sm mb-5">
          Enter your predicted annualised return for each stock. The optimizer finds the allocation
          that maximises the Sharpe ratio using the historical covariance structure.
        </p>

        {/* Per-stock expected returns */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-5">
          {tickers.map(t => (
            <div key={t} className="flex items-center gap-3 bg-card2/40 border border-border/50 rounded-xl px-4 py-3">
              <span className="text-sm font-bold text-txt w-16">{t}</span>
              <input
                type="number" step="any" placeholder="e.g. 12"
                value={er[t] ?? ""}
                onChange={e => setEr(prev => ({ ...prev, [t]: e.target.value }))}
                className="flex-1 bg-transparent border-b border-border/60 text-sm text-txt
                  placeholder:text-txt2/40 focus:border-accent outline-none py-1 tabular-nums text-right"
              />
              <span className="text-xs text-txt2">%</span>
            </div>
          ))}
        </div>

        {/* Constraints row */}
        <div className="flex flex-wrap items-center gap-4 mb-3">
          <label className="flex items-center gap-2 text-sm text-txt2 cursor-pointer select-none">
            <input type="checkbox" checked={longOnly} onChange={e => setLongOnly(e.target.checked)}
              className="accent-[#d946ef] w-4 h-4 rounded" />
            Long only
          </label>
          <label className="flex items-center gap-2 text-sm text-txt2 cursor-pointer select-none">
            <input type="checkbox" checked={useShrinkage} onChange={e => setUseShrinkage(e.target.checked)}
              className="accent-[#d946ef] w-4 h-4 rounded" />
            Ledoit-Wolf shrinkage
          </label>
          <div className="flex items-center gap-2">
            <span className="text-xs text-txt2">Max position</span>
            <input type="number" min="5" max="100" value={maxPos}
              onChange={e => setMaxPos(e.target.value)}
              className="w-16 bg-card2 border border-border rounded-lg px-2 py-1.5 text-sm text-txt text-right" />
            <span className="text-xs text-txt2">%</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-txt2">Risk-free rate</span>
            <input type="number" step="0.1" value={rf}
              onChange={e => setRf(e.target.value)}
              className="w-16 bg-card2 border border-border rounded-lg px-2 py-1.5 text-sm text-txt text-right" />
            <span className="text-xs text-txt2">%</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-txt2">Max risk contribution</span>
            <input type="number" min="5" max="100" placeholder="—" value={maxRiskContrib}
              onChange={e => setMaxRiskContrib(e.target.value)}
              className="w-16 bg-card2 border border-border rounded-lg px-2 py-1.5 text-sm text-txt text-right" />
            <span className="text-xs text-txt2">%</span>
          </div>
        </div>
        <p className="text-xs text-txt2 mb-5">
          <span className="text-txt font-semibold">Ledoit-Wolf</span> reduces covariance estimation error (Paleologo Ch. 8).{" "}
          <span className="text-txt font-semibold">Max risk contribution</span> limits each stock's share of portfolio variance — a risk-budget constraint (Ch. 7).
        </p>

        <button onClick={run} disabled={loading}
          className="px-6 py-2.5 rounded-xl font-bold text-sm text-white transition-all
            bg-gradient-to-r from-accent to-accent2
            disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 active:scale-95">
          {loading ? "Optimizing..." : "Optimize Portfolio"}
        </button>
        {error && <p className="text-neg text-sm mt-3">{error}</p>}
      </div>

      {loading && (
        <div className="flex items-center gap-3 text-txt2 text-sm p-4">
          <div className="w-5 h-5 rounded-full border-2 border-accent border-t-transparent animate-spin" />
          Running mean-variance optimisation...
        </div>
      )}

      {/* Results */}
      {opt && (
        <>
          {/* Metric cards — current vs optimal */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <Metric label="Current Sharpe"  value={opt.current_expected_sharpe.toFixed(2)} />
            <Metric label="Optimal Sharpe"  value={opt.expected_sharpe.toFixed(2)} positive={opt.expected_sharpe > opt.current_expected_sharpe} />
            <Metric label="Current Return"  value={`${(opt.current_expected_return * 100).toFixed(1)}%`} />
            <Metric label="Optimal Return"  value={`${(opt.expected_return * 100).toFixed(1)}%`} positive={opt.expected_return > opt.current_expected_return} />
            <Metric label="Current Vol"     value={`${(opt.current_expected_vol * 100).toFixed(1)}%`} />
            <Metric label="Optimal Vol"     value={`${(opt.expected_vol * 100).toFixed(1)}%`} positive={opt.expected_vol < opt.current_expected_vol} />
          </div>

          {/* Weight comparison chart */}
          <div className="bg-card border border-border rounded-2xl p-4">
            <Chart
              data={[
                {
                  x: tickers, y: tickers.map(t => (opt.current_weights[t] ?? 0) * 100),
                  name: "Current", type: "bar",
                  marker: { color: TXT2, opacity: 0.5 },
                } as any,
                {
                  x: tickers, y: tickers.map(t => (opt.optimal_weights[t] ?? 0) * 100),
                  name: "Optimal", type: "bar",
                  marker: { color: ACCENT },
                } as any,
              ]}
              layout={{
                title: { text: "Weight Allocation (%)", font: { size: 15, color: "#f0f0ff" } },
                barmode: "group",
                yaxis: { title: { text: "Weight %" }, gridcolor: BORDER, ticksuffix: "%" },
                xaxis: { gridcolor: BORDER },
                legend: { orientation: "h", y: -0.2, font: { color: TXT2 } },
              } as any}
              height={300}
            />
          </div>

          {/* Adjustments table */}
          <div className="bg-card border border-border rounded-2xl p-5">
            <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-3">Suggested Adjustments</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-txt2 text-xs uppercase tracking-wider border-b border-border">
                    <th className="pb-2 text-left">Ticker</th>
                    <th className="pb-2 text-right">Current %</th>
                    <th className="pb-2 text-right">Optimal %</th>
                    <th className="pb-2 text-right">Current $</th>
                    <th className="pb-2 text-right">Optimal $</th>
                    <th className="pb-2 text-right">Delta $</th>
                    <th className="pb-2 text-center">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {tickers.map(t => {
                    const a = opt.adjustments[t];
                    if (!a) return null;
                    const cls = a.action === "BUY" ? "text-pos" : a.action === "SELL" ? "text-neg" : "text-txt2";
                    return (
                      <tr key={t} className="border-b border-border/40 hover:bg-card2/50">
                        <td className="py-2.5 font-bold text-txt">{t}</td>
                        <td className="py-2.5 text-right tabular-nums text-txt2">{(a.current_pct * 100).toFixed(1)}%</td>
                        <td className="py-2.5 text-right tabular-nums text-txt">{(a.optimal_pct * 100).toFixed(1)}%</td>
                        <td className="py-2.5 text-right tabular-nums text-txt2">
                          ${a.current_dollars.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                        </td>
                        <td className="py-2.5 text-right tabular-nums text-txt">
                          ${a.optimal_dollars.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                        </td>
                        <td className={`py-2.5 text-right tabular-nums font-semibold ${cls}`}>
                          {a.delta_dollars >= 0 ? "+" : ""}${a.delta_dollars.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                        </td>
                        <td className="py-2.5 text-center">
                          <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                            a.action === "BUY"  ? "bg-pos/15 text-pos" :
                            a.action === "SELL" ? "bg-neg/15 text-neg" :
                            "bg-card2 text-txt2"
                          }`}>{a.action}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* FLAM — Fundamental Law of Active Management */}
          {opt.flam && (
            <div className="bg-card border border-border rounded-2xl p-5">
              <div className="flex items-center justify-between mb-1">
                <div className="text-sm font-semibold text-txt">Signal Quality — Fundamental Law</div>
                <div className="text-xs text-txt2">Grinold-Kahn · Paleologo Ch. 6</div>
              </div>
              <p className="text-xs text-txt2 mb-4 leading-relaxed">
                IR ≈ IC × √BR where IC is the correlation between your predicted and realised returns,
                and BR is breadth (independent bets per year). This is a sanity check on your forecasts.
              </p>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="text-center">
                  <div className={`text-2xl font-bold tabular-nums ${Math.abs(opt.flam.ic) > 0.3 ? "text-pos" : Math.abs(opt.flam.ic) < 0.05 ? "text-neg" : "text-txt"}`}>
                    {opt.flam.ic.toFixed(2)}
                  </div>
                  <div className="text-xs text-txt2 mt-1">Information Coefficient (IC)</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold tabular-nums text-txt">{opt.flam.breadth}</div>
                  <div className="text-xs text-txt2 mt-1">Breadth (bets/yr)</div>
                </div>
                <div className="text-center">
                  <div className={`text-2xl font-bold tabular-nums ${opt.flam.ir_implied > 0.5 ? "text-pos" : opt.flam.ir_implied < 0 ? "text-neg" : "text-txt"}`}>
                    {opt.flam.ir_implied.toFixed(2)}
                  </div>
                  <div className="text-xs text-txt2 mt-1">Implied IR</div>
                </div>
              </div>
              {Math.abs(opt.flam.ir_implied) > 1.5 && (
                <div className="text-xs bg-neg/10 border border-neg/20 rounded-lg px-3 py-2 text-neg">
                  Implied IR &gt; 1.5 — your predicted returns may be overfit to historical data.
                  Consider more conservative estimates.
                </div>
              )}
              {Math.abs(opt.flam.ic) < 0.03 && (
                <div className="text-xs bg-card2 border border-border rounded-lg px-3 py-2 text-txt2">
                  IC ≈ 0 — your predicted returns have little correlation with realised returns over this period.
                  The optimizer is effectively running on noise.
                </div>
              )}
              <div className="mt-4">
                <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-2">Predicted vs Realised</div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {tickers.map(t => (
                    <div key={t} className="flex justify-between items-center bg-card2/50 rounded-lg px-3 py-2 text-xs">
                      <span className="font-bold text-txt">{t}</span>
                      <span className="text-txt2 tabular-nums">
                        pred: <span className="text-txt">{Number(er[t]).toFixed(1)}%</span>{" "}
                        actual: <span className={opt.flam!.realized_returns[t] > 0 ? "text-pos" : "text-neg"}>
                          {((opt.flam!.realized_returns[t] ?? 0) * 100).toFixed(1)}%
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Disclaimer */}
          <div className="bg-card border border-border rounded-2xl p-4">
            <p className="text-xs text-txt2">
              This is a theoretical mean-variance optimisation based on your predicted returns and historical
              covariance. Past correlations may not persist. This is not financial advice.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
