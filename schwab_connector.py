"""
schwab_connector.py
--------------------
Fetches portfolio positions from Charles Schwab via schwab-py.

First-time setup:
  1. Go to https://developer.schwab.com and create an Individual app.
  2. Set the callback URL to exactly:  https://127.0.0.1:8182
  3. Copy your App Key (Client ID) and App Secret.
  4. The first time you click "Connect" in the web app, a browser window
     will open for you to log in to Schwab and authorise the app.
  5. After authorisation, your token is saved to schwab_token.json.
     Future connections use this saved token automatically.
"""

from typing import List, Tuple


def get_schwab_portfolio(
    client_id: str,
    client_secret: str,
    token_path: str = "schwab_token.json",
) -> Tuple[List[str], List[float]]:
    """
    Authenticate with Schwab and return all equity positions as
    (tickers, market_values).

    Parameters
    ----------
    client_id     : Your Schwab App Key (Client ID) from developer.schwab.com
    client_secret : Your Schwab App Secret
    token_path    : Where to save/load the OAuth token (default: schwab_token.json)

    Returns
    -------
    tickers       : List of ticker symbols (e.g. ['AAPL', 'MSFT'])
    market_values : Corresponding market values in USD (used as portfolio weights)
    """
    try:
        import schwab
    except ImportError:
        raise ImportError(
            "schwab-py is not installed.\n"
            "Fix: run  python3 -m pip install schwab-py  in Terminal, then try again."
        )

    client = schwab.auth.easy_client(
        api_key=client_id,
        app_secret=client_secret,
        callback_url="https://127.0.0.1:8182",
        token_path=token_path,
    )

    resp = client.get_accounts(fields=[client.Account.Fields.POSITIONS])
    resp.raise_for_status()
    data = resp.json()

    tickers:       List[str]   = []
    market_values: List[float] = []

    for account in data:
        positions = account.get("securitiesAccount", {}).get("positions", [])
        for pos in positions:
            instrument   = pos.get("instrument", {})
            asset_type   = instrument.get("assetType", "")
            symbol       = instrument.get("symbol", "").strip()
            market_value = float(pos.get("marketValue", 0))

            # Equity long positions only — skip options, bonds, cash, short positions
            long_qty = float(pos.get("longQuantity", 0))
            if asset_type == "EQUITY" and symbol and market_value > 0 and long_qty > 0:
                tickers.append(symbol)
                market_values.append(market_value)

    if not tickers:
        raise ValueError(
            "No equity positions found in your Schwab account.\n"
            "Make sure the account has stock holdings and try again."
        )

    return tickers, market_values
