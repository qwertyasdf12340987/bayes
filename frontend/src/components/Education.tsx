function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-bold text-txt border-b border-border pb-3">{title}</h2>
      {children}
    </div>
  );
}

function Card({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="bg-card border border-border rounded-2xl p-5">
      {title && <div className="font-semibold text-txt mb-2">{title}</div>}
      <div className="text-txt2 text-sm leading-relaxed">{children}</div>
    </div>
  );
}

function Formula({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-[#0d0d16] border border-border rounded-xl px-4 py-3 font-mono text-sm text-accent my-2 overflow-x-auto">
      {children}
    </div>
  );
}

function Term({ word, def }: { word: string; def: string }) {
  return (
    <div className="border-b border-border py-3 last:border-0">
      <span className="font-semibold text-txt text-sm">{word}</span>
      <span className="text-txt2 text-sm ml-2">— {def}</span>
    </div>
  );
}

const FACTORS = [
  { name: "Mkt-RF", label: "Market", color: "#7c6af7", desc: "Excess return of the market over the risk-free rate. Captures broad equity risk." },
  { name: "SMB", label: "Size", color: "#06b6d4", desc: "Small Minus Big. Long small-cap, short large-cap stocks. Captures the size premium." },
  { name: "HML", label: "Value", color: "#22c55e", desc: "High Minus Low. Long high book-to-market, short growth stocks. Captures the value premium." },
  { name: "RMW", label: "Profitability", color: "#f59e0b", desc: "Robust Minus Weak. Long profitable firms, short unprofitable. Captures the profitability premium." },
  { name: "CMA", label: "Investment", color: "#ec4899", desc: "Conservative Minus Aggressive. Long low-investment firms. Captures the investment premium." },
  { name: "Mom", label: "Momentum", color: "#a78bfa", desc: "Long recent winners, short recent losers. Captures the momentum anomaly." },
];

export default function Education() {
  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-10 pb-12">

      {/* Hero */}
      <div className="text-center pt-4">
        <h1 className="text-3xl font-extrabold text-txt mb-2">Factor-Neutral Portfolio Construction</h1>
        <p className="text-txt2 max-w-xl mx-auto text-sm leading-relaxed">
          A concise guide to understanding systematic risk factors, how they affect your returns,
          and how to build a portfolio that isolates alpha from unwanted exposures.
        </p>
      </div>

      {/* 1. Risk factors */}
      <Section title="1. What Are Risk Factors?">
        <Card>
          Traditional finance says stock returns come from two sources:{" "}
          <span className="text-txt font-semibold">systematic risk</span> (broad market forces you can't diversify away)
          and <span className="text-txt font-semibold">idiosyncratic risk</span> (company-specific events you can diversify away).
          <br /><br />
          Fama & French showed that beyond the market, additional <em>systematic</em> factors explain a large
          portion of portfolio returns — and each factor commands a long-run risk premium because it is
          correlated with bad economic times.
        </Card>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {FACTORS.map(f => (
            <div key={f.name} className="bg-card border border-border rounded-2xl p-4 flex gap-3">
              <div className="w-2 rounded-full shrink-0" style={{ backgroundColor: f.color }} />
              <div>
                <div className="font-bold text-txt text-sm">
                  {f.name} <span className="text-txt2 font-normal">— {f.label}</span>
                </div>
                <div className="text-txt2 text-xs leading-relaxed mt-1">{f.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* 2. The factor model */}
      <Section title="2. The Fama-French Factor Model">
        <Card>
          The model decomposes your portfolio's excess return into factor exposures (betas) plus alpha:
        </Card>
        <Formula>
          R_p − R_f = α + β₁·Mkt-RF + β₂·SMB + β₃·HML + β₄·RMW + β₅·CMA + β₆·Mom + ε
        </Formula>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Card title="Alpha (α)">
            Return unexplained by factors. Positive alpha is evidence of stock-picking skill or
            exposure to a risk not captured by the model. It is <em>very</em> hard to sustain.
          </Card>
          <Card title="Beta (β)">
            Sensitivity of your portfolio to each factor. A market beta of 1.3 means your
            portfolio moves 1.3% for every 1% move in the market.
          </Card>
          <Card title="R²">
            The fraction of return variance explained by the model. A high R² (≥ 0.90) means
            the model captures most of your portfolio's risk drivers.
          </Card>
        </div>
        <Card title="How Bayes estimates these">
          Bayes downloads monthly returns for your portfolio and the six factors, then runs an
          OLS regression with <span className="text-txt font-semibold">HC3 robust standard errors</span>{" "}
          to correct for heteroskedasticity. Stars (*, **, ***) indicate significance at the 10%, 5%, and 1% levels.
        </Card>
      </Section>

      {/* 3. Factor-neutral construction */}
      <Section title="3. Factor-Neutral Portfolio Construction">
        <Card>
          A <span className="text-txt font-semibold">factor-neutral portfolio</span> has zero (or near-zero)
          beta to one or more systematic factors. The goal is to isolate your return to alpha alone —
          removing exposure to macro risks you didn't intend to take.
          <br /><br />
          This is the foundation of <em>market-neutral</em> and <em>long-short equity</em> hedge fund strategies.
        </Card>

        <div className="bg-card border border-border rounded-2xl p-5">
          <div className="font-semibold text-txt mb-4">The three-step process</div>
          <div className="flex flex-col gap-4">
            {[
              ["1. Measure", "Run the factor regression on your current portfolio to identify which factors you are significantly exposed to (|beta| > 0.15, p < 0.10)."],
              ["2. Hedge", "Take offsetting positions in ETFs that are highly loaded on each unwanted factor. For example, a high market beta is hedged by shorting SPY; small-cap tilt by shorting IWM."],
              ["3. Verify", "Re-run the regression on the hedged portfolio. Factor betas should be near zero. The remaining return is closer to pure alpha."],
            ].map(([step, desc]) => (
              <div key={step as string} className="flex gap-3">
                <div className="shrink-0 w-6 h-6 rounded-full bg-accent/20 text-accent text-xs font-bold flex items-center justify-center">
                  {(step as string)[0]}
                </div>
                <div>
                  <div className="font-semibold text-txt text-sm">{step}</div>
                  <div className="text-txt2 text-sm mt-0.5 leading-relaxed">{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <Card title="Hedge ETF mapping (Bayes defaults)">
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 mt-1">
            {[
              ["Market (β_mkt)", "SPY"],
              ["Size (SMB)", "IWM"],
              ["Value (HML)", "IVE"],
              ["Quality (RMW)", "QUAL"],
              ["Low-vol (CMA)", "USMV"],
              ["Momentum", "MTUM"],
              ["Each sector", "XLK / XLV / XLF …"],
            ].map(([f, etf]) => (
              <div key={f} className="flex justify-between text-xs">
                <span className="text-txt2">{f}</span>
                <span className="font-mono text-accent">{etf}</span>
              </div>
            ))}
          </div>
        </Card>
      </Section>

      {/* 4. Mean-variance optimization */}
      <Section title="4. Mean-Variance Optimization">
        <Card>
          Markowitz (1952) showed that for a given set of expected returns and a covariance matrix,
          there exists a <span className="text-txt font-semibold">frontier</span> of portfolios that
          maximize expected return for each level of risk. The portfolio with the best risk-adjusted
          return (highest Sharpe ratio) is the <em>tangency portfolio</em>.
        </Card>
        <Formula>
          maximize  Sharpe(w) = (w·μ − r_f) / √(w·Σ·wᵀ)
          {"\n"}
          subject to  Σwᵢ = 1,  wᵢ ≥ 0  (long-only)
        </Formula>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Card title="Inputs">
            <ul className="list-disc list-inside space-y-1">
              <li><span className="text-txt font-semibold">μ</span> — your predicted annualized returns (entered in the Optimizer tab)</li>
              <li><span className="text-txt font-semibold">Σ</span> — annualized covariance matrix from historical returns</li>
              <li><span className="text-txt font-semibold">r_f</span> — risk-free rate (your assumption)</li>
            </ul>
          </Card>
          <Card title="Output">
            Optimal weight vector <span className="font-mono text-accent">w*</span> that maximizes Sharpe.
            Bayes then shows you the dollar BUY/SELL trades needed to move from your current weights to optimal.
          </Card>
        </div>
        <Card title="Important caveat">
          Mean-variance optimization is highly sensitive to the expected return inputs (μ).
          Small changes in predicted returns can cause large swings in optimal weights.
          Always treat the output as a <em>starting point</em> for discussion, not a trading signal.
          Consider using a Black-Litterman prior or shrinkage estimator for more robust results.
        </Card>
      </Section>

      {/* 5. Key metrics */}
      <Section title="5. Key Performance Metrics">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Card title="Sharpe Ratio">
            (Return − Risk-free rate) / Volatility. Measures return per unit of total risk.
            A ratio above 1.0 is generally considered good. Annualised by multiplying by √12 for monthly data.
          </Card>
          <Card title="Sortino Ratio">
            Like Sharpe, but only penalises <em>downside</em> volatility. Better for strategies
            with asymmetric return distributions. Higher is better.
          </Card>
          <Card title="Max Drawdown">
            Largest peak-to-trough decline in portfolio value. Measures the worst historical
            loss an investor would have experienced. More intuitive than volatility as a risk measure.
          </Card>
          <Card title="Calmar Ratio">
            Annualised return / |Max Drawdown|. Measures return per unit of drawdown risk.
            Common in hedge fund and CTA analysis.
          </Card>
          <Card title="VaR (95%)">
            Value at Risk: the loss not exceeded in 95% of months. A VaR of −5% means
            in a typical bad month you lose no more than 5%. Based on historical simulation.
          </Card>
          <Card title="CVaR (95%)">
            Conditional VaR / Expected Shortfall: the average loss in the worst 5% of months.
            More conservative than VaR; captures tail risk better.
          </Card>
        </div>
      </Section>

      {/* 6. Glossary */}
      <Section title="6. Glossary">
        <div className="bg-card border border-border rounded-2xl p-5">
          <Term word="Alpha" def="Return unexplained by factor exposures. The 'skill' component of a manager's performance." />
          <Term word="Beta" def="Sensitivity of a portfolio to a risk factor. Market beta = 1 means the portfolio moves 1-for-1 with the market." />
          <Term word="Covariance matrix" def="Describes how each pair of stocks moves together. The fundamental input to portfolio risk calculations." />
          <Term word="Factor exposure" def="How much of your return variation is explained by a systematic factor. Measured by the regression beta." />
          <Term word="HC3 robust errors" def="Heteroskedasticity-consistent standard errors. Correct t-statistics when return variances are not constant over time." />
          <Term word="Long-short" def="Simultaneously holding long positions in some assets and short positions in others, reducing net market exposure." />
          <Term word="Marginal risk contribution" def="The fraction of total portfolio variance attributable to each stock. Sums to 100%." />
          <Term word="Market-neutral" def="A portfolio with near-zero market beta. Returns are driven by stock selection, not market direction." />
          <Term word="Risk premium" def="The extra return investors demand for bearing a systematic risk. Factors earn premiums because they are painful to hold in bad times." />
          <Term word="Sharpe ratio" def="(Return − Risk-free) / Volatility. The standard measure of risk-adjusted performance." />
          <Term word="Tangency portfolio" def="The portfolio on the efficient frontier with the highest Sharpe ratio." />
        </div>
      </Section>

      <p className="text-xs text-txt2 text-center">
        This platform is for educational and research purposes only. Nothing here constitutes investment advice.
      </p>
    </div>
  );
}
