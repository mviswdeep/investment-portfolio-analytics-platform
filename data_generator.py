import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Constants for Mock Tickers
TICKERS = {
    # Ticker: (Name, Asset Class, Sector, Initial Price, Drift, Volatility)
    "AAPL": ("Apple Inc.", "Equity", "Technology", 175.0, 0.15, 0.20),
    "MSFT": ("Microsoft Corp.", "Equity", "Technology", 370.0, 0.18, 0.18),
    "GOOGL": ("Alphabet Inc.", "Equity", "Communication", 140.0, 0.12, 0.22),
    "NVDA": ("NVIDIA Corp.", "Equity", "Technology", 480.0, 0.55, 0.35),
    "AMZN": ("Amazon.com Inc.", "Equity", "Consumer Cyclical", 150.0, 0.14, 0.25),
    "JNJ": ("Johnson & Johnson", "Equity", "Healthcare", 160.0, 0.05, 0.12),
    "PG": ("Procter & Gamble Co.", "Equity", "Consumer Defensive", 150.0, 0.06, 0.11),
    "XOM": ("Exxon Mobil Corp.", "Equity", "Energy", 100.0, 0.04, 0.20),
    "BTC": ("Bitcoin", "Cryptocurrency", "Cryptocurrency", 42000.0, 0.40, 0.50),
    "ETH": ("Ethereum", "Cryptocurrency", "Cryptocurrency", 2200.0, 0.35, 0.55),
    "SOL": ("Solana", "Cryptocurrency", "Cryptocurrency", 100.0, 0.60, 0.70),
    "SPY": ("S&P 500 ETF Trust", "Equity (Index)", "Benchmark", 470.0, 0.10, 0.14)
}

PROVIDERS = {
    "Yahoo Finance": "REST API",
    "Alpha Vantage": "REST API",
    "CoinGecko": "REST API",
    "SEC EDGAR": "XML Filings",
    "CSV Ingestion": "Local File System"
}

def generate_gbm_prices(ticker, start_date, end_date):
    """Generates stock prices using Geometric Brownian Motion (GBM)."""
    name, asset_class, sector, s0, drift, vol = TICKERS[ticker]
    
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    n = len(dates)
    
    # Time delta in years
    dt = 1 / 365.0
    
    # GBM formula: S(t) = S(0)*exp((drift - 0.5*vol^2)*t + vol*W(t))
    # Brownian increments
    dW = np.random.normal(0, np.sqrt(dt), n - 1)
    W = np.cumsum(dW)
    W = np.insert(W, 0, 0) # Start at W(0) = 0
    
    t = np.linspace(0, n*dt, n)
    prices = s0 * np.exp((drift - 0.5 * vol**2) * t + vol * W)
    
    # Volume modeling: randomized with correlation to returns
    avg_vol = 1000000 if asset_class == "Equity" else 50000000
    if ticker == "SPY":
        avg_vol = 70000000
    volumes = np.random.lognormal(np.log(avg_vol), 0.4, n)
    
    df = pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'ticker': ticker,
        'close_price': prices,
        'volume': volumes
    })
    return df

def generate_mock_financial_data(start_date="2024-01-01", end_date="2026-06-30"):
    """Generates clean and anomalies-injected datasets representing raw API feeds."""
    np.random.seed(42) # Reconstructable data
    
    # 1. Asset Metadata DataFrame
    assets_data = []
    for ticker, info in TICKERS.items():
        provider = "CoinGecko" if info[1] == "Cryptocurrency" else "Alpha Vantage"
        assets_data.append({
            'ticker': ticker,
            'name': info[0],
            'asset_class': info[1],
            'sector': info[2],
            'provider': provider
        })
    df_assets = pd.DataFrame(assets_data)

    # 2. Historical Prices DataFrame
    price_dfs = []
    for ticker in TICKERS.keys():
        df_ticker = generate_gbm_prices(ticker, start_date, end_date)
        # Assign provider
        info = TICKERS[ticker]
        df_ticker['provider'] = "CoinGecko" if info[1] == "Cryptocurrency" else "Yahoo Finance"
        if ticker == "SPY":
            df_ticker['provider'] = "Alpha Vantage"
        price_dfs.append(df_ticker)
    
    df_prices = pd.concat(price_dfs, ignore_index=True)

    # 3. Inject Anomalies in Prices (for ETL Data Quality Checks)
    # Target some specific indexes to mutate
    total_price_rows = len(df_prices)
    
    # Anomaly A: Extreme Spike (Fat-Finger Error) - NVDA price spiked by 10x on a single day
    nvda_idx = df_prices[(df_prices['ticker'] == 'NVDA') & (df_prices['date'] == '2025-05-15')].index
    if not nvda_idx.empty:
        df_prices.loc[nvda_idx, 'close_price'] *= 10.0
        
    # Anomaly B: Negative Price (System Glitch) - AAPL price is negative on a day
    aapl_idx = df_prices[(df_prices['ticker'] == 'AAPL') & (df_prices['date'] == '2024-08-20')].index
    if not aapl_idx.empty:
        df_prices.loc[aapl_idx, 'close_price'] = -150.0

    # Anomaly C: Null/NaN values - PG and SOL close price is missing on a few dates
    pg_sol_idx = df_prices[((df_prices['ticker'] == 'PG') & (df_prices['date'] == '2025-03-10')) | 
                           ((df_prices['ticker'] == 'SOL') & (df_prices['date'] == '2026-01-12'))].index
    if not pg_sol_idx.empty:
        df_prices.loc[pg_sol_idx, 'close_price'] = np.nan

    # 4. Generate Mock Transaction History
    # We will model three portfolios: Tech Growth, Crypto Venture, and Balanced Retirement
    portfolios = {
        "Tech Growth Portfolio": [
            ("AAPL", 150, "2024-01-05"), ("MSFT", 80, "2024-01-05"), 
            ("GOOGL", 180, "2024-01-05"), ("NVDA", 50, "2024-01-05"), 
            ("AMZN", 120, "2024-01-05"),
            # Rebalancing
            ("NVDA", -15, "2025-06-10"), ("MSFT", 20, "2025-06-10"),
            ("AAPL", 10, "2026-02-15"), ("GOOGL", -30, "2026-02-15")
        ],
        "Crypto Venture Portfolio": [
            ("BTC", 2, "2024-02-10"), ("ETH", 25, "2024-02-10"),
            ("SOL", 250, "2024-02-10"),
            # Rebalancing
            ("SOL", -100, "2025-09-20"), ("BTC", 0.5, "2025-09-20"),
            ("ETH", -5, "2026-04-18"), ("SOL", 150, "2026-04-18")
        ],
        "Balanced Retirement Portfolio": [
            ("AAPL", 50, "2024-01-15"), ("MSFT", 30, "2024-01-15"),
            ("JNJ", 100, "2024-01-15"), ("PG", 120, "2024-01-15"),
            ("XOM", 150, "2024-01-15"), ("BTC", 0.3, "2024-01-15"),
            # Periodic saving additions
            ("JNJ", 10, "2025-01-15"), ("PG", 10, "2025-01-15"),
            ("XOM", 15, "2025-01-15"), ("MSFT", 5, "2025-01-15")
        ]
    }
    
    transactions = []
    tx_counter = 10001
    
    for port_name, tx_list in portfolios.items():
        for ticker, qty, tx_date in tx_list:
            tx_type = "BUY" if qty > 0 else "SELL"
            abs_qty = abs(qty)
            
            # Fetch price on transaction date
            p_row = df_prices[(df_prices['ticker'] == ticker) & (df_prices['date'] == tx_date)]
            if not p_row.empty:
                # If there's an anomaly or nan price, fallback to initial price
                price = p_row.iloc[0]['close_price']
                if pd.isna(price) or price <= 0:
                    price = TICKERS[ticker][3]
            else:
                price = TICKERS[ticker][3]
            
            # Add transaction
            transactions.append({
                "transaction_id": f"TX-{tx_counter}",
                "portfolio_name": port_name,
                "ticker": ticker,
                "transaction_type": tx_type,
                "quantity": abs_qty,
                "price": price,
                "transaction_date": tx_date,
                "provider": "CSV Ingestion" if port_name == "Balanced Retirement Portfolio" else "SEC EDGAR"
            })
            tx_counter += 1

    df_transactions = pd.DataFrame(transactions)

    # 5. Inject Transaction Anomalies
    # Anomaly D: Transaction with quantity <= 0 (Invalid data input)
    tx_bad_qty = {
        "transaction_id": f"TX-{tx_counter}",
        "portfolio_name": "Tech Growth Portfolio",
        "ticker": "AAPL",
        "transaction_type": "BUY",
        "quantity": -5.0, # Negative quantity
        "price": 180.0,
        "transaction_date": "2025-03-05",
        "provider": "SEC EDGAR"
    }
    df_transactions = pd.concat([df_transactions, pd.DataFrame([tx_bad_qty])], ignore_index=True)
    tx_counter += 1
    
    # Anomaly E: Transaction with price is null
    tx_null_price = {
        "transaction_id": f"TX-{tx_counter}",
        "portfolio_name": "Crypto Venture Portfolio",
        "ticker": "BTC",
        "transaction_type": "SELL",
        "quantity": 0.1,
        "price": np.nan, # Missing price
        "transaction_date": "2025-11-12",
        "provider": "CoinGecko"
    }
    df_transactions = pd.concat([df_transactions, pd.DataFrame([tx_null_price])], ignore_index=True)

    return df_assets, df_prices, df_transactions

if __name__ == "__main__":
    assets, prices, txs = generate_mock_financial_data()
    print(f"Generated {len(assets)} assets.")
    print(f"Generated {len(prices)} price records with anomalies.")
    print(f"Generated {len(txs)} transactions with anomalies.")
    print(df_prices[df_prices['close_price'].isna() | (df_prices['close_price'] < 0)])
