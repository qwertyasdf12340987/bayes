import { AnalysisResult } from "../api";
import Chart, { ACCENT, NEG, TXT2, BORDER, PALETTE } from "./Chart";
import { SectionHeader } from "./Dashboard";
import Metric from "./Metric";

function RiskBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-txt2">{label}</span>
        <span className="font-semibold text-txt">{pct.toFixed(1)}%</span>
      </div>
      <div className="h-2.5 bg-card2 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function cumulative(pts: { date: string; value: number }[]) {
  let cum = 1;
  return pts.map(p => { cum *= 1 + p.value; return { date: p.date, value: cum }; });
}

function drawdownSeries(pts: { date: string; value: number }[]) {
  const cum = cumulative(pts);
  let peak = -Infinity;
  return cum.map(p => {
    if (p.value > peak) peak = p.value;
    return { date: p.date, value: (p.value / peak - 1) * 100 };
  });
}

export default function Analytics({ result }: { result: AnalysisResult }) {
  const dd = drawdownSeries(result.port_returns);
  const benchDD = drawdownSeries(result.benchmark);
  const portCum  = cumulative(result.port_returns);
  const benchCum = cumulative(result.benchmark);

  // Rolling betas chart data
  const factors = result.rolling_betas.length > 0
    ? Object.keys(result.rolling_betas[0]).filter(k => k !== "date")
    : [];
  const dates = result.rolling_betas.map(r => r.date as string);

  const rd = result.risk_decomp;
  const tickers = Object.keys(result.vols);

  const metrics = [
    { label: "Ann. Return",   value: `${(result.ann_return  * 100).toFixed(1)}%`, positive: result.ann_return > 0 },
    { label: "Sharpe",        value: result.sharpe.toFixed(2),                     positive: result.sharpe > 0 },
    { label: "Sortino",       value: result.sortino.toFixed(2),                    positive: result.sortino > 0 },
    { label: "Calmar",        value: result.calmar.toFixed(2),                     positive: result.calmar > 0 },
    { label: "Max Drawdown",  value: `${(result.max_drawdown * 100).toFixed(1)}%`, positive: false },
    { label: "VaR 95%",       value: `${(result.var95 * 100).toFixed(2)}%`,        positive: false },
    { label: "CVaR 95%",      value: `${(result.cvar95 * 100).toFixed(2)}%`,       positive: false },
    { label: "Port. Vol",     value: `${(result.port_vol * 100).toFixed(1)}%`,     positive: undefined },
  ];

  const activeMetrics = [
    { label: "Active Return vs SPY", value: `${((result.active_return ?? 0) * 100).toFixed(2)}%`,  positive: (result.active_return ?? 0) > 0 },
    { label: "Tracking Error",       value: `${((result.tracking_error ?? 0) * 100).toFixed(2)}%`, positive: undefined },
    { label: "Information Ratio",    value: (result.information_ratio ?? 0).toFixed(2),             positive: (result.information_ratio ?? 0) > 0 },
  ];

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader>Performance Analytics</SectionHeader>

      {/* Performance metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {metrics.map(m => (
          <Metric key={m.label} label={m.label} value={m.value} positive={m.positive} />
        ))}
      </div>

      {/* Active risk metrics (vs SPY) */}
      <div className="grid grid-cols-3 gap-4">
        {activeMetrics.map(m => (
          <Metric key={m.label} label={m.label} value={m.value} positive={m.positive} />
        ))}
      </div>

      {/* Risk decomposition — Paleologo Ch. 4 */}
      {rd && (
        <div className="bg-card border border-border rounded-2xl p-5">
          <div className="flex items-center justify-between mb-1">
            <div className="text-sm font-semibold text-txt">Risk Decomposition</div>
            <div className="text-xs text-txt2">Systematic vs Specific — Paleologo Ch. 4</div>
          </div>
          <p className="text-xs text-txt2 mb-5 leading-relaxed">
            Total portfolio variance split into <span className="text-accent">factor (systematic)</span> risk
            you could hedge cheaply, and <span className="text-[#22c55e]">specific (idiosyncratic)</span> risk
            you are being compensated to hold.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="flex flex-col gap-3">
              <RiskBar label={`Systematic — ${rd.systematic_pct.toFixed(1)}% of variance (vol: ${(rd.systematic_vol*100).toFixed(1)}%)`}
                pct={rd.systematic_pct} color="#7c6af7" />
              <RiskBar label={`Specific — ${rd.specific_pct.toFixed(1)}% of variance (vol: ${(rd.specific_vol*100).toFixed(1)}%)`}
                pct={rd.specific_pct} color="#22c55e" />
              <div className="text-xs text-txt2 mt-1">
                Total vol: <span className="text-txt font-semibold">{(rd.total_vol * 100).toFixed(1)}%</span>
              </div>
            </div>

            {/* Per-stock specific risk */}
            <div className="flex flex-col gap-2">
              <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-1">
                Per-stock specific risk (% of total variance)
              </div>
              {tickers.map((t, i) => (
                <div key={t} className="flex items-center gap-3">
                  <span className="text-xs font-bold text-txt w-12">{t}</span>
                  <div className="flex-1 h-2 bg-card2 rounded-full overflow-hidden">
                    <div className="h-full rounded-full"
                      style={{
                        width: `${Math.min(rd.per_stock_specific[t] ?? 0, 100)}%`,
                        backgroundColor: PALETTE[i % PALETTE.length],
                      }} />
                  </div>
                  <span className="text-xs text-txt2 tabular-nums w-10 text-right">
                    {(rd.per_stock_specific[t] ?? 0).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Cumulative return vs SPY */}
      <div className="bg-card border border-border rounded-2xl p-4">
        <Chart
          data={[
            {
              x: benchCum.map(p => p.date), y: benchCum.map(p => p.value),
              mode: "lines", name: "SPY",
              line: { color: TXT2, width: 1.5, dash: "dot" },
            } as any,
            {
              x: portCum.map(p => p.date), y: portCum.map(p => p.value),
              mode: "lines", name: "Portfolio",
              line: { color: ACCENT, width: 2.5 },
            } as any,
          ]}
          layout={{
            title: { text: "Cumulative Return vs SPY", font: { size: 15, color: "#f0f0ff" } },
            yaxis: { title: { text: "Growth of $1" }, gridcolor: BORDER },
            xaxis: { gridcolor: BORDER },
            legend: { orientation: "h", y: -0.2, font: { color: TXT2 } },
            shapes: [{ type: "line", x0: 0, x1: 1, xref: "paper", y0: 1, y1: 1,
              line: { color: "#555", dash: "dash", width: 1 } }],
          } as any}
          height={300}
        />
      </div>

      {/* Drawdown */}
      <div className="bg-card border border-border rounded-2xl p-4">
        <Chart
          data={[
            {
              x: benchDD.map(p => p.date), y: benchDD.map(p => p.value),
              mode: "lines", name: "SPY", fill: "tozeroy",
              line: { color: TXT2, width: 1 },
              fillcolor: "rgba(136,136,170,0.07)",
            } as any,
            {
              x: dd.map(p => p.date), y: dd.map(p => p.value),
              mode: "lines", name: "Portfolio", fill: "tozeroy",
              line: { color: NEG, width: 2 },
              fillcolor: "rgba(251,113,133,0.13)",
            } as any,
          ]}
          layout={{
            title: { text: "Drawdown (%)", font: { size: 15, color: "#f0f0ff" } },
            yaxis: { title: { text: "Drawdown %" }, gridcolor: BORDER, ticksuffix: "%" },
            xaxis: { gridcolor: BORDER },
            legend: { orientation: "h", y: -0.2, font: { color: TXT2 } },
          } as any}
          height={280}
        />
      </div>

      {/* Rolling betas */}
      {factors.length > 0 && (
        <div className="bg-card border border-border rounded-2xl p-4">
          <Chart
            data={factors.map((f, i) => ({
              x: dates,
              y: result.rolling_betas.map(r => r[f] as number),
              mode: "lines", name: f,
              line: { color: PALETTE[i % PALETTE.length], width: 1.8 },
            } as any))}
            layout={{
              title: { text: "Rolling 36-Month Factor Betas", font: { size: 15, color: "#f0f0ff" } },
              yaxis: { title: { text: "Beta" }, gridcolor: BORDER, zerolinecolor: "#555" },
              xaxis: { gridcolor: BORDER },
              legend: { orientation: "h", y: -0.2, font: { color: TXT2 } },
            } as any}
            height={320}
          />
        </div>
      )}
    </div>
  );
}
