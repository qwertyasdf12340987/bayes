import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";

const Plot = createPlotlyComponent(Plotly as any);

const BASE_LAYOUT: Partial<Plotly.Layout> = {
  paper_bgcolor: "#13131c",
  plot_bgcolor:  "#0d0d14",
  font:          { color: "#f0f0ff", family: "Inter, system-ui, sans-serif", size: 12 },
  margin:        { l: 16, r: 16, t: 48, b: 16 },
  xaxis:         { gridcolor: "#2a2a38", zerolinecolor: "#2a2a38" },
  yaxis:         { gridcolor: "#2a2a38", zerolinecolor: "#2a2a38" },
};

type Props = {
  data: Plotly.Data[];
  layout?: Partial<Plotly.Layout>;
  height?: number;
};

export default function Chart({ data, layout = {}, height = 340 }: Props) {
  return (
    <Plot
      data={data}
      layout={{ ...BASE_LAYOUT, height, ...layout } as Plotly.Layout}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%" }}
    />
  );
}

// Shared colour palette
export const PALETTE = [
  "#d946ef", "#f472b6", "#4ade80", "#818cf8",
  "#fb923c", "#fbbf24", "#60a5fa", "#a78bfa",
];
export const POS    = "#4ade80";
export const NEG    = "#fb7185";
export const ACCENT = "#d946ef";
export const PINK   = "#f472b6";
export const TXT2   = "#8888aa";
export const BORDER = "#2a2a38";
export const CARD2  = "#1c1c28";
