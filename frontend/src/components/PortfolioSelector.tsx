import { useEffect, useState } from "react";
import { api, SavedPortfolio } from "../api";

type Props = {
  tickers: string[];
  weights: number[];
  startDate: string;
  endDate: string;
  onLoad: (p: SavedPortfolio) => void;
};

export default function PortfolioSelector({ tickers, weights, startDate, endDate, onLoad }: Props) {
  const [portfolios, setPortfolios] = useState<SavedPortfolio[]>([]);
  const [open, setOpen]             = useState(false);
  const [saving, setSaving]         = useState(false);
  const [newName, setNewName]       = useState("");
  const [error, setError]           = useState<string | null>(null);

  useEffect(() => {
    api.getPortfolios().then(setPortfolios).catch(() => {});
  }, []);

  async function save() {
    if (!newName.trim() || !tickers.length) return;
    setSaving(true);
    setError(null);
    try {
      const p = await api.createPortfolio({
        name: newName.trim(),
        tickers, weights, start_date: startDate, end_date: endDate,
      });
      setPortfolios(prev => [p, ...prev]);
      setNewName("");
      setOpen(false);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number, e: React.MouseEvent) {
    e.stopPropagation();
    await api.deletePortfolio(id).catch(() => {});
    setPortfolios(prev => prev.filter(p => p.id !== id));
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs text-txt2 font-semibold uppercase tracking-wider">Saved Portfolios</div>

      {portfolios.length > 0 && (
        <div className="flex flex-col gap-1 max-h-40 overflow-y-auto">
          {portfolios.map(p => (
            <div key={p.id}
              onClick={() => onLoad(p)}
              className="flex items-center justify-between px-3 py-2 rounded-lg bg-card2 border border-border
                cursor-pointer hover:border-accent/50 transition-all group">
              <span className="text-xs font-semibold text-txt truncate">{p.name}</span>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="text-xs text-txt2">{p.tickers.length} stocks</span>
                <button onClick={(e) => remove(p.id, e)}
                  className="text-txt2 hover:text-neg opacity-0 group-hover:opacity-100 transition-all ml-1">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M18 6L6 18M6 6l12 12"/>
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {open ? (
        <div className="flex flex-col gap-2">
          <input
            value={newName}
            onChange={e => setNewName(e.target.value)}
            placeholder="Portfolio name…"
            onKeyDown={e => e.key === "Enter" && save()}
            className="text-sm w-full"
            autoFocus
          />
          {error && <p className="text-neg text-xs">{error}</p>}
          <div className="flex gap-1.5">
            <button onClick={save} disabled={saving || !newName.trim()}
              className="flex-1 py-1.5 rounded-lg text-xs font-bold text-white
                bg-gradient-to-r from-accent to-accent2
                disabled:opacity-40 hover:opacity-90 transition-all">
              {saving ? "Saving…" : "Save"}
            </button>
            <button onClick={() => { setOpen(false); setError(null); setNewName(""); }}
              className="px-3 py-1.5 rounded-lg border border-border text-xs text-txt2 hover:text-txt transition-all">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button onClick={() => setOpen(true)} disabled={!tickers.length}
          className="py-1.5 rounded-lg border border-border text-xs text-txt2
            hover:border-accent/50 hover:text-accent disabled:opacity-40 transition-all">
          + Save current
        </button>
      )}
    </div>
  );
}
