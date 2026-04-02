const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "bayes_token";

let authToken = localStorage.getItem(TOKEN_KEY);

function headers(json = true): Record<string, string> {
  const out: Record<string, string> = {};
  if (json) out["Content-Type"] = "application/json";
  if (authToken) out.Authorization = `Bearer ${authToken}`;
  return out;
}

function withQuery(path: string, query?: Record<string, string | number | undefined>) {
  const url = new URL(`${BASE}${path}`);
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
    });
  }
  return url.toString();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText);
  return r.json();
}

async function get<T>(path: string, query?: Record<string, string | number | undefined>): Promise<T> {
  const r = await fetch(withQuery(path, query), { headers: headers(false) });
  if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText);
  return r.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText);
  return r.json();
}

async function del(path: string) {
  const r = await fetch(`${BASE}${path}`, { method: "DELETE", headers: headers(false) });
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
  oil_exposure: {
    oil_proxy: string;
    covariance: number;
    annualized_covariance: number;
    beta: number;
    correlation: number;
    n_obs: number;
  };
  rates_exposure: {
    rates_proxy: string;
    covariance: number;
    annualized_covariance: number;
    beta: number;
    correlation: number;
    n_obs: number;
  };
  rolling_betas: { date: string; [key: string]: number | string }[];
  sharpe: number; sortino: number; max_drawdown: number;
  calmar: number; var95: number; cvar95: number; ann_return: number;
};

export type Trade = {
  id: number; portfolio_id: number; ticker: string; trade_date: string; action: string;
  quantity: number; price: number; notes: string;
};

export type User = {
  id: number;
  email: string;
  name: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type SavedPortfolio = {
  id: number;
  user_id: number;
  name: string;
  tickers: string[];
  weights: number[];
  start_date: string;
  end_date: string;
  created_at: string;
  updated_at: string;
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

function saveToken(token: string) {
  authToken = token;
  localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
  authToken = null;
  localStorage.removeItem(TOKEN_KEY);
}

export const api = {
  setToken: saveToken,
  clearToken,
  getStoredToken: () => authToken,
  signup:         (b: { email: string; password: string; name?: string }) => post<AuthResponse>("/auth/signup", b),
  login:          (b: { email: string; password: string }) => post<AuthResponse>("/auth/login", b),
  me:             () => get<User>("/auth/me"),
  getPortfolios:  () => get<SavedPortfolio[]>("/portfolios"),
  createPortfolio:(b: { name: string; tickers: string[]; weights: number[]; start_date: string; end_date: string }) =>
    post<SavedPortfolio>("/portfolios", b),
  updatePortfolio:(id: number, b: Partial<{ name: string; tickers: string[]; weights: number[]; start_date: string; end_date: string }>) =>
    put<SavedPortfolio>(`/portfolios/${id}`, b),
  deletePortfolio:(id: number) => del(`/portfolios/${id}`),
  analyze:        (b: object) => post<AnalysisResult>("/analyze", b),
  hedges:         (b: object) => post<{ factor_hedges: HedgeRow[]; industry_hedges: HedgeRow[] }>("/hedges", b),
  optimize:       (b: object) => post<OptimizeResult>("/optimize", b),
  simulate:       (b: object) => post<SimulateResult>("/simulate", b),
  backtest:       (b: object) => post<BacktestResult>("/backtest", b),
  getSignals:     (ticker: string) => get<SignalData>(`/signals/${ticker}`),
  getMacro:       ()          => get<MacroData>("/macro"),
  getTrades:      (portfolioId: number) => get<Trade[]>("/trades", { portfolio_id: portfolioId }),
  addTrade:       (b: object) => post("/trades", b),
  deleteTrade:    (id: number) => del(`/trades/${id}`),
  getPortfolio:   (portfolioId: number) => get<{ portfolio: SavedPortfolio; tickers: string[]; weights: number[]; positions: Position[] }>("/portfolio", { portfolio_id: portfolioId }),
  getPnl:         (portfolioId: number) => get<PnLRow[]>("/pnl", { portfolio_id: portfolioId }),
  getPortfolioValue: (portfolioId: number) => get<{ date: string; value: number }[]>("/portfolio-value", { portfolio_id: portfolioId }),
};
