import { AnalysisResult, FactorResult } from "../api";
import Chart, { ACCENT, NEG, BORDER, TXT2, CARD2 } from "./Chart";
import { SectionHeader } from "./Dashboard";

function stars(p: number) { return p < 0.01 ? "★★★" : p < 0.05 ? "★★" : p < 0.1 ? "★" : ""; }

export default function Industry({ result }: { result: AnalysisResult }) {
  if (!result.ind) {
    return (
      <div className="flex flex-col gap-5">
        <SectionHeader>Industry / Sector Analysis</SectionHeader>
        <div className="bg-card border border-border rounded-2xl p-8 text-center text-txt2">
          Industry analysis was not requested. Re-run with the "Industry analysis" checkbox enabled.
        </div>
      </div>
    );
  }

  const ind = result.ind as FactorResult;
  const factors = Object.keys(ind.betas);
  const betas   = factors.map(f => ind.betas[f]);
  const tstats  = factors.map(f => ind.tstats[f]);
  const errors  = betas.map((b, i) => tstats[i] ? Math.abs(b / tstats[i]) * 1.96 : 0);
  const colors  = betas.map(b => b >= 0 ? ACCENT : NEG);

  const alpha = ind.alpha_annualized * 100;
  const annotation = `α = ${alpha.toFixed(1)}%  t = ${ind.alpha_tstat.toFixed(1)}  R² = ${ind.r_squared.toFixed(2)}`;

  const rows = [
    { factor: "Alpha (ann.)", exposure: `${(ind.alpha_annualized * 100).toFixed(2)}%`, t: ind.alpha_tstat.toFixed(2), sig: stars(ind.alpha_pval) },
    ...factors.map(f => ({
      factor: f, exposure: ind.betas[f].toFixed(3),
      t: ind.tstats[f].toFixed(2), sig: stars(ind.pvals[f]),
    })),
  ];

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader>Industry / Sector Analysis</SectionHeader>
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 bg-card border border-border rounded-2xl p-4">
          <Chart
            data={[{ x: betas, y: factors, orientation: "h", type: "bar",
              marker: { color: colors, opacity: 0.85 },
              error_x: { type: "data", array: errors, visible: true, color: "#555", thickness: 1.5 },
            } as any]}
            layout={{
              title: { text: "Sector ETF Loadings (95% CI)", font: { size: 15, color: "#f0f0ff" } },
              xaxis: { title: "Beta", gridcolor: BORDER, zerolinecolor: TXT2 },
              yaxis: { autorange: "reversed", gridcolor: BORDER },
              annotations: [{ xref: "paper", yref: "paper", x: 0.99, y: 0.02,
                text: annotation, showarrow: false, font: { size: 11, color: TXT2 },
                bgcolor: CARD2, bordercolor: BORDER, borderwidth: 1, borderpad: 6, align: "right",
              }],
            }}
            height={Math.max(380, factors.length * 32 + 120)}
          />
        </div>
        <div className="bg-card border border-border rounded-2xl p-5">
          <div className="text-xs text-txt2 uppercase tracking-wider font-semibold mb-3">Sector Regression</div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-txt2 text-xs uppercase tracking-wider border-b border-border">
                <th className="pb-2 text-left">Sector</th>
                <th className="pb-2 text-right">Beta</th>
                <th className="pb-2 text-right">t</th>
                <th className="pb-2 text-right">Sig.</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.factor} className="border-b border-border/40 hover:bg-card2/50">
                  <td className="py-1.5 text-xs font-medium text-txt truncate max-w-[90px]">{r.factor}</td>
                  <td className="py-1.5 text-right tabular-nums text-txt text-xs">{r.exposure}</td>
                  <td className="py-1.5 text-right tabular-nums text-txt2 text-xs">{r.t}</td>
                  <td className="py-1.5 text-right text-accent font-bold text-xs">{r.sig}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-txt2 mt-3">{ind.n_obs} monthly obs · HC3 SEs · ★★★ p&lt;0.01</p>
        </div>
      </div>
    </div>
  );
}
