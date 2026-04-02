const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText);
  return r.json();
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText);
  return r.json();
}

async function del(path: string) {
  const r = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!r.ok) throw new Error(r.statusText);
}

export type FactorResult = {
  alpha: number; alpha_annualized: number; alpha_tstat: number; alpha_pval: number;
  betas: Record<string, number>; tstats: Record<string, number>; pvals: Record<string, number>;
  r_squared: number; r_squared_adj: number; n_obs: number;
};

export type AnalysisResult = {
  ff: { portfolio: FactorResult; stocks: Record<string, FactorResult> };
  ind: FactorResult | null;
  cov: Record<string, Record<string, number>>;
  corr: Record<string, Record<string, number>>;
  vols: Record<string, number>;
  mrc: Record<string, number>;
  port_vol: number;
  port_returns: { date: string; value: number }[];
  stock_returns: Record<string, { date: string; value: number }[]>;
  benchmark: { date: string; value: number }[];
  rolling_betas: { date: string; [key: string]: number | string }[];
  sharpe: number; sortino: number; max_drawdown: number;
  calmar: number; var95: number; cvar95: number; ann_return: number;
};

export type Trade = {
  id: number; ticker: string; trade_date: string; action: string;
  quantity: number; price: number; notes: string;
};

export type Position = { Ticker: string; "Net Qty": number; "Avg Cost": number; "Cost Basis": number };
export type PnLRow = {
  Ticker: string; "Net Qty": number; "Avg Cost": number;
  "Current Price": number; "Market Value": number;
  "Unrealized P&L": number; "P&L %": number;
};
export type HedgeRow = {
  factor?: string; sector?: string; port_beta: number;
  hedge_etf: string; direction: string;
  notional: number; current_price: number | null; approx_shares: number | null;
};

export type OptimizeResult = {
  optimal_weights: Record<string, number>;
  current_weights: Record<string, number>;
  expected_return: number;
  expected_vol: number;
  expected_sharpe: number;
  current_expected_return: number;
  current_expected_vol: number;
  current_expected_sharpe: number;
  portfolio_value: number;
  adjustments: Record<string, {
    current_pct: number;
    optimal_pct: number;
    current_dollars: number;
    optimal_dollars: number;
    delta_dollars: number;
    action: string;
  }>;
};

export type SimulateResult = {
  n_simulations: number;
  horizon_months: number;
  percentile_paths: Record<number, number[]>;
  months: number[];
  terminal_values: number[];
  prob_loss: number;
  median_return: number;
  percentile_5_return: number;
  percentile_95_return: number;
  expected_annual_return: number;
  expected_annual_vol: number;
};

export type BacktestResult = {
  dates: string[];
  rebalanced: number[];
  buy_and_hold: number[];
  rebalance_freq: string;
  metrics: {
    ann_return: number;
    ann_vol: number;
    sharpe: number;
    max_drawdown: number;
    total_return: number;
  };
};

export type SignalData = {
  ticker: string;
  name: string;
  sector: string;
  market_cap: number | null;
  pe_ratio: number | null;
  forward_pe: number | null;
  dividend_yield: number | null;
  beta: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
  avg_volume: number | null;
  earnings_date: string | null;
  recommendation: string | null;
  target_price: number | null;
  analyst_count: number | null;
  put_call_ratio: number | null;
  short_percent: number | null;
};

export type MacroData = {
  vix: number | null;
  us10y: number | null;
  us3m: number | null;
  spy_price: number | null;
  spy_pe: number | null;
};

export const api = {
  analyze:        (b: object) => post<AnalysisResult>("/analyze", b),
  hedges:         (b: object) => post<{ factor_hedges: HedgeRow[]; industry_hedges: HedgeRow[] }>("/hedges", b),
  optimize:       (b: object) => post<OptimizeResult>("/optimize", b),
  simulate:       (b: object) => post<SimulateResult>("/simulate", b),
  backtest:       (b: object) => post<BacktestResult>("/backtest", b),
  getSignals:     (ticker: string) => get<SignalData>(`/signals/${ticker}`),
  getMacro:       ()          => get<MacroData>("/macro"),
  getTrades:      ()          => get<Trade[]>("/trades"),
  addTrade:       (b: object) => post("/trades", b),
  deleteTrade:    (id: number) => del(`/trades/${id}`),
  getPortfolio:   ()          => get<{ tickers: string[]; weights: number[]; positions: Position[] }>("/portfolio"),
  getPnl:         ()          => get<PnLRow[]>("/pnl"),
  getPortfolioValue: ()       => get<{ date: string; value: number }[]>("/portfolio-value"),
};
