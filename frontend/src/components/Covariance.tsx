import { AnalysisResult } from "../api";
import Chart, { ACCENT, NEG, BORDER, TXT2 } from "./Chart";
import { SectionHeader } from "./Dashboard";
import Metric from "./Metric";

export default function Covariance({ result }: { result: AnalysisResult }) {
  const tickers = Object.keys(result.corr);

  const z = tickers.map(row => tickers.map(col => result.corr[row][col]));
  const text = z.map(row => row.map(v => v.toFixed(2)));

  const mrcEntries = Object.entries(result.mrc).sort((a, b) => b[1] - a[1]);
  const vols = result.vols;

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader>Covariance &amp; Correlation</SectionHeader>

      {/* Vol + MRC cards */}
      <div className={`grid gap-4`} style={{ gridTemplateColumns: `repeat(${Math.min(tickers.length, 4)}, minmax(0,1fr))` }}>
        {Object.entries(vols).map(([t, v]) => (
          <Metric key={t} label={t + " Vol (ann.)"} value={`${(v * 100).toFixed(1)}%`} />
        ))}
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Correlation heatmap */}
        <div className="col-span-2 bg-card border border-border rounded-2xl p-4">
          <Chart
            data={[{
              type: "heatmap",
              z, x: tickers, y: tickers,
              text,
              texttemplate: "%{text}",
              textfont: { size: 12, color: "white" },
              colorscale: [[0, NEG], [0.5, "#1c1c28"], [1, ACCENT]],
              zmin: -1, zmax: 1, zmid: 0,
            } as any]}
            layout={{
              title: { text: "Correlation Matrix", font: { size: 15, color: "#f0f0ff" } },
              xaxis: { gridcolor: BORDER },
              yaxis: { autorange: "reversed", gridcolor: BORDER },
            }}
            height={Math.max(320, tickers.length * 60 + 100)}
          />
        </div>

        {/* MRC table */}
        <div className="bg-card border border-border rounded-2xl p-5 flex flex-col gap-3">
          <div className="text-xs text-txt2 uppercase tracking-wider font-semibold">
            Marginal Risk Contribution
          </div>
          <div className="flex flex-col gap-2">
            {mrcEntries.map(([ticker, mrc]) => {
              const pct = mrc * 100;
              const total = mrcEntries.reduce((s, [, v]) => s + v, 0);
              const share = total > 0 ? mrc / total : 0;
              return (
                <div key={ticker}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-semibold text-txt">{ticker}</span>
                    <span className="tabular-nums text-txt2">{pct.toFixed(2)}%</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-border overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-accent to-accent2"
                      style={{ width: `${Math.max(share * 100, 2)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-txt2 mt-auto">
            MRC = % contribution to portfolio variance
          </p>
        </div>
      </div>

      {/* Covariance heatmap */}
      <div className="bg-card border border-border rounded-2xl p-4">
        <Chart
          data={[{
            type: "heatmap",
            z: tickers.map(row => tickers.map(col => result.cov[row][col] * 10000)),
            x: tickers, y: tickers,
            text: tickers.map(row => tickers.map(col => (result.cov[row][col] * 10000).toFixed(2))),
            texttemplate: "%{text}",
            textfont: { size: 12, color: "white" },
            colorscale: [[0, "#1c1c28"], [1, ACCENT]],
            colorbar: { title: { text: "× 10⁻⁴", font: { color: TXT2, size: 11 } } },
          } as any]}
          layout={{
            title: { text: "Covariance Matrix (×10⁻⁴)", font: { size: 15, color: "#f0f0ff" } },
            xaxis: { gridcolor: BORDER },
            yaxis: { autorange: "reversed", gridcolor: BORDER },
          }}
          height={Math.max(320, tickers.length * 60 + 100)}
        />
      </div>
    </div>
  );
}
