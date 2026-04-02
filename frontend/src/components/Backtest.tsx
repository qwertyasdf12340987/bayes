import { useState } from "react";
import { api, BacktestResult } from "../api";
import { PortfolioParams } from "../App";
import { SectionHeader } from "./Dashboard";
import Chart, { ACCENT, TXT2, BORDER, NEG } from "./Chart";
import Metric from "./Metric";

export default function Backtest({ params }: { params: PortfolioParams }) {
  const [freq, setFreq]       = useState("quarterly");
  const [result, setResult]   = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.backtest({
        tickers: params.tickers,
        weights: params.weights,
        start_date: params.startDate,
        end_date: params.endDate,
        rebalance_freq: freq,
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
      <SectionHeader>Backtest</SectionHeader>

      <div className="bg-card border border-border rounded-2xl p-6">
        <p className="text-txt2 text-sm mb-5">
          Test how periodically rebalancing to your target weights would have performed
          compared to buy-and-hold over the historical period.
        </p>
        <div className="flex flex-wrap items-end gap-4 mb-5">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-txt2">Rebalance Frequency</span>
            <select value={freq} onChange={e => setFreq(e.target.value)}
              className="bg-card2 border border-border rounded-lg px-3 py-2 text-sm text-txt">
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="annually">Annually</option>
            </select>
          </div>
          <button onClick={run} disabled={loading}
            className="px-6 py-2.5 rounded-xl font-bold text-sm text-white transition-all
              bg-gradient-to-r from-accent to-accent2
              disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 active:scale-95">
            {loading ? "Running..." : "Run Backtest"}
          </button>
        </div>
        {error && <p className="text-neg text-sm">{error}</p>}
      </div>

      {loading && (
        <div className="flex items-center gap-3 text-txt2 text-sm p-4">
          <div className="w-5 h-5 rounded-full border-2 border-accent border-t-transparent animate-spin" />
          Running backtest...
        </div>
      )}

      {result && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <Metric label="Total Return"  value={`${(result.metrics.total_return * 100).toFixed(1)}%`}
              positive={result.metrics.total_return > 0} />
            <Metric label="Ann. Return"   value={`${(result.metrics.ann_return * 100).toFixed(1)}%`}
              positive={result.metrics.ann_return > 0} />
            <Metric label="Ann. Vol"      value={`${(result.metrics.ann_vol * 100).toFixed(1)}%`} />
            <Metric label="Sharpe"        value={result.metrics.sharpe.toFixed(2)}
              positive={result.metrics.sharpe > 0} />
            <Metric label="Max Drawdown"  value={`${(result.metrics.max_drawdown * 100).toFixed(1)}%`}
              positive={false} />
          </div>

          <div className="bg-card border border-border rounded-2xl p-4">
            <Chart
              data={[
                {
                  x: result.dates.slice(1), y: result.buy_and_hold.slice(1),
                  mode: "lines", name: "Buy & Hold",
                  line: { color: TXT2, width: 1.5, dash: "dot" },
                } as any,
                {
                  x: result.dates.slice(1), y: result.rebalanced.slice(1),
                  mode: "lines", name: `Rebalanced (${freq})`,
                  line: { color: ACCENT, width: 2.5 },
                } as any,
              ]}
              layout={{
                title: { text: "Rebalanced vs Buy & Hold", font: { size: 15, color: "#f0f0ff" } },
                yaxis: { title: { text: "Growth of $1" }, gridcolor: BORDER },
                xaxis: { gridcolor: BORDER },
                legend: { orientation: "h", y: -0.2, font: { color: TXT2 } },
                shapes: [{
                  type: "line", x0: 0, x1: 1, xref: "paper", y0: 1, y1: 1,
                  line: { color: "#555", dash: "dash", width: 1 },
                }],
              } as any}
              height={340}
            />
          </div>

          <div className="bg-card border border-border rounded-2xl p-4">
            <p className="text-xs text-txt2">
              The rebalanced strategy returns to target weights at each {freq} interval.
              Buy & hold starts with the same weights but lets them drift with market movements.
              Past performance does not guarantee future results.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
