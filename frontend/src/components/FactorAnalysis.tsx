import { AnalysisResult, FactorResult } from "../api";
import Chart, { ACCENT, NEG, BORDER, TXT2, CARD2 } from "./Chart";
import { SectionHeader } from "./Dashboard";

function stars(p: number) { return p < 0.01 ? "★★★" : p < 0.05 ? "★★" : p < 0.1 ? "★" : ""; }

function FactorBar({ result, title }: { result: FactorResult; title: string }) {
  const factors = Object.keys(result.betas);
  const betas   = factors.map(f => result.betas[f]);
  const tstats  = factors.map(f => result.tstats[f]);
  const errors  = betas.map((b, i) => tstats[i] ? Math.abs(b / tstats[i]) * 1.96 : 0);
  const colors  = betas.map(b => b >= 0 ? ACCENT : NEG);

  const alpha = result.alpha_annualized * 100;
  const annotation = `α = ${alpha.toFixed(1)}%  t = ${result.alpha_tstat.toFixed(1)}  R² = ${result.r_squared.toFixed(2)}`;

  return (
    <Chart
      data={[{ x: betas, y: factors, orientation: "h", type: "bar",
        marker: { color: colors, opacity: 0.85 },
        error_x: { type: "data", array: errors, visible: true, color: "#555", thickness: 1.5 },
      } as any]}
      layout={{
        title: { text: title, font: { size: 15, color: "#f0f0ff" } },
        xaxis: { title: "Beta", gridcolor: BORDER, zerolinecolor: TXT2 },
        yaxis: { autorange: "reversed", gridcolor: BORDER },
        annotations: [{ xref: "paper", yref: "paper", x: 0.99, y: 0.02,
          text: annotation, showarrow: false, font: { size: 11, color: TXT2 },
          bgcolor: CARD2, bordercolor: BORDER, borderwidth: 1, borderpad: 6, align: "right",
        }],
      }}
      height={380}
    />
  );
}

function FactorTable({ result }: { result: FactorResult }) {
  const rows = [
    { factor: "Alpha (ann.)", exposure: `${(result.alpha_annualized * 100).toFixed(2)}%`, t: result.alpha_tstat.toFixed(2), sig: stars(result.alpha_pval) },
    ...Object.keys(result.betas).map(f => ({
      factor: f, exposure: result.betas[f].toFixed(3),
      t: result.tstats[f].toFixed(2), sig: stars(result.pvals[f]),
    })),
  ];
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-txt2 text-xs uppercase tracking-wider border-b border-border">
          <th className="pb-2 text-left">Factor</th>
          <th className="pb-2 text-right">Exposure</th>
          <th className="pb-2 text-right">t-stat</th>
          <th className="pb-2 text-right">Sig.</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(r => (
          <tr key={r.factor} className="border-b border-border/40 hover:bg-card2/50">
            <td className="py-2 font-medium text-txt">{r.factor}</td>
            <td className="py-2 text-right tabular-nums text-txt">{r.exposure}</td>
            <td className="py-2 text-right tabular-nums text-txt2">{r.t}</td>
            <td className="py-2 text-right text-accent font-bold">{r.sig}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function StockHeatmap({ stocks }: { stocks: Record<string, FactorResult> }) {
  const tickers = Object.keys(stocks);
  const r0      = stocks[tickers[0]];
  const factors = ["Alpha (ann.%)", ...Object.keys(r0.betas)];
  const z = tickers.map(t => {
    const r = stocks[t];
    return [r.alpha_annualized * 100, ...Object.values(r.betas)];
  });
  return (
    <Chart
      data={[{ type: "heatmap", z, x: factors, y: tickers,
        text: z.map(row => row.map(v => v.toFixed(2))),
        texttemplate: "%{text}", textfont: { size: 11, color: "white" },
        colorscale: [[0, NEG], [0.5, "#1c1c28"], [1, ACCENT]], zmid: 0,
      } as any]}
      layout={{ title: { text: "Per-Stock Factor Loadings", font: { size: 15, color: "#f0f0ff" } } }}
      height={Math.max(280, tickers.length * 50 + 100)}
    />
  );
}

export default function FactorAnalysis({ result }: { result: AnalysisResult }) {
  return (
    <div className="flex flex-col gap-5">
      <SectionHeader>Fama-French 5-Factor + Momentum</SectionHeader>
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 bg-card border border-border rounded-2xl p-4">
          <FactorBar result={result.ff.portfolio} title="Portfolio Factor Loadings (95% CI)" />
        </div>
        <div className="bg-card border border-border rounded-2xl p-5">
          <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-3">Regression Results</div>
          <FactorTable result={result.ff.portfolio} />
          <p className="text-xs text-txt2 mt-3">{result.ff.portfolio.n_obs} monthly obs · HC3 SEs · ★★★ p&lt;0.01</p>
        </div>
      </div>
      {Object.keys(result.ff.stocks).length > 0 && (
        <>
          <SectionHeader>Per-Stock Factor Loadings</SectionHeader>
          <div className="bg-card border border-border rounded-2xl p-4">
            <StockHeatmap stocks={result.ff.stocks} />
          </div>
        </>
      )}
    </div>
  );
}
