import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Dashboard from "./components/Dashboard";
import FactorAnalysis from "./components/FactorAnalysis";
import Industry from "./components/Industry";
import Covariance from "./components/Covariance";
import Analytics from "./components/Analytics";
import Hedges from "./components/Hedges";
import Optimizer from "./components/Optimizer";
import Kelly from "./components/Kelly";
import Simulate from "./components/Simulate";
import Backtest from "./components/Backtest";
import Signals from "./components/Signals";
import Education from "./components/Education";
import TradeLog from "./components/TradeLog";
import AuthModal from "./components/AuthModal";
import { AnalysisResult, AuthUser } from "./api";
import { clearAuth, getUser } from "./auth";

const TABS = [
  "Dashboard", "Factor Analysis", "Industry", "Covariance", "Analytics",
  "Hedges", "Optimizer", "Kelly", "Simulate", "Backtest", "Signals", "Education", "Trade Log",
];

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
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [user, setUser]         = useState<AuthUser | null>(getUser());
  const [showAuth, setShowAuth] = useState(false);

  const TRADE_TAB = TABS.length - 1; // Trade Log is always last
  const EDU_TAB   = TABS.indexOf("Education");

  return (
    <>
    <div className="flex h-screen bg-bg overflow-hidden">
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/60 z-40 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      <div className={`fixed lg:static inset-y-0 left-0 z-50 transform transition-transform lg:transform-none ${
        sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
      }`}>
        <Sidebar
          loading={loading}
          setLoading={setLoading}
          setResult={setResult}
          setParams={setParams}
          setError={setError}
          setTab={(i: number) => { setTab(i); setSidebarOpen(false); }}
        />
      </div>

      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <div className="flex items-center gap-2 px-3 sm:px-6 pt-4 pb-0 bg-bg">
          <button onClick={() => setSidebarOpen(true)}
            className="lg:hidden shrink-0 p-2 rounded-lg text-txt2 hover:text-txt hover:bg-card2">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <path d="M2 4.5h16M2 10h16M2 15.5h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
            </svg>
          </button>
          <div className="flex gap-1 bg-card rounded-xl p-1 border border-border overflow-x-auto scrollbar-hide flex-1">
            {TABS.map((t, i) => (
              <button
                key={t}
                onClick={() => setTab(i)}
                className={`px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${
                  tab === i
                    ? "bg-gradient-to-r from-accent to-accent2 text-white shadow"
                    : "text-txt2 hover:text-txt"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Auth button */}
          {user ? (
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-txt2 hidden sm:block">{user.name || user.email}</span>
              <button onClick={() => { clearAuth(); setUser(null); }}
                className="text-xs text-txt2 hover:text-neg border border-border rounded-lg px-2.5 py-1.5 transition-all whitespace-nowrap">
                Sign out
              </button>
            </div>
          ) : (
            <button onClick={() => setShowAuth(true)}
              className="shrink-0 text-xs font-semibold text-white px-3 py-1.5 rounded-lg
                bg-gradient-to-r from-accent to-accent2 hover:opacity-90 transition-all whitespace-nowrap">
              Sign in
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-3 sm:p-6">
          {error && (
            <div className="mb-4 p-4 bg-neg/10 border border-neg/30 rounded-xl text-neg text-sm">
              {error}
            </div>
          )}
          {loading && (
            <div className="flex flex-col items-center justify-center h-64 gap-4">
              <div className="w-12 h-12 rounded-full border-2 border-accent border-t-transparent animate-spin" />
              <p className="text-txt2">Downloading data & running regressions... (15-30 s)</p>
            </div>
          )}
          {!loading && !result && tab !== TRADE_TAB && tab !== EDU_TAB && <Landing />}
          {!loading && result && tab === 0  && <Dashboard result={result} />}
          {!loading && result && tab === 1  && <FactorAnalysis result={result} />}
          {!loading && result && tab === 2  && <Industry result={result} />}
          {!loading && result && tab === 3  && <Covariance result={result} />}
          {!loading && result && tab === 4  && <Analytics result={result} />}
          {!loading && result && tab === 5  && <Hedges result={result} params={params!} />}
          {!loading && result && tab === 6  && <Optimizer result={result} params={params!} />}
          {!loading && result && tab === 7  && <Kelly result={result} params={params!} />}
          {!loading && result && tab === 8  && <Simulate params={params!} />}
          {!loading && result && tab === 9  && <Backtest params={params!} />}
          {!loading && result && tab === 10 && <Signals params={params!} />}
          {!loading && tab === EDU_TAB      && <Education />}
          {!loading && tab === TRADE_TAB    && <TradeLog onLoad={(t, w) => {
            setParams(p => p ? { ...p, tickers: t, weights: w } : null);
          }} />}
        </div>
      </div>
    </div>

    {showAuth && (
      <AuthModal
        onClose={() => setShowAuth(false)}
        onAuth={(u) => setUser(u)}
      />
    )}
    </>
  );
}

function Landing() {
  return (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center gap-4">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" className="text-accent">
        <path d="M2 20 C6 20, 6 4, 12 4 S18 20, 22 20" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" fill="none"/>
        <path d="M2 20 C6 20, 8 10, 12 10 S18 20, 22 20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.4"/>
      </svg>
      <h1 className="text-3xl font-extrabold text-txt">Bayes</h1>
      <p className="text-txt2 max-w-md">
        Enter your holdings in the sidebar, choose a date range,
        then click <span className="text-accent font-semibold">Run Analysis</span>.
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mt-6 text-left max-w-3xl">
        {[
          ["Factor Analysis", "FF5 + Momentum regressions with per-stock breakdowns"],
          ["Industry", "Sector ETF regression to find your sector tilts"],
          ["Covariance", "Correlation matrix and risk contribution by stock"],
          ["Analytics", "Sharpe, Sortino, VaR, drawdown vs S&P 500"],
          ["Hedges", "ETF positions to neutralise factor exposure"],
          ["Optimizer", "Mean-variance optimisation to maximise Sharpe"],
          ["Kelly", "Kelly Criterion log-optimal position sizing"],
          ["Simulate", "Monte Carlo simulation of portfolio outcomes"],
          ["Backtest", "Test rebalancing strategies against buy & hold"],
          ["Signals", "Fundamentals, analyst targets, options flow"],
          ["Education", "Factor-neutral portfolio construction explained"],
          ["Trade Log", "Persistent trade history with live P&L"],
        ].map(([title, desc]) => (
          <div key={title as string} className="bg-card border border-border rounded-xl p-4 hover:border-accent/40 transition-colors">
            <div className="font-semibold text-txt text-sm mb-1">{title}</div>
            <div className="text-txt2 text-xs leading-relaxed">{desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
