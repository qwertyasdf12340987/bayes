import { useEffect, useMemo, useState } from "react";
import { api, AnalysisResult, SavedPortfolio, User } from "../api";
import { PortfolioParams } from "../App";

type Props = {
  loading: boolean;
  setLoading: (v: boolean) => void;
  setResult: (v: AnalysisResult | null) => void;
  setParams: (v: PortfolioParams) => void;
  setError: (v: string | null) => void;
  setTab: (v: number) => void;
  user: User;
  portfolios: SavedPortfolio[];
  activePortfolioId: number | null;
  onSelectPortfolio: (id: number) => void;
  onPortfolioSaved: (portfolioId: number | null) => Promise<void> | void;
  onLogout: () => void;
};

type SourceMode = "manual" | "tradelog";

const fiveYearsAgo = () => {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 5);
  return d.toISOString().split("T")[0];
};

const today = () => new Date().toISOString().split("T")[0];

function rowsFromPortfolio(portfolio: SavedPortfolio | null) {
  if (!portfolio || !portfolio.tickers.length) return [{ ticker: "AAPL", amount: 10000 }];
  return portfolio.tickers.map((ticker, index) => ({
    ticker,
    amount: Number(portfolio.weights[index] ?? 0),
  }));
}

export default function Sidebar({
  loading,
  setLoading,
  setResult,
  setParams,
  setError,
  setTab,
  user,
  portfolios,
  activePortfolioId,
  onSelectPortfolio,
  onPortfolioSaved,
  onLogout,
}: Props) {
  const activePortfolio = portfolios.find((portfolio) => portfolio.id === activePortfolioId) ?? null;

  const [source, setSource] = useState<SourceMode>("manual");
  const [rows, setRows] = useState(rowsFromPortfolio(activePortfolio));
  const [startDate, setStartDate] = useState(activePortfolio?.start_date || fiveYearsAgo());
  const [endDate, setEndDate] = useState(activePortfolio?.end_date || today());
  const [industry, setIndustry] = useState(true);
  const [tlTickers, setTlTickers] = useState<string[]>([]);
  const [tlWeights, setTlWeights] = useState<number[]>([]);
  const [portfolioName, setPortfolioName] = useState(activePortfolio?.name || "");
  const [savingPortfolio, setSavingPortfolio] = useState(false);
  const [portfolioNotice, setPortfolioNotice] = useState<string | null>(null);

  useEffect(() => {
    setRows(rowsFromPortfolio(activePortfolio));
    setStartDate(activePortfolio?.start_date || fiveYearsAgo());
    setEndDate(activePortfolio?.end_date || today());
    setPortfolioName(activePortfolio?.name || "");
    setResult(null);
    setParams({
      tickers: activePortfolio?.tickers ?? [],
      weights: activePortfolio?.weights ?? [],
      startDate: activePortfolio?.start_date || fiveYearsAgo(),
      endDate: activePortfolio?.end_date || today(),
      includeIndustry: industry,
    });
    if (activePortfolioId) {
      api.getPortfolio(activePortfolioId)
        .then((portfolio) => {
          setTlTickers(portfolio.tickers);
          setTlWeights(portfolio.weights);
        })
        .catch(() => {
          setTlTickers([]);
          setTlWeights([]);
        });
    } else {
      setTlTickers([]);
      setTlWeights([]);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePortfolioId]);

  const tickers = useMemo(
    () => (source === "manual"
      ? rows.map((row) => row.ticker.toUpperCase().trim()).filter(Boolean)
      : tlTickers),
    [rows, source, tlTickers],
  );

  const weights = useMemo(
    () => (source === "manual"
      ? rows.filter((row) => row.ticker.trim()).map((row) => Number(row.amount))
      : tlWeights),
    [rows, source, tlWeights],
  );

  async function run() {
    if (!tickers.length) {
      setError("Add at least one holding before running analysis");
      return;
    }
    setError(null);
    setPortfolioNotice(null);
    setLoading(true);
    try {
      const nextParams: PortfolioParams = {
        tickers,
        weights,
        startDate,
        endDate,
        includeIndustry: industry,
      };
      setParams(nextParams);
      const res = await api.analyze({
        tickers,
        weights,
        start_date: startDate,
        end_date: endDate,
        include_industry: industry,
      });
      setResult(res);
      setTab(0);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function savePortfolio() {
    setPortfolioNotice(null);
    setError(null);
    if (!portfolioName.trim()) {
      setError("Give the portfolio a name before saving it");
      return;
    }
    if (!tickers.length) {
      setError("Add holdings before saving the portfolio");
      return;
    }

    setSavingPortfolio(true);
    try {
      const payload = {
        name: portfolioName.trim(),
        tickers,
        weights,
        start_date: startDate,
        end_date: endDate,
      };
      if (activePortfolioId) {
        await api.updatePortfolio(activePortfolioId, payload);
        await onPortfolioSaved(activePortfolioId);
        setPortfolioNotice("Portfolio updated");
      } else {
        const created = await api.createPortfolio(payload);
        await onPortfolioSaved(created.id);
        onSelectPortfolio(created.id);
        setPortfolioNotice("Portfolio created");
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSavingPortfolio(false);
    }
  }

  async function createFreshPortfolio() {
    setPortfolioNotice(null);
    setError(null);
    setSavingPortfolio(true);
    try {
      const created = await api.createPortfolio({
        name: `Portfolio ${portfolios.length + 1}`,
        tickers: ["AAPL"],
        weights: [10000],
        start_date: fiveYearsAgo(),
        end_date: today(),
      });
      await onPortfolioSaved(created.id);
      onSelectPortfolio(created.id);
      setSource("manual");
      setPortfolioNotice("New portfolio ready");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSavingPortfolio(false);
    }
  }

  async function removePortfolio() {
    if (!activePortfolioId) return;
    setPortfolioNotice(null);
    setError(null);
    setSavingPortfolio(true);
    try {
      await api.deletePortfolio(activePortfolioId);
      const fallbackId = portfolios.find((portfolio) => portfolio.id !== activePortfolioId)?.id ?? null;
      await onPortfolioSaved(fallbackId);
      if (fallbackId) onSelectPortfolio(fallbackId);
      setPortfolioNotice("Portfolio deleted");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSavingPortfolio(false);
    }
  }

  return (
    <div className="w-72 shrink-0 bg-[#0d0d16] border-r border-border flex flex-col h-full overflow-y-auto">
      <div className="p-5 border-b border-border">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-accent">
                <path d="M2 20 C6 20, 6 4, 12 4 S18 20, 22 20" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" fill="none" />
                <path d="M2 20 C6 20, 8 10, 12 10 S18 20, 22 20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.4" />
              </svg>
              <span className="text-xl font-extrabold text-txt">Bayes</span>
            </div>
            <div className="text-xs text-txt2 mt-2">{user.name || user.email}</div>
          </div>
          <button
            onClick={onLogout}
            className="px-3 py-2 rounded-lg border border-border text-xs text-txt2 hover:text-txt hover:border-accent transition-all"
          >
            Log out
          </button>
        </div>
      </div>

      <div className="p-4 flex-1 flex flex-col gap-4">
        <div className="rounded-2xl border border-border bg-card p-4">
          <div className="text-xs text-txt2 font-semibold uppercase tracking-wider mb-3">Named Portfolio</div>
          <label className="text-xs text-txt2">Portfolio</label>
          <select
            value={activePortfolioId ?? ""}
            onChange={(e) => onSelectPortfolio(Number(e.target.value))}
            className="mt-2 text-sm w-full"
          >
            {portfolios.map((portfolio) => (
              <option key={portfolio.id} value={portfolio.id}>
                {portfolio.name}
              </option>
            ))}
          </select>

          <label className="block text-xs text-txt2 mt-4">Name</label>
          <input
            value={portfolioName}
            onChange={(e) => setPortfolioName(e.target.value)}
            placeholder="Finance Club Long Book"
            className="mt-2 text-sm w-full"
          />

          <div className="grid grid-cols-2 gap-2 mt-3">
            <button
              onClick={savePortfolio}
              disabled={savingPortfolio}
              className="py-2 rounded-lg bg-gradient-to-r from-accent to-accent2 text-white text-sm font-semibold disabled:opacity-40"
            >
              {savingPortfolio ? "Saving..." : "Save"}
            </button>
            <button
              onClick={createFreshPortfolio}
              disabled={savingPortfolio}
              className="py-2 rounded-lg border border-border text-sm text-txt2 hover:text-txt hover:border-accent transition-all disabled:opacity-40"
            >
              New
            </button>
          </div>

          <button
            onClick={removePortfolio}
            disabled={savingPortfolio || portfolios.length <= 1}
            className="mt-2 w-full py-2 rounded-lg border border-border text-sm text-neg hover:border-neg transition-all disabled:opacity-30"
          >
            Delete Portfolio
          </button>

          {portfolioNotice && <div className="mt-3 text-xs text-pos">{portfolioNotice}</div>}
        </div>

        <div className="flex rounded-lg overflow-hidden border border-border text-xs font-semibold">
          {(["manual", "tradelog"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setSource(mode)}
              className={`flex-1 py-2 transition-all ${source === mode ? "bg-accent text-white" : "text-txt2 hover:text-txt"}`}
            >
              {mode === "manual" ? "Manual" : "Trade Log"}
            </button>
          ))}
        </div>

        {source === "manual" ? (
          <div className="flex flex-col gap-2">
            <div className="text-xs text-txt2 font-semibold uppercase tracking-wider">Holdings</div>
            <div className="grid grid-cols-2 gap-1 text-xs text-txt2 font-semibold px-1">
              <span>Ticker</span>
              <span>Amount ($)</span>
            </div>
            {rows.map((row, index) => (
              <div key={`${row.ticker}-${index}`} className="grid grid-cols-2 gap-1">
                <input
                  value={row.ticker}
                  placeholder="AAPL"
                  onChange={(e) => setRows((current) => current.map((item, i) => i === index ? { ...item, ticker: e.target.value } : item))}
                  className="text-sm"
                />
                <input
                  type="number"
                  value={row.amount}
                  min={0}
                  onChange={(e) => setRows((current) => current.map((item, i) => i === index ? { ...item, amount: Number(e.target.value) } : item))}
                  className="text-sm"
                />
              </div>
            ))}
            <div className="flex gap-2">
              <button
                onClick={() => setRows((current) => [...current, { ticker: "", amount: 0 }])}
                className="flex-1 py-1.5 rounded-lg border border-border text-xs text-txt2 hover:border-accent hover:text-accent transition-all"
              >
                + Add row
              </button>
              {rows.length > 1 && (
                <button
                  onClick={() => setRows((current) => current.slice(0, -1))}
                  className="px-3 py-1.5 rounded-lg border border-border text-xs text-neg hover:border-neg transition-all"
                >
                  −
                </button>
              )}
            </div>
          </div>
        ) : (
          <div>
            <div className="text-xs text-txt2 font-semibold uppercase tracking-wider mb-2">From Trade Log</div>
            {tlTickers.length ? (
              <div className="flex flex-col gap-1">
                {tlTickers.map((ticker, index) => (
                  <div key={ticker} className="flex justify-between text-sm">
                    <span className="font-semibold text-txt">{ticker}</span>
                    <span className="text-txt2">{tlWeights[index]?.toFixed(4)} shares</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-txt2">No trades logged for this portfolio yet. Use the Trade Log tab to add them.</p>
            )}
          </div>
        )}

        <div className="border-t border-border pt-4 flex flex-col gap-2">
          <div className="text-xs text-txt2 font-semibold uppercase tracking-wider">Date Range</div>
          <div className="flex flex-col gap-1.5">
            <div className="text-xs text-txt2">From</div>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="text-sm w-full" />
            <div className="text-xs text-txt2 mt-1">To</div>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="text-sm w-full" />
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-txt2 cursor-pointer">
          <input
            type="checkbox"
            checked={industry}
            onChange={(e) => setIndustry(e.target.checked)}
            className="accent-accent w-4 h-4"
          />
          Industry analysis
        </label>
      </div>

      <div className="p-4 border-t border-border">
        <button
          onClick={run}
          disabled={loading || !tickers.length}
          className="w-full py-3 rounded-xl font-bold text-sm text-white transition-all bg-gradient-to-r from-accent to-accent2 disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 active:scale-95"
        >
          {loading ? "Running…" : "Run Analysis"}
        </button>
      </div>
    </div>
  );
}
