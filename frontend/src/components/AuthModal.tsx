import { useState } from "react";
import { api, AuthUser } from "../api";
import { setAuth } from "../auth";

type Props = {
  onClose: () => void;
  onAuth: (user: AuthUser) => void;
};

export default function AuthModal({ onClose, onAuth }: Props) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [name, setName]         = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = mode === "signup"
        ? await api.signup({ email, password, name })
        : await api.login({ email, password });
      setAuth(res.token, res.user);
      onAuth(res.user);
      onClose();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-[#0d0d16] border border-border rounded-2xl w-full max-w-sm mx-4 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="text-accent">
              <path d="M2 20 C6 20, 6 4, 12 4 S18 20, 22 20" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" fill="none"/>
            </svg>
            <span className="font-bold text-txt">Bayes</span>
          </div>
          <button onClick={onClose} className="text-txt2 hover:text-txt transition-colors">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {/* Tab toggle */}
        <div className="flex border-b border-border">
          {(["login", "signup"] as const).map(m => (
            <button key={m} onClick={() => { setMode(m); setError(null); }}
              className={`flex-1 py-3 text-sm font-semibold transition-all ${
                mode === m
                  ? "text-txt border-b-2 border-accent"
                  : "text-txt2 hover:text-txt"
              }`}>
              {m === "login" ? "Sign in" : "Create account"}
            </button>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={submit} className="p-6 flex flex-col gap-4">
          {mode === "signup" && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs text-txt2 font-semibold">Name</label>
              <input
                value={name} onChange={e => setName(e.target.value)}
                placeholder="Your name"
                className="w-full px-3 py-2.5 bg-card2 border border-border rounded-xl text-sm text-txt
                  focus:outline-none focus:border-accent/60 transition-colors"
              />
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-txt2 font-semibold">Email</label>
            <input
              type="email" required
              value={email} onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full px-3 py-2.5 bg-card2 border border-border rounded-xl text-sm text-txt
                focus:outline-none focus:border-accent/60 transition-colors"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-txt2 font-semibold">Password</label>
            <input
              type="password" required minLength={6}
              value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3 py-2.5 bg-card2 border border-border rounded-xl text-sm text-txt
                focus:outline-none focus:border-accent/60 transition-colors"
            />
          </div>

          {error && (
            <div className="text-neg text-xs bg-neg/10 border border-neg/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button type="submit" disabled={loading}
            className="w-full py-2.5 rounded-xl font-bold text-sm text-white
              bg-gradient-to-r from-accent to-accent2
              disabled:opacity-40 disabled:cursor-not-allowed
              hover:opacity-90 active:scale-95 transition-all mt-1">
            {loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>

          <p className="text-center text-xs text-txt2">
            {mode === "login" ? "No account? " : "Already have one? "}
            <button type="button" onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(null); }}
              className="text-accent hover:underline font-semibold">
              {mode === "login" ? "Sign up" : "Sign in"}
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}
