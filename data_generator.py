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

    return df_assets, df_prices, df_transactions


# ==========================================
# SEC CORPORATE FILINGS GENERATION
# ==========================================

SEC_SECTOR_COMPANIES = {
    "Technology": [
        ("AAPL", "Apple Inc.", "10001", "Consumer Electronics"),
        ("MSFT", "Microsoft Corp.", "10002", "Software Infrastructure"),
        ("GOOGL", "Alphabet Inc.", "10003", "Internet Content"),
        ("NVDA", "NVIDIA Corp.", "10004", "Semiconductors"),
        ("AMZN", "Amazon.com Inc.", "10005", "E-Commerce/Cloud")
    ],
    "Healthcare": [
        ("JNJ", "Johnson & Johnson", "20001", "Drug Manufacturers"),
        ("PFE", "Pfizer Inc.", "20002", "Drug Manufacturers"),
        ("LLY", "Eli Lilly & Co.", "20003", "Drug Manufacturers"),
        ("UNH", "UnitedHealth Group Inc.", "20004", "Healthcare Plans"),
        ("MRK", "Merck & Co. Inc.", "20005", "Drug Manufacturers")
    ],
    "Energy": [
        ("XOM", "Exxon Mobil Corp.", "30001", "Oil & Gas Integrated"),
        ("CVX", "Chevron Corp.", "30002", "Oil & Gas Integrated"),
        ("BP", "BP plc", "30003", "Oil & Gas Integrated"),
        ("COP", "ConocoPhillips", "30004", "Oil & Gas E&P"),
        ("TTE", "TotalEnergies SE", "30005", "Oil & Gas Integrated")
    ],
    "SaaS": [
        ("CRM", "Salesforce Inc.", "40001", "Software Application"),
        ("NOW", "ServiceNow Inc.", "40002", "Software Application"),
        ("WDAY", "Workday Inc.", "40003", "Software Application"),
        ("ADBE", "Adobe Inc.", "40004", "Software Application"),
        ("SNOW", "Snowflake Inc.", "40005", "Software Application")
    ],
    "Agriculture": [
        ("DE", "Deere & Co.", "50001", "Farm & Heavy Construction Machinery"),
        ("CTVA", "Corteva Inc.", "50002", "Agricultural Inputs"),
        ("BG", "Bunge Global SA", "50003", "Agricultural Inputs"),
        ("ADM", "Archer-Daniels-Midland Co.", "50004", "Agricultural Inputs"),
        ("FMC", "FMC Corp.", "50005", "Agricultural Inputs")
    ],
    "Automotive": [
        ("TSLA", "Tesla Inc.", "60001", "Auto Manufacturers"),
        ("F", "Ford Motor Co.", "60002", "Auto Manufacturers"),
        ("GM", "General Motors Co.", "60003", "Auto Manufacturers"),
        ("TM", "Toyota Motor Corp.", "60004", "Auto Manufacturers"),
        ("HMC", "Honda Motor Co. Ltd.", "60005", "Auto Manufacturers")
    ],
    "Banking": [
        ("JPM", "JPMorgan Chase & Co.", "70001", "Banks Diversified"),
        ("BAC", "Bank of America Corp.", "70002", "Banks Diversified"),
        ("WFC", "Wells Fargo & Co.", "70003", "Banks Diversified"),
        ("C", "Citigroup Inc.", "70004", "Banks Diversified"),
        ("MS", "Morgan Stanley", "70005", "Capital Markets")
    ],
    "Business/Conglomerate": [
        ("HON", "Honeywell International Inc.", "80001", "Conglomerates"),
        ("MMM", "3M Company", "80002", "Conglomerates"),
        ("GE", "General Electric Co.", "80003", "Conglomerates"),
        ("CAT", "Caterpillar Inc.", "80004", "Farm & Heavy Construction Machinery"),
        ("EMR", "Emerson Electric Co.", "80005", "Industrial Machinery")
    ],
    "Cannabis": [
        ("TLRY", "Tilray Brands Inc.", "90001", "Drug Manufacturers - Specialty"),
        ("CGC", "Canopy Growth Corp.", "90002", "Drug Manufacturers - Specialty"),
        ("CRON", "Cronos Group Inc.", "90003", "Drug Manufacturers - Specialty"),
        ("ACB", "Aurora Cannabis Inc.", "90004", "Drug Manufacturers - Specialty"),
        ("CURLF", "Curaleaf Holdings Inc.", "90005", "Drug Manufacturers - Specialty")
    ],
    "Entertainment": [
        ("DIS", "The Walt Disney Co.", "95001", "Entertainment"),
        ("NFLX", "Netflix Inc.", "95002", "Entertainment"),
        ("WBD", "Warner Bros. Discovery Inc.", "95003", "Entertainment"),
        ("SONY", "Sony Group Corp.", "95004", "Entertainment"),
        ("CMCSA", "Comcast Corp.", "95005", "Entertainment")
    ]
}

def generate_mock_sec_filings():
    """Generates standard annual (10-K) and quarterly (10-Q) filing facts with anomalies."""
    np.random.seed(42)
    filings = []
    
    # Financial profile configs per sector to keep mock values realistic
    sector_profiles = {
        "Technology": {"base_rev": 12000000000, "gross_margin": 0.45, "rd_ratio": 0.12, "sga_ratio": 0.15, "debt_ratio": 0.35, "asset_base": 80000000000},
        "Healthcare": {"base_rev": 8000000000, "gross_margin": 0.60, "rd_ratio": 0.18, "sga_ratio": 0.25, "debt_ratio": 0.45, "asset_base": 90000000000},
        "Energy": {"base_rev": 15000000000, "gross_margin": 0.22, "rd_ratio": 0.01, "sga_ratio": 0.05, "debt_ratio": 0.50, "asset_base": 120000000000},
        "SaaS": {"base_rev": 1500000000, "gross_margin": 0.75, "rd_ratio": 0.25, "sga_ratio": 0.35, "debt_ratio": 0.20, "asset_base": 15000000000},
        "Agriculture": {"base_rev": 4000000000, "gross_margin": 0.25, "rd_ratio": 0.04, "sga_ratio": 0.10, "debt_ratio": 0.55, "asset_base": 30000000000},
        "Automotive": {"base_rev": 9000000000, "gross_margin": 0.18, "rd_ratio": 0.06, "sga_ratio": 0.08, "debt_ratio": 0.70, "asset_base": 100000000000},
        "Banking": {"base_rev": 10000000000, "gross_margin": 0.85, "rd_ratio": 0.00, "sga_ratio": 0.40, "debt_ratio": 0.88, "asset_base": 500000000000},
        "Business/Conglomerate": {"base_rev": 5000000000, "gross_margin": 0.28, "rd_ratio": 0.05, "sga_ratio": 0.12, "debt_ratio": 0.55, "asset_base": 45000000000},
        "Cannabis": {"base_rev": 120000000, "gross_margin": 0.35, "rd_ratio": 0.02, "sga_ratio": 0.45, "debt_ratio": 0.60, "asset_base": 1200000000},
        "Entertainment": {"base_rev": 6000000000, "gross_margin": 0.38, "rd_ratio": 0.04, "sga_ratio": 0.20, "debt_ratio": 0.65, "asset_base": 75000000000}
    }
    
    periods = [
        # (Year, Quarter, Form, date_offset_days)
        (2023, "Q1", "10-Q", "2023-05-10"),
        (2023, "Q2", "10-Q", "2023-08-08"),
        (2023, "Q3", "10-Q", "2023-11-09"),
        (2023, "FY", "10-K", "2024-01-30"),
        (2024, "Q1", "10-Q", "2024-05-12"),
        (2024, "Q2", "10-Q", "2024-08-10"),
        (2024, "Q3", "10-Q", "2024-11-07"),
        (2024, "FY", "10-K", "2025-02-02"),
        (2025, "Q1", "10-Q", "2025-05-14"),
        (2025, "Q2", "10-Q", "2025-08-09"),
        (2025, "Q3", "10-Q", "2025-11-08"),
        (2025, "FY", "10-K", "2026-02-04"),
        (2026, "Q1", "10-Q", "2026-05-10"),
        (2026, "Q2", "10-Q", "2026-08-07")
    ]
    
    for sector, companies in SEC_SECTOR_COMPANIES.items():
        prof = sector_profiles[sector]
        
        for idx, (ticker, name, cik, industry) in enumerate(companies):
            # Ticker specific adjustment multiplier to make companies distinct
            company_mult = 0.7 + (idx * 0.15) # 0.7, 0.85, 1.0, 1.15, 1.3
            
            # High profile growth multipliers (e.g. NVIDIA growth)
            growth_trend = 1.05
            if ticker == "NVDA":
                growth_trend = 1.65 # massive revenue growth!
            elif ticker == "TSLA":
                growth_trend = 1.10
            elif ticker == "TLRY":
                growth_trend = 0.95 # declining/flat
                
            for year, quarter, form, filing_date in periods:
                # Compound growth based on years
                year_diff = year - 2023
                growth_factor = (growth_trend ** year_diff) * company_mult
                
                # Seasonality factor for quarters vs full year
                period_scale = 1.0 if quarter == "FY" else 0.25
                
                # Baseline metrics
                revenue = prof["base_rev"] * growth_factor * period_scale * np.random.uniform(0.95, 1.05)
                cost_of_rev = revenue * (1 - prof["gross_margin"]) * np.random.uniform(0.98, 1.02)
                gross_profit = revenue - cost_of_rev
                
                rd = revenue * prof["rd_ratio"] * np.random.uniform(0.96, 1.04)
                sga = revenue * prof["sga_ratio"] * np.random.uniform(0.96, 1.04)
                
                # Net income
                operating_income = gross_profit - rd - sga
                interest_taxes = revenue * 0.05 * np.random.uniform(0.9, 1.1)
                net_income = operating_income - interest_taxes
                
                # Balance Sheet
                assets = prof["asset_base"] * growth_factor * (1.0 + (year_diff * 0.08)) * np.random.uniform(0.97, 1.03)
                liabilities = assets * prof["debt_ratio"] * np.random.uniform(0.97, 1.03)
                equity = assets - liabilities
                
                # Cash Flow
                depreciation = revenue * 0.06
                operating_cash_flow = net_income * 1.15 + depreciation
                capex = revenue * (0.05 if sector == "SaaS" else (0.18 if sector == "Energy" else 0.08))
                free_cash_flow = operating_cash_flow - capex
                
                # ==========================================
                # INJECT DATA QUALITY ANOMALIES
                # ==========================================
                
                # Anomaly A: Unbalanced Balance sheet (Pfizer PFE FY 2024 10-K)
                if ticker == "PFE" and year == 2024 and quarter == "FY":
                    # Offset assets from liabilities + equity by +50 million
                    equity = assets - liabilities + 50000000.0
                    
                # Anomaly B: Gross Profit mismatch (Disney DIS Q2 2025 10-Q)
                if ticker == "DIS" and year == 2025 and quarter == "Q2":
                    gross_profit = revenue - cost_of_rev - 12000000.0
                    
                # Anomaly C: Negative Assets (Cronos CRON Q3 2025 10-Q)
                if ticker == "CRON" and year == 2025 and quarter == "Q3":
                    assets = -500000.0
                    
                # Anomaly D: Net Income > Revenue (Tilray TLRY Q1 2024 10-Q)
                if ticker == "TLRY" and year == 2024 and quarter == "Q1":
                    net_income = revenue * 1.5
                    
                # Compile records
                line_items = {
                    "Revenue": revenue,
                    "CostOfRevenue": cost_of_rev,
                    "GrossProfit": gross_profit,
                    "ResearchDevelopment": rd,
                    "SellingGeneralAdmin": sga,
                    "NetIncome": net_income,
                    "TotalAssets": assets,
                    "TotalLiabilities": liabilities,
                    "TotalEquity": equity,
                    "OperatingCashFlow": operating_cash_flow,
                    "CapitalExpenditures": capex,
                    "FreeCashFlow": free_cash_flow
                }
                
                for item, val in line_items.items():
                    filings.append({
                        "ticker": ticker,
                        "company_name": name,
                        "form": form,
                        "fiscal_year": int(year),
                        "fiscal_quarter": quarter,
                        "line_item": item,
                        "value": float(val),
                        "filing_date": filing_date
                    })
                    
    return pd.DataFrame(filings)


if __name__ == "__main__":
    assets, prices, txs = generate_mock_financial_data()
    print(f"Generated {len(assets)} assets.")
    print(f"Generated {len(prices)} price records.")
    print(f"Generated {len(txs)} transactions.")
    
    df_sec = generate_mock_sec_filings()
    print(f"Generated {len(df_sec)} SEC filing records.")
    print(df_sec.head())

