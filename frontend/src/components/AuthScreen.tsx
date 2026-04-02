import { useState } from "react";
import { api, User } from "../api";

type Props = {
  onAuthenticated: (user: User) => Promise<void> | void;
};

export default function AuthScreen({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const auth = mode === "signup"
        ? await api.signup({ email, password, name })
        : await api.login({ email, password });
      api.setToken(auth.access_token);
      await onAuthenticated(auth.user);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-bg text-txt flex items-center justify-center px-4">
      <div className="w-full max-w-5xl grid lg:grid-cols-[1.2fr_0.9fr] gap-6">
        <div className="bg-card border border-border rounded-3xl p-8 lg:p-10 flex flex-col justify-between">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border bg-card2 text-xs text-txt2 uppercase tracking-[0.2em]">
              Bayes
            </div>
            <h1 className="mt-6 text-4xl lg:text-5xl font-black leading-tight">
              One workspace for personal portfolios and club portfolios.
            </h1>
            <p className="mt-4 text-base text-txt2 max-w-xl leading-relaxed">
              Sign in to save named portfolios, keep separate trade logs, and come back to the same setup later without rebuilding your book from scratch.
            </p>
          </div>
          <div className="grid sm:grid-cols-3 gap-3 mt-8">
            {[
              ["Named portfolios", "Keep personal and institutional books separate."],
              ["Saved trade logs", "Track P&L and reload each portfolio later."],
              ["Analytics on demand", "Run factor, hedge, optimization, and backtests from the same place."],
            ].map(([title, body]) => (
              <div key={title} className="rounded-2xl border border-border bg-[#10101a] p-4">
                <div className="text-sm font-bold">{title}</div>
                <div className="text-sm text-txt2 mt-2 leading-relaxed">{body}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-card border border-border rounded-3xl p-8">
          <div className="flex rounded-xl overflow-hidden border border-border text-sm font-semibold mb-6">
            {(["login", "signup"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => {
                  setMode(value);
                  setError(null);
                }}
                className={`flex-1 py-3 transition-all ${mode === value ? "bg-gradient-to-r from-accent to-accent2 text-white" : "text-txt2 hover:text-txt"}`}
              >
                {value === "login" ? "Log In" : "Create Account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="flex flex-col gap-4">
            {mode === "signup" && (
              <div>
                <label className="block text-xs uppercase tracking-wider text-txt2 mb-2">Name</label>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Finance Club PM" />
              </div>
            )}
            <div>
              <label className="block text-xs uppercase tracking-wider text-txt2 mb-2">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-wider text-txt2 mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                required
              />
            </div>
            {error && <div className="rounded-xl border border-neg/30 bg-neg/10 px-4 py-3 text-sm text-neg">{error}</div>}
            <button
              type="submit"
              disabled={loading}
              className="mt-2 w-full py-3 rounded-xl font-bold text-sm text-white bg-gradient-to-r from-accent to-accent2 disabled:opacity-40"
            >
              {loading ? "Working..." : mode === "login" ? "Enter Workspace" : "Create Workspace"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
