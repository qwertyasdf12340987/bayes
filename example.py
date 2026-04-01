"""
example.py
----------
Demonstrates how to use PortfolioAnalyzer.

Run:
    python example.py
"""

from portfolio_analyzer import PortfolioAnalyzer

# -------------------------------------------------------------------
# Define your portfolio
# -------------------------------------------------------------------
# tickers : list of stock symbols
# weights : dollar amounts or percentage weights (will be normalised)
#           omit for equal-weight

tickers = ["AAPL", "MSFT", "NVDA", "JPM", "XOM"]
weights = [0.25, 0.25, 0.20, 0.15, 0.15]

# -------------------------------------------------------------------
# Run full analysis (last 5 years, monthly)
# -------------------------------------------------------------------
analyzer = PortfolioAnalyzer(
    tickers=tickers,
    weights=weights,
    start_date="2019-01-01",
    end_date="2024-12-31",
    frequency="monthly",      # 'monthly' recommended for factor models
)

analyzer.run(
    factor_model=True,        # FF5 + Momentum regression
    industry_model=True,      # Sector ETF regression
    covariance=True,          # Covariance / correlation matrix
    plots=True,               # Display charts
    per_stock=True,           # Factor loadings for each stock individually
)

# -------------------------------------------------------------------
# Access individual results programmatically
# -------------------------------------------------------------------

# Factor regression results dict
ff_results = analyzer.factor_analysis(include_momentum=True, per_stock=True)

# Portfolio-level betas
port_betas = ff_results["portfolio"]["betas"]
print("\nPortfolio betas:", port_betas)

# Per-stock betas
for ticker in tickers:
    stock_betas = ff_results["stocks"][ticker]["betas"]
    print(f"{ticker} betas: {stock_betas}")

# Annualised covariance matrix (as a DataFrame)
cov = analyzer.covariance_matrix(annualized=True)
print("\nCovariance matrix:\n", cov)

# Correlation matrix
corr = analyzer.correlation_matrix()
print("\nCorrelation matrix:\n", corr.round(3))

# Portfolio volatility
print(f"\nPortfolio volatility (ann.): {analyzer.portfolio_volatility()*100:.2f}%")

# Risk contributions
print("\nRisk contributions:")
print(analyzer.marginal_risk_contributions().map("{:.1%}".format))
