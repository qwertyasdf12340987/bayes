import { AnalysisResult } from "../api";
import Metric from "./Metric";
import Chart, { PALETTE, TXT2, BORDER } from "./Chart";

function cumulative(pts: { date: string; value: number }[]) {
  let cum = 1;
  return pts.map(p => { cum *= 1 + p.value; return { date: p.date, value: cum }; });
}

export default function Dashboard({ result }: { result: AnalysisResult }) {
  const portCum  = cumulative(result.port_returns);
  const benchCum = cumulative(result.benchmark);

  const chartData: Plotly.Data[] = [
    {
      x: benchCum.map(p => p.date), y: benchCum.map(p => p.value),
      mode: "lines", name: "SPY",
      line: { color: TXT2, width: 1.5, dash: "dot" },
    } as any,
    ...Object.entries(result.stock_returns).map(([ticker, pts], i) => ({
      x: cumulative(pts).map(p => p.date),
      y: cumulative(pts).map(p => p.value),
      mode: "lines", name: ticker,
      line: { color: PALETTE[i % PALETTE.length], width: 1.2 },
      opacity: 0.6,
    } as any)),
    {
      x: portCum.map(p => p.date), y: portCum.map(p => p.value),
      mode: "lines", name: "Portfolio",
      line: { color: "#ffffff", width: 2.5 },
    } as any,
  ];

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader>Portfolio Overview</SectionHeader>
      <div className="grid grid-cols-4 gap-4">
        <Metric label="Holdings"      value={String(Object.keys(result.stock_returns).length)} />
        <Metric label="Portfolio Vol" value={`${(result.port_vol * 100).toFixed(1)}%`} />
        <Metric label="FF5 R²"        value={result.ff.portfolio.r_squared.toFixed(2)} />
        <Metric label="Alpha (ann.)"  value={`${(result.ff.portfolio.alpha_annualized * 100).toFixed(1)}%`}
          positive={result.ff.portfolio.alpha_annualized > 0} />
      </div>
      <div className="bg-card border border-border rounded-2xl p-4">
        <Chart
          data={chartData}
          layout={{
            title: { text: "Cumulative Returns", font: { size: 15, color: "#f0f0ff" } },
            yaxis: { title: { text: "Growth of $1" }, gridcolor: BORDER },
            xaxis: { gridcolor: BORDER },
            legend: { orientation: "h", y: -0.2, font: { color: TXT2 } },
            shapes: [{ type: "line", x0: 0, x1: 1, xref: "paper", y0: 1, y1: 1,
              line: { color: "#555", dash: "dash", width: 1 } }],
          } as any}
          height={360}
        />
      </div>
    </div>
  );
}

export function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-1 h-5 rounded-full bg-gradient-to-b from-accent to-accent2" />
      <h2 className="text-lg font-bold text-txt">{children}</h2>
    </div>
  );
}
