import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import Dashboard from "./components/Dashboard";
import FactorAnalysis from "./components/FactorAnalysis";
import Industry from "./components/Industry";
import Covariance from "./components/Covariance";
import Analytics from "./components/Analytics";
import Hedges from "./components/Hedges";
import Optimizer from "./components/Optimizer";
import Simulate from "./components/Simulate";
import Backtest from "./components/Backtest";
import Signals from "./components/Signals";
import TradeLog from "./components/TradeLog";
import AuthScreen from "./components/AuthScreen";
import { AnalysisResult, api, SavedPortfolio, User } from "./api";

const TABS = [
  "Dashboard", "Factor Analysis", "Industry", "Covariance", "Analytics",
  "Hedges", "Optimizer", "Simulate", "Backtest", "Signals", "Trade Log",
];

export type PortfolioParams = {
  tickers: string[];
  weights: number[];
  startDate: string;
  endDate: string;
  includeIndustry: boolean;
};

export default function App() {
  const [tab, setTab] = useState(0);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [params, setParams] = useState<PortfolioParams | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [authLoading, setAuthLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [portfolios, setPortfolios] = useState<SavedPortfolio[]>([]);
  const [activePortfolioId, setActivePortfolioId] = useState<number | null>(null);

  const TRADE_TAB = TABS.length - 1;

  async function loadPortfolios(preferredId?: number | null) {
    const items = await api.getPortfolios();
    setPortfolios(items);
    if (!items.length) {
      setActivePortfolioId(null);
      return;
    }
    const nextId = preferredId && items.some((item) => item.id === preferredId)
      ? preferredId
      : activePortfolioId && items.some((item) => item.id === activePortfolioId)
        ? activePortfolioId
        : items[0].id;
    setActivePortfolioId(nextId ?? items[0].id);
  }

  async function handleAuthenticated(authUser: User) {
    setUser(authUser);
    await loadPortfolios();
    setAuthLoading(false);
  }

  function logout() {
    api.clearToken();
    setUser(null);
    setPortfolios([]);
    setActivePortfolioId(null);
    setResult(null);
    setParams(null);
    setError(null);
    setAuthLoading(false);
  }

  useEffect(() => {
    const token = api.getStoredToken();
    if (!token) {
      setAuthLoading(false);
      return;
    }
    api.me()
      .then(async (me) => {
        setUser(me);
        await loadPortfolios();
      })
      .catch(() => {
        api.clearToken();
        setUser(null);
      })
      .finally(() => setAuthLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (authLoading) {
    return (
      <div className="min-h-screen bg-bg text-txt flex items-center justify-center">
        <div className="flex items-center gap-3 text-sm text-txt2">
          <div className="w-5 h-5 rounded-full border-2 border-accent border-t-transparent animate-spin" />
          Restoring your workspace...
        </div>
      </div>
    );
  }

  if (!user) {
    return <AuthScreen onAuthenticated={handleAuthenticated} />;
  }

  const activePortfolio = portfolios.find((portfolio) => portfolio.id === activePortfolioId) ?? null;

  return (
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
          user={user}
          portfolios={portfolios}
          activePortfolioId={activePortfolioId}
          onSelectPortfolio={(id) => {
            setActivePortfolioId(id);
            setError(null);
          }}
          onPortfolioSaved={async (portfolioId) => {
            await loadPortfolios(portfolioId);
          }}
          onLogout={logout}
        />
      </div>

      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <div className="flex flex-wrap items-center justify-between gap-3 px-3 sm:px-6 pt-4 pb-0 bg-bg">
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden shrink-0 p-2 rounded-lg text-txt2 hover:text-txt hover:bg-card2"
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                <path d="M2 4.5h16M2 10h16M2 15.5h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" />
              </svg>
            </button>
            <div className="min-w-0">
              <div className="text-xs uppercase tracking-[0.2em] text-txt2">Workspace</div>
              <div className="text-lg font-bold text-txt truncate">
                {activePortfolio?.name ?? "Pick or create a portfolio"}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:block text-right">
              <div className="text-sm font-semibold text-txt">{user.name || user.email}</div>
              <div className="text-xs text-txt2">{user.email}</div>
            </div>
            <div className="flex gap-1 bg-card rounded-xl p-1 border border-border overflow-x-auto scrollbar-hide max-w-full">
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
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3 sm:p-6">
          {error && (
            <div className="mb-4 p-4 bg-neg/10 border border-neg/30 rounded-xl text-neg text-sm">
              {error}
            </div>
          )}
          {!activePortfolioId && !loading && (
            <div className="mb-4 p-4 bg-card border border-border rounded-xl text-txt2 text-sm">
              Create a portfolio in the sidebar to save holdings, attach trades, and run analysis.
            </div>
          )}
          {loading && (
            <div className="flex flex-col items-center justify-center h-64 gap-4">
              <div className="w-12 h-12 rounded-full border-2 border-accent border-t-transparent animate-spin" />
              <p className="text-txt2">Downloading data &amp; running regressions... (15-30 s)</p>
            </div>
          )}
          {!loading && !result && tab !== TRADE_TAB && <Landing />}
          {!loading && result && tab === 0 && <Dashboard result={result} />}
          {!loading && result && tab === 1 && <FactorAnalysis result={result} />}
          {!loading && result && tab === 2 && <Industry result={result} />}
          {!loading && result && tab === 3 && <Covariance result={result} />}
          {!loading && result && tab === 4 && <Analytics result={result} />}
          {!loading && result && tab === 5 && <Hedges result={result} params={params!} />}
          {!loading && result && tab === 6 && <Optimizer result={result} params={params!} />}
          {!loading && result && tab === 7 && <Simulate params={params!} />}
          {!loading && result && tab === 8 && <Backtest params={params!} />}
          {!loading && result && tab === 9 && <Signals params={params!} />}
          {!loading && tab === TRADE_TAB && activePortfolioId && (
            <TradeLog
              portfolioId={activePortfolioId}
              portfolioName={activePortfolio?.name ?? "Portfolio"}
              onLoad={(tickers, weights) => {
                setParams((current) => current ? { ...current, tickers, weights } : current);
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function Landing() {
  return (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center gap-4">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" className="text-accent">
        <path d="M2 20 C6 20, 6 4, 12 4 S18 20, 22 20" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" fill="none" />
        <path d="M2 20 C6 20, 8 10, 12 10 S18 20, 22 20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.4" />
      </svg>
      <h1 className="text-3xl font-extrabold text-txt">Bayes</h1>
      <p className="text-txt2 max-w-md">
        Pick a saved portfolio or build a new one in the sidebar, then click <span className="text-accent font-semibold">Run Analysis</span>.
      </p>
    </div>
  );
}
