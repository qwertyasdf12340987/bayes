import { useState } from "react";
import { api, SimulateResult } from "../api";
import { PortfolioParams } from "../App";
import { SectionHeader } from "./Dashboard";
import Chart, { ACCENT, NEG, BORDER, TXT2 } from "./Chart";
import Metric from "./Metric";

export default function Simulate({ params }: { params: PortfolioParams }) {
  const [horizon, setHorizon] = useState("12");
  const [sims, setSims]       = useState("5000");
  const [result, setResult]   = useState<SimulateResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.simulate({
        tickers: params.tickers,
        weights: params.weights,
        start_date: params.startDate,
        end_date: params.endDate,
        n_simulations: Number(sims),
        horizon_months: Number(horizon),
      });
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader>Monte Carlo Simulation</SectionHeader>

      <div className="bg-card border border-border rounded-2xl p-6">
        <p className="text-txt2 text-sm mb-5">
          Simulates thousands of possible portfolio paths using historical volatility and correlations.
          See the range of outcomes and probability of loss over your chosen horizon.
        </p>
        <div className="flex flex-wrap items-end gap-4 mb-5">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-txt2">Horizon (months)</span>
            <input type="number" min="1" max="120" value={horizon}
              onChange={e => setHorizon(e.target.value)}
              className="w-24 bg-card2 border border-border rounded-lg px-3 py-2 text-sm text-txt text-right" />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs text-txt2">Simulations</span>
            <input type="number" min="100" max="50000" step="100" value={sims}
              onChange={e => setSims(e.target.value)}
              className="w-28 bg-card2 border border-border rounded-lg px-3 py-2 text-sm text-txt text-right" />
          </div>
          <button onClick={run} disabled={loading}
            className="px-6 py-2.5 rounded-xl font-bold text-sm text-white transition-all
              bg-gradient-to-r from-accent to-accent2
              disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 active:scale-95">
            {loading ? "Simulating..." : "Run Simulation"}
          </button>
        </div>
        {error && <p className="text-neg text-sm">{error}</p>}
      </div>

      {loading && (
        <div className="flex items-center gap-3 text-txt2 text-sm p-4">
          <div className="w-5 h-5 rounded-full border-2 border-accent border-t-transparent animate-spin" />
          Running {sims} simulations...
        </div>
      )}

      {result && (
        <>
          {/* Summary metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <Metric label="P(Loss)" value={`${(result.prob_loss * 100).toFixed(1)}%`}
              positive={result.prob_loss < 0.3} />
            <Metric label="Median Return" value={`${(result.median_return * 100).toFixed(1)}%`}
              positive={result.median_return > 0} />
            <Metric label="Worst 5%" value={`${(result.percentile_5_return * 100).toFixed(1)}%`}
              positive={result.percentile_5_return > 0} />
            <Metric label="Best 5%" value={`${(result.percentile_95_return * 100).toFixed(1)}%`}
              positive={result.percentile_95_return > 0} />
            <Metric label="Ann. Vol" value={`${(result.expected_annual_vol * 100).toFixed(1)}%`} />
          </div>

          {/* Fan chart */}
          <div className="bg-card border border-border rounded-2xl p-4">
            <Chart
              data={[
                {
                  x: result.months, y: result.percentile_paths[5],
                  mode: "lines", name: "5th pct", line: { color: NEG, width: 1 },
                  showlegend: false,
                } as any,
                {
                  x: result.months, y: result.percentile_paths[95],
                  mode: "lines", name: "95th pct", fill: "tonexty",
                  line: { color: NEG, width: 0 },
                  fillcolor: "rgba(251,113,133,0.08)",
                  showlegend: false,
                } as any,
                {
                  x: result.months, y: result.percentile_paths[25],
                  mode: "lines", name: "25th pct", line: { color: ACCENT, width: 1, dash: "dot" },
                  showlegend: false,
                } as any,
                {
                  x: result.months, y: result.percentile_paths[75],
                  mode: "lines", name: "75th pct", fill: "tonexty",
                  line: { color: ACCENT, width: 0 },
                  fillcolor: "rgba(217,70,239,0.12)",
                  showlegend: false,
                } as any,
                {
                  x: result.months, y: result.percentile_paths[50],
                  mode: "lines", name: "Median",
                  line: { color: "#ffffff", width: 2.5 },
                } as any,
                {
                  x: result.months,
                  y: result.months.map(() => 1),
                  mode: "lines", name: "Break-even",
                  line: { color: TXT2, width: 1, dash: "dash" },
                } as any,
              ]}
              layout={{
                title: { text: `Simulated Portfolio Paths (${result.n_simulations.toLocaleString()} runs)`, font: { size: 15, color: "#f0f0ff" } },
                xaxis: { title: { text: "Months" }, gridcolor: BORDER },
                yaxis: { title: { text: "Growth of $1" }, gridcolor: BORDER },
                legend: { orientation: "h", y: -0.2, font: { color: TXT2 } },
              } as any}
              height={340}
            />
          </div>

          {/* Terminal value histogram */}
          <div className="bg-card border border-border rounded-2xl p-4">
            <Chart
              data={[{
                x: result.terminal_values,
                type: "histogram",
                nbinsx: 80,
                marker: { color: ACCENT, opacity: 0.7 },
                name: "Terminal Value",
              } as any]}
              layout={{
                title: { text: "Distribution of Terminal Portfolio Value", font: { size: 15, color: "#f0f0ff" } },
                xaxis: { title: { text: "Growth of $1" }, gridcolor: BORDER },
                yaxis: { title: { text: "Frequency" }, gridcolor: BORDER },
                shapes: [{
                  type: "line", x0: 1, x1: 1, y0: 0, y1: 1, yref: "paper",
                  line: { color: NEG, width: 2, dash: "dash" },
                }],
              } as any}
              height={280}
            />
          </div>
        </>
      )}
    </div>
  );
}
