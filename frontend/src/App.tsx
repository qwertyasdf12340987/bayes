import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Dashboard from "./components/Dashboard";
import FactorAnalysis from "./components/FactorAnalysis";
import Industry from "./components/Industry";
import Covariance from "./components/Covariance";
import Analytics from "./components/Analytics";
import Hedges from "./components/Hedges";
import TradeLog from "./components/TradeLog";
import { AnalysisResult } from "./api";

const TABS = ["Dashboard", "Factor Analysis", "Industry", "Covariance", "Analytics", "Hedges", "Trade Log"];

export type PortfolioParams = {
  tickers: string[];
  weights: number[];
  startDate: string;
  endDate: string;
  includeIndustry: boolean;
};

export default function App() {
  const [tab, setTab]           = useState(0);
  const [result, setResult]     = useState<AnalysisResult | null>(null);
  const [params, setParams]     = useState<PortfolioParams | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  return (
    <div className="flex h-screen bg-bg overflow-hidden">
      <Sidebar
        loading={loading}
        setLoading={setLoading}
        setResult={setResult}
        setParams={setParams}
        setError={setError}
        setTab={setTab}
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Tab bar */}
        <div className="flex items-center gap-1 px-6 pt-5 pb-0 bg-bg">
          <div className="flex gap-1 bg-card rounded-xl p-1 border border-border">
            {TABS.map((t, i) => (
              <button
                key={t}
                onClick={() => setTab(i)}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                  tab === i
                    ? "bg-gradient-to-r from-accent to-accent2 text-white shadow"
                    : "text-txt2 hover:text-txt"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-4 bg-neg/10 border border-neg/30 rounded-xl text-neg text-sm">
              {error}
            </div>
          )}
          {loading && (
            <div className="flex flex-col items-center justify-center h-64 gap-4">
              <div className="w-12 h-12 rounded-full border-2 border-accent border-t-transparent animate-spin" />
              <p className="text-txt2">Downloading data & running regressions… (15–30 s)</p>
            </div>
          )}
          {!loading && !result && tab !== 6 && (
            <Landing />
          )}
          {!loading && result && tab === 0 && <Dashboard result={result} />}
          {!loading && result && tab === 1 && <FactorAnalysis result={result} />}
          {!loading && result && tab === 2 && <Industry result={result} />}
          {!loading && result && tab === 3 && <Covariance result={result} />}
          {!loading && result && tab === 4 && <Analytics result={result} />}
          {!loading && result && tab === 5 && <Hedges result={result} params={params!} />}
          {!loading && tab === 6 && <TradeLog onLoad={(t, w) => {
            setParams(p => p ? { ...p, tickers: t, weights: w } : null);
          }} />}
        </div>
      </div>
    </div>
  );
}

function Landing() {
  return (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center gap-4">
      <div className="text-6xl">📊</div>
      <h1 className="text-3xl font-extrabold text-txt">Bayes</h1>
      <p className="text-txt2 max-w-md">
        Enter your holdings in the sidebar, choose a date range,
        then click <span className="text-accent font-semibold">Run Analysis</span>.
      </p>
      <div className="grid grid-cols-3 gap-4 mt-6 text-left max-w-2xl">
        {[
          ["📈", "Factor Analysis", "FF5 + Momentum regressions with per-stock breakdowns"],
          ["🏭", "Industry", "Sector ETF regression to find your sector tilts"],
          ["🔗", "Covariance", "Correlation matrix and risk contribution by stock"],
          ["📉", "Analytics", "Sharpe, Sortino, VaR, drawdown vs S&P 500"],
          ["🛡️", "Hedges", "Exact ETF positions to neutralise factor exposure"],
          ["📋", "Trade Log", "Persistent trade history with live P&L"],
        ].map(([icon, title, desc]) => (
          <div key={title as string} className="bg-card border border-border rounded-xl p-4">
            <div className="text-2xl mb-2">{icon}</div>
            <div className="font-semibold text-txt text-sm mb-1">{title}</div>
            <div className="text-txt2 text-xs">{desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
