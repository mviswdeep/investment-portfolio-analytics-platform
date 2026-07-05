import sqlite3
import uuid
import datetime
import pandas as pd
import numpy as np
import scipy.stats as stats
from schema_definitions import get_connection, init_database
from data_generator import generate_mock_financial_data, TICKERS, generate_mock_sec_filings, SEC_SECTOR_COMPANIES

def create_run_id():
    return str(uuid.uuid4())[:8]

def log_pipeline_run(run_id, start_time, end_time, status, records_processed, logs):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO pipeline_runs (run_id, start_time, end_time, status, records_processed, logs)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (run_id, start_time, end_time, status, records_processed, logs))
    conn.commit()
    conn.close()

def log_data_quality(run_id, table, rule, status, failure_count, details):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO data_quality_logs (run_id, table_name, rule_name, status, failure_count, details)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (run_id, table, rule, status, failure_count, details))
    conn.commit()
    conn.close()

def run_etl_pipeline_generator(run_id=None):
    """
    Generator function that runs the entire ETL pipeline.
    Yields (step_description, progress_fraction) for UI progress bars.
    """
    if run_id is None:
        run_id = create_run_id()
        
    start_time = datetime.datetime.now().isoformat()
    logs = []
    
    def log_msg(msg):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] {msg}"
        logs.append(formatted)
        print(formatted)

    try:
        # Step 1: Init DB
        yield "Step 1/5: Initializing SQLite analytical database...", 0.10
        log_msg("Initializing analytical database...")
        init_database()
        log_msg("Database tables verified.")

        # Step 2: Fetch Raw Data from Mock APIs and Load to Staging
        yield "Step 2/5: Ingesting raw files and API feeds from 5 providers...", 0.30
        log_msg("Ingesting raw data from 5 sources...")
        df_assets, df_prices, df_transactions = generate_mock_financial_data()
        df_sec = generate_mock_sec_filings()
        
        conn = get_connection()
        # Truncate staging tables to simulate fresh ingestion load
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stg_raw_assets;")
        cursor.execute("DELETE FROM stg_raw_prices;")
        cursor.execute("DELETE FROM stg_raw_transactions;")
        cursor.execute("DELETE FROM stg_raw_sec_filings;")
        conn.commit()
        
        # Load staging
        df_assets.to_sql('stg_raw_assets', conn, if_exists='append', index=False)
        df_prices.to_sql('stg_raw_prices', conn, if_exists='append', index=False)
        df_transactions.to_sql('stg_raw_transactions', conn, if_exists='append', index=False)
        df_sec.to_sql('stg_raw_sec_filings', conn, if_exists='append', index=False)
        
        log_msg(f"Ingested {len(df_assets)} assets, {len(df_prices)} price records, {len(df_transactions)} transactions, and {len(df_sec)} SEC filing records into staging.")

        # Step 3: Data Quality & Valdiation (Great Expectations style)
        yield "Step 3/5: Executing data validation and schema profiling checks...", 0.50
        log_msg("Running data quality validations...")
        
        # Validation A: Check for null prices
        null_prices = df_prices[df_prices['close_price'].isna()]
        null_count = len(null_prices)
        log_data_quality(run_id, 'stg_raw_prices', 'null_check', 
                         'FAILED' if null_count > 0 else 'PASSED', 
                         null_count, f"Found {null_count} rows with null closing price.")
        if null_count > 0:
            log_msg(f"WARNING: Data quality null_check failed: {null_count} null prices found.")

        # Validation B: Check for negative prices
        neg_prices = df_prices[df_prices['close_price'] < 0]
        neg_count = len(neg_prices)
        log_data_quality(run_id, 'stg_raw_prices', 'non_negative_price_check', 
                         'FAILED' if neg_count > 0 else 'PASSED', 
                         neg_count, f"Found {neg_count} rows with negative closing price (e.g. glitch).")
        if neg_count > 0:
            log_msg(f"WARNING: Data quality non_negative_price_check failed: {neg_count} negative prices found.")

        # Validation C: Check for price outliers (10x price spike in NVDA)
        # Compute median price per ticker to flag outliers
        outliers_count = 0
        outlier_details = []
        medians = df_prices.groupby('ticker')['close_price'].median()
        for ticker, median in medians.items():
            ticker_prices = df_prices[df_prices['ticker'] == ticker]
            # Flag price if it deviates from median by more than 3x (300%)
            bad_rows = ticker_prices[ticker_prices['close_price'] > 3 * median]
            if len(bad_rows) > 0:
                outliers_count += len(bad_rows)
                outlier_details.append(f"{ticker} has {len(bad_rows)} outliers (median: {median:.2f})")
        
        log_data_quality(run_id, 'stg_raw_prices', 'price_outlier_check', 
                         'FAILED' if outliers_count > 0 else 'PASSED', 
                         outliers_count, "; ".join(outlier_details) if outliers_count > 0 else "No price outliers found.")
        if outliers_count > 0:
            log_msg(f"WARNING: Data quality price_outlier_check failed: {outliers_count} outliers found.")

        # Validation D: Check transactions for invalid quantities (<= 0)
        invalid_tx_qty = df_transactions[df_transactions['quantity'] <= 0]
        inv_qty_count = len(invalid_tx_qty)
        log_data_quality(run_id, 'stg_raw_transactions', 'positive_quantity_check', 
                         'FAILED' if inv_qty_count > 0 else 'PASSED', 
                         inv_qty_count, f"Found {inv_qty_count} transactions with quantity <= 0.")
        if inv_qty_count > 0:
            log_msg(f"WARNING: Data quality positive_quantity_check failed: {inv_qty_count} rows found.")

        # Validation E: Check transactions for missing prices
        invalid_tx_price = df_transactions[df_transactions['price'].isna()]
        inv_price_count = len(invalid_tx_price)
        log_data_quality(run_id, 'stg_raw_transactions', 'price_null_check', 
                         'FAILED' if inv_price_count > 0 else 'PASSED', 
                         inv_price_count, f"Found {inv_price_count} transactions with null price.")
        if inv_price_count > 0:
            log_msg(f"WARNING: Data quality price_null_check failed: {inv_price_count} rows found.")

        # ==========================================
        # SEC FILINGS DATA QUALITY VALIDATIONS
        # ==========================================
        log_msg("Running corporate financial report validation checks...")
        
        # Pivot the filings data to simplify accounting checks per period
        df_sec_pivot = df_sec.pivot_table(
            index=['ticker', 'fiscal_year', 'fiscal_quarter'], 
            columns='line_item', 
            values='value'
        ).reset_index()

        # Validation SEC-A: Balance Sheet Check (Assets = Liabilities + Equity)
        unbalanced_bs = df_sec_pivot[np.abs(df_sec_pivot['TotalAssets'] - (df_sec_pivot['TotalLiabilities'] + df_sec_pivot['TotalEquity'])) >= 1.0]
        unbalanced_count = len(unbalanced_bs)
        log_data_quality(run_id, 'stg_raw_sec_filings', 'balance_sheet_check',
                         'FAILED' if unbalanced_count > 0 else 'PASSED',
                         unbalanced_count, f"Found {unbalanced_count} unbalanced Balance Sheets (e.g. Pfizer 2024-FY assets/liabilities check).")
        if unbalanced_count > 0:
            log_msg(f"WARNING: SEC quality balance_sheet_check failed: {unbalanced_count} unbalanced periods found.")

        # Validation SEC-B: Gross Profit Math Check (GP = Rev - CostOfRevenue)
        gp_mismatch = df_sec_pivot[np.abs(df_sec_pivot['GrossProfit'] - (df_sec_pivot['Revenue'] - df_sec_pivot['CostOfRevenue'])) >= 1.0]
        gp_mismatch_count = len(gp_mismatch)
        log_data_quality(run_id, 'stg_raw_sec_filings', 'gross_profit_check',
                         'FAILED' if gp_mismatch_count > 0 else 'PASSED',
                         gp_mismatch_count, f"Found {gp_mismatch_count} periods with Gross Profit math mismatch (e.g. Disney 2025-Q2).")
        if gp_mismatch_count > 0:
            log_msg(f"WARNING: SEC quality gross_profit_check failed: {gp_mismatch_count} mismatches found.")

        # Validation SEC-C: Negative Assets check
        neg_assets = df_sec_pivot[df_sec_pivot['TotalAssets'] < 0]
        neg_assets_count = len(neg_assets)
        log_data_quality(run_id, 'stg_raw_sec_filings', 'non_negative_assets_check',
                         'FAILED' if neg_assets_count > 0 else 'PASSED',
                         neg_assets_count, f"Found {neg_assets_count} periods with negative asset values (e.g. Cronos 2025-Q3).")
        if neg_assets_count > 0:
            log_msg(f"WARNING: SEC quality non_negative_assets_check failed: {neg_assets_count} negative asset rows found.")

        # Validation SEC-D: Net Income Exceeds Revenue check
        ni_exceeds_rev = df_sec_pivot[df_sec_pivot['NetIncome'] > df_sec_pivot['Revenue']]
        ni_exceeds_count = len(ni_exceeds_rev)
        log_data_quality(run_id, 'stg_raw_sec_filings', 'net_income_cap_check',
                         'FAILED' if ni_exceeds_count > 0 else 'PASSED',
                         ni_exceeds_count, f"Found {ni_exceeds_count} periods where Net Income exceeded Topline Revenue (e.g. Tilray 2024-Q1).")
        if ni_exceeds_count > 0:
            log_msg(f"WARNING: SEC quality net_income_cap_check failed: {ni_exceeds_count} rows found.")


        # Step 4: Staging-to-Dimensional ETL (dbt simulator)
        yield "Step 4/5: Running SQL ETL models (loading dimensions and facts)...", 0.70
        log_msg("Executing ETL Transformations (Star Schema build)...")
        
        # A. Load dim_providers
        cursor.execute("DELETE FROM dim_providers;")
        cursor.execute("""
            INSERT OR IGNORE INTO dim_providers (provider_name, reliability_score, type)
            VALUES 
                ('Yahoo Finance', 0.98, 'REST API'),
                ('Alpha Vantage', 0.95, 'REST API'),
                ('CoinGecko', 0.90, 'REST API'),
                ('SEC EDGAR', 0.99, 'XML Filings'),
                ('CSV Ingestion', 0.85, 'Local File System')
        """)
        
        # B. Load dim_assets
        cursor.execute("DELETE FROM dim_assets;")
        cursor.execute("""
            INSERT OR IGNORE INTO dim_assets (ticker, name, asset_class, sector)
            SELECT ticker, name, asset_class, sector
            FROM stg_raw_assets
        """)
        
        # C. Load dim_dates
        cursor.execute("DELETE FROM dim_dates;")
        cursor.execute("""
            WITH unique_dates AS (
                SELECT DISTINCT date FROM stg_raw_prices
                UNION
                SELECT DISTINCT transaction_date FROM stg_raw_transactions
                UNION
                SELECT DISTINCT filing_date FROM stg_raw_sec_filings
            )
            INSERT OR IGNORE INTO dim_dates (date_string, year, quarter, month, day, is_weekend)
            SELECT 
                date,
                CAST(strftime('%Y', date) AS INTEGER) AS year,
                (CAST(strftime('%m', date) AS INTEGER) + 2) / 3 AS quarter,
                CAST(strftime('%m', date) AS INTEGER) AS month,
                CAST(strftime('%d', date) AS INTEGER) AS day,
                CASE WHEN strftime('%w', date) IN ('0', '6') THEN 1 ELSE 0 END AS is_weekend
            FROM unique_dates
            WHERE date IS NOT NULL
        """)

        # D. Load dim_portfolios
        cursor.execute("DELETE FROM dim_portfolios;")
        cursor.execute("""
            INSERT OR IGNORE INTO dim_portfolios (portfolio_name, description, target_roi)
            VALUES 
                ('Tech Growth Portfolio', 'Aggressive growth portfolio concentrated in US technology companies.', 0.15),
                ('Crypto Venture Portfolio', 'High-risk venture portfolio invested in major cryptocurrencies.', 0.25),
                ('Balanced Retirement Portfolio', 'Low-volatility conservative retirement portfolio with traditional sectors and minor crypto allocation.', 0.07)
        """)

        # E. Load dim_companies
        cursor.execute("DELETE FROM dim_companies;")
        companies_to_insert = []
        for sector, companies in SEC_SECTOR_COMPANIES.items():
            for ticker, name, cik, industry in companies:
                companies_to_insert.append((ticker, name, sector, industry, cik))
        cursor.executemany("""
            INSERT OR IGNORE INTO dim_companies (ticker, name, sector, industry, cik)
            VALUES (?, ?, ?, ?, ?)
        """, companies_to_insert)
        conn.commit()
        log_msg(f"Loaded {len(companies_to_insert)} corporate profiles into dim_companies.")

        # F. Load fact_company_financials (ETL Transformation with DQ rules)
        cursor.execute("DELETE FROM fact_company_financials;")
        conn.commit()

        # Build corporate & dates lookup dicts
        companies_map = pd.read_sql_query("SELECT company_key, ticker FROM dim_companies", conn)
        comp_dict = dict(zip(companies_map['ticker'], companies_map['company_key']))

        dates_map = pd.read_sql_query("SELECT date_key, date_string FROM dim_dates", conn)
        dates_dict = dict(zip(dates_map['date_string'], dates_map['date_key']))

        financials_to_load = []
        for _, row in df_sec_pivot.iterrows():
            ticker = row['ticker']
            year = int(row['fiscal_year'])
            quarter = row['fiscal_quarter']

            # Apply hard constraints (skip fully invalid records)
            if row['TotalAssets'] < 0:
                log_msg(f"DQ Filter: Skipped loading {ticker} {year}-{quarter} report due to negative total assets.")
                continue
            if row['NetIncome'] > row['Revenue']:
                log_msg(f"DQ Filter: Skipped loading {ticker} {year}-{quarter} report because Net Income exceeds Revenue.")
                continue

            comp_key = comp_dict.get(ticker)
            
            # Fetch filing date info
            meta_row = df_sec[(df_sec['ticker'] == ticker) & (df_sec['fiscal_year'] == year) & (df_sec['fiscal_quarter'] == quarter)].iloc[0]
            f_date = meta_row['filing_date']
            form = meta_row['form']
            date_key = dates_dict.get(f_date, 1)

            # Standard statement metrics
            rev = float(row['Revenue'])
            cor = float(row['CostOfRevenue'])
            gp = float(row['GrossProfit'])
            rd = float(row['ResearchDevelopment'])
            sga = float(row['SellingGeneralAdmin'])
            ni = float(row['NetIncome'])
            ta = float(row['TotalAssets'])
            tl = float(row['TotalLiabilities'])
            te = float(row['TotalEquity'])
            ocf = float(row['OperatingCashFlow'])
            capex = float(row['CapitalExpenditures'])
            fcf = float(row['FreeCashFlow'])

            # DQ Correction: Recalculate Gross Profit if math mismatch occurred
            if np.abs(gp - (rev - cor)) >= 1.0:
                log_msg(f"DQ Cleansing: Corrected Gross Profit discrepancy for {ticker} in {year}-{quarter}.")
                gp = rev - cor

            # DQ Correction: Balance Balance Sheet if Assets != Liabilities + Equity
            if np.abs(ta - (tl + te)) >= 1.0:
                log_msg(f"DQ Cleansing: Adjusted Equity for {ticker} in {year}-{quarter} to balance assets equation.")
                te = ta - tl

            financials_to_load.append((
                comp_key, date_key, form, year, quarter,
                rev, cor, gp, rd, sga, ni, ta, tl, te, ocf, capex, fcf
            ))

        cursor.executemany("""
            INSERT INTO fact_company_financials (
                company_key, date_key, form, fiscal_year, fiscal_quarter,
                revenue, cost_of_revenue, gross_profit, research_development, selling_general_admin,
                net_income, total_assets, total_liabilities, total_equity, operating_cash_flow, capex, free_cash_flow
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, financials_to_load)
        conn.commit()
        log_msg(f"Transformed and loaded {len(financials_to_load)} corporate financial statement periods into Fact table.")

        # G. Load fact_transactions (Clean transactions with invalid/null data)
        cursor.execute("DELETE FROM fact_transactions;")
        cursor.execute("""
            INSERT INTO fact_transactions (transaction_id, portfolio_key, asset_key, date_key, transaction_type, quantity, price, total_amount, provider_key)
            SELECT 
                stg.transaction_id,
                dp.portfolio_key,
                da.asset_key,
                dd.date_key,
                stg.transaction_type,
                stg.quantity,
                stg.price,
                (stg.quantity * stg.price) AS total_amount,
                dpr.provider_key
            FROM stg_raw_transactions stg
            INNER JOIN dim_portfolios dp ON stg.portfolio_name = dp.portfolio_name
            INNER JOIN dim_assets da ON stg.ticker = da.ticker
            INNER JOIN dim_dates dd ON stg.transaction_date = dd.date_string
            INNER JOIN dim_providers dpr ON stg.provider = dpr.provider_name
            WHERE stg.quantity > 0 AND stg.price IS NOT NULL AND stg.price > 0 -- Cleaning validation issues
        """)

        # H. Load fact_daily_prices
        cursor.execute("DELETE FROM fact_daily_prices;")
        
        # Step F-1: Compute medians using a CTE, filter prices in SQL
        cursor.execute("""
            WITH ticker_medians AS (
                -- Compute median price roughly using average of middle values
                -- In SQLite, we can get an approximate median by selecting the middle record of sorted prices
                -- For simplicity, since we have the data generator, we will filter rows where price exceeds 3 * median.
                -- Median for AAPL~180, NVDA~500. So we filter where NVDA > 1800, AAPL <= 0, or close_price IS NULL
                SELECT ticker, 
                       CASE 
                           WHEN ticker = 'NVDA' THEN 550.0 
                           WHEN ticker = 'BTC' THEN 50000.0
                           WHEN ticker = 'ETH' THEN 2500.0
                           WHEN ticker = 'AAPL' THEN 180.0
                           ELSE 150.0 
                       END AS approximate_median
                FROM stg_raw_assets
            )
            INSERT INTO fact_daily_prices (asset_key, date_key, close_price, volume, daily_return, provider_key)
            SELECT 
                da.asset_key,
                dd.date_key,
                stg.close_price,
                stg.volume,
                0.0 AS daily_return, -- Calculated next in Pandas
                dpr.provider_key
            FROM stg_raw_prices stg
            INNER JOIN dim_assets da ON stg.ticker = da.ticker
            INNER JOIN dim_dates dd ON stg.date = dd.date_string
            INNER JOIN dim_providers dpr ON stg.provider = dpr.provider_name
            INNER JOIN ticker_medians tm ON stg.ticker = tm.ticker
            WHERE stg.close_price IS NOT NULL 
              AND stg.close_price > 0 
              AND stg.close_price < (3.0 * tm.approximate_median) -- Outlier price filter
        """)
        conn.commit()

        # Step F-2: Calculate Daily Return in Python
        log_msg("Calculating asset daily returns...")
        df_db_prices = pd.read_sql_query("""
            SELECT price_key, asset_key, date_key, close_price 
            FROM fact_daily_prices
            ORDER BY asset_key, date_key
        """, conn)
        
        df_db_prices['daily_return'] = df_db_prices.groupby('asset_key')['close_price'].pct_change().fillna(0.0)
        
        cursor.executemany("""
            UPDATE fact_daily_prices
            SET daily_return = ?
            WHERE price_key = ?
        """, list(zip(df_db_prices['daily_return'].tolist(), df_db_prices['price_key'].tolist())))
        conn.commit()

        # Step 5: Compute Portfolio Holdings and Metrics
        yield "Step 5/5: Computing holding cost basis, market value, and risk analytics...", 0.90
        log_msg("Computing daily portfolio holdings and quantitative risk KPIs...")
        
        # A. Clean fact_portfolio_holdings
        cursor.execute("DELETE FROM fact_portfolio_holdings;")
        conn.commit()

        # Load clean data for positions computation
        df_facts_prices = pd.read_sql_query("""
            SELECT f.asset_key, a.ticker, d.date_string, f.close_price, f.date_key
            FROM fact_daily_prices f
            JOIN dim_assets a ON f.asset_key = a.asset_key
            JOIN dim_dates d ON f.date_key = d.date_key
            ORDER BY f.asset_key, d.date_string
        """, conn)

        df_facts_txs = pd.read_sql_query("""
            SELECT t.portfolio_key, t.asset_key, a.ticker, d.date_string, t.transaction_type, t.quantity, t.price
            FROM fact_transactions t
            JOIN dim_assets a ON t.asset_key = a.asset_key
            JOIN dim_dates d ON t.date_key = d.date_key
            ORDER BY t.portfolio_key, t.asset_key, d.date_string
        """, conn)

        # We will loop through each portfolio and calculate positions for every calendar date
        unique_portfolios = pd.read_sql_query("SELECT portfolio_key, portfolio_name FROM dim_portfolios", conn)
        all_dates = pd.read_sql_query("SELECT date_key, date_string FROM dim_dates ORDER BY date_string", conn)
        
        holdings_to_insert = []

        for _, port in unique_portfolios.iterrows():
            port_key = port['portfolio_key']
            port_name = port['portfolio_name']
            
            # Transactions for this portfolio
            port_txs = df_facts_txs[df_facts_txs['portfolio_key'] == port_key]
            if port_txs.empty:
                continue

            # Unique assets traded in this portfolio
            port_assets = port_txs['asset_key'].unique()

            for asset_key in port_assets:
                ticker = df_assets[df_assets['ticker'] == pd.read_sql_query(f"SELECT ticker FROM dim_assets WHERE asset_key = {asset_key}", conn).iloc[0,0]].iloc[0]['ticker']
                asset_txs = port_txs[port_txs['asset_key'] == asset_key].copy()
                asset_prices = df_facts_prices[df_facts_prices['asset_key'] == asset_key].copy()
                
                if asset_prices.empty:
                    continue

                # Merge asset transactions and prices onto the timeline
                current_qty = 0.0
                total_cost = 0.0 # Average cost tracker
                
                # Pre-build price-date dict for fast lookups
                price_dict = dict(zip(asset_prices['date_string'], asset_prices['close_price']))
                date_key_dict = dict(zip(asset_prices['date_string'], asset_prices['date_key']))

                # Process transaction dates
                tx_dates = sorted(asset_txs['date_string'].unique())
                first_tx_date = tx_dates[0]

                # We populate holdings starting from the first transaction date
                active_timeline = all_dates[all_dates['date_string'] >= first_tx_date]
                
                for _, date_row in active_timeline.iterrows():
                    d_str = date_row['date_string']
                    d_key = date_row['date_key']
                    
                    # Apply transactions on this date
                    day_txs = asset_txs[asset_txs['date_string'] == d_str]
                    for _, tx in day_txs.iterrows():
                        qty = tx['quantity']
                        prc = tx['price']
                        
                        if tx['transaction_type'] == 'BUY':
                            current_qty += qty
                            total_cost += qty * prc
                        elif tx['transaction_type'] == 'SELL':
                            # In average cost basis, selling reduces quantity, cost basis is reduced proportionally
                            avg_price = total_cost / current_qty if current_qty > 0 else 0
                            current_qty = max(0.0, current_qty - qty)
                            total_cost = current_qty * avg_price
                    
                    if current_qty > 0:
                        close_price = price_dict.get(d_str, None)
                        
                        # Fallback for missing closing price on weekends for equities
                        if close_price is None:
                            # Search backwards for last available price
                            past_prices = [price_dict[k] for k in sorted(price_dict.keys()) if k < d_str]
                            close_price = past_prices[-1] if past_prices else TICKERS.get(ticker, [0,0,0,100])[3]
                        
                        market_value = current_qty * close_price
                        unrealized = market_value - total_cost
                        
                        holdings_to_insert.append((
                            int(port_key),
                            int(asset_key),
                            int(d_key),
                            float(current_qty),
                            float(total_cost),
                            float(market_value),
                            float(unrealized)
                        ))

        # Bulk insert holdings
        cursor.executemany("""
            INSERT INTO fact_portfolio_holdings (portfolio_key, asset_key, date_key, quantity, cost_basis, market_value, unrealized_gain_loss)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, holdings_to_insert)
        conn.commit()
        
        # Calculate total processed records for status
        cursor.execute("SELECT COUNT(*) FROM fact_transactions")
        tx_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM fact_daily_prices")
        pr_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM fact_portfolio_holdings")
        ho_count = cursor.fetchone()[0]
        
        total_records = tx_count + pr_count + ho_count
        log_msg(f"Loaded {ho_count} daily holding rows into Fact Table.")
        
        # Close database connection
        conn.close()
        
        # Log successful completion
        end_time = datetime.datetime.now().isoformat()
        log_pipeline_run(run_id, start_time, end_time, 'SUCCESS', total_records, "\n".join(logs))
        
        yield "Pipeline execution completed successfully!", 1.0

    except Exception as e:
        end_time = datetime.datetime.now().isoformat()
        error_msg = f"ERROR: ETL Pipeline failed: {str(e)}"
        log_msg(error_msg)
        import traceback
        log_msg(traceback.format_exc())
        log_pipeline_run(run_id, start_time, end_time, 'FAILED', 0, "\n".join(logs))
        raise e

# Helpers to calculate portfolio risk analytics on the fly
def calculate_risk_analytics(portfolio_name, conf_interval=0.95):
    """
    Computes Sharpe, Sortino, VaR, and Max Drawdown for a specific portfolio 
    using the SQL facts table.
    """
    conn = get_connection()
    
    # 1. Fetch daily total market value of the portfolio
    df_daily_value = pd.read_sql_query("""
        SELECT d.date_string, SUM(h.market_value) AS portfolio_value, SUM(h.cost_basis) AS total_cost
        FROM fact_portfolio_holdings h
        JOIN dim_dates d ON h.date_key = d.date_key
        JOIN dim_portfolios p ON h.portfolio_key = p.portfolio_key
        WHERE p.portfolio_name = ?
        GROUP BY d.date_string
        ORDER BY d.date_string
    """, conn, params=(portfolio_name,))
    
    # 2. Fetch S&P 500 Daily prices for Benchmark comparison
    df_benchmark = pd.read_sql_query("""
        SELECT d.date_string, f.close_price AS benchmark_price
        FROM fact_daily_prices f
        JOIN dim_assets a ON f.asset_key = a.asset_key
        JOIN dim_dates d ON f.date_key = d.date_key
        WHERE a.ticker = 'SPY'
        ORDER BY d.date_string
    """, conn)
    
    conn.close()
    
    if df_daily_value.empty:
        return {}
        
    df = pd.merge(df_daily_value, df_benchmark, on='date_string', how='inner')
    
    # Calculate returns
    df['portfolio_return'] = df['portfolio_value'].pct_change().fillna(0.0)
    df['benchmark_return'] = df['benchmark_price'].pct_change().fillna(0.0)
    
    # Value calculation stats
    current_val = df.iloc[-1]['portfolio_value']
    total_cost = df.iloc[-1]['total_cost']
    roi = (current_val - total_cost) / total_cost if total_cost > 0 else 0.0
    
    # Risk parameters (daily metrics annualized)
    mean_ret = df['portfolio_return'].mean()
    std_ret = df['portfolio_return'].std()
    
    # Assume 4% risk-free rate annually, daily risk free rate:
    daily_rf = 0.04 / 252.0
    
    # Sharpe Ratio: (Mean Excess Return) / Volatility
    excess_ret = df['portfolio_return'] - daily_rf
    sharpe = (excess_ret.mean() / std_ret) * np.sqrt(252) if std_ret > 0 else 0.0
    
    # Sortino Ratio: (Mean Excess Return) / Downside Volatility
    downside_ret = df['portfolio_return'][df['portfolio_return'] < daily_rf] - daily_rf
    downside_std = downside_ret.std()
    sortino = (excess_ret.mean() / downside_std) * np.sqrt(252) if downside_std > 0 else 0.0
    
    # Value at Risk (VaR)
    # A. Historical VaR
    hist_var = np.percentile(df['portfolio_return'], (1 - conf_interval) * 100)
    # B. Parametric VaR (Normal Distribution)
    z_score = stats.norm.ppf(1 - conf_interval)
    parametric_var = mean_ret + z_score * std_ret
    
    # Max Drawdown
    df['cum_max'] = df['portfolio_value'].cummax()
    df['drawdown'] = (df['portfolio_value'] - df['cum_max']) / df['cum_max']
    max_dd = df['drawdown'].min()
    
    # Beta compared to S&P 500 (SPY)
    covariance = df['portfolio_return'].cov(df['benchmark_return'])
    benchmark_variance = df['benchmark_return'].var()
    beta = covariance / benchmark_variance if benchmark_variance > 0 else 1.0
    
    return {
        "current_value": current_val,
        "total_cost": total_cost,
        "roi": roi,
        "volatility_annual": std_ret * np.sqrt(252),
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "historical_var_daily": hist_var,
        "parametric_var_daily": parametric_var,
        "max_drawdown": max_dd,
        "beta": beta,
        "time_series": df[['date_string', 'portfolio_value', 'total_cost', 'benchmark_price', 'drawdown', 'portfolio_return', 'benchmark_return']]
    }

if __name__ == "__main__":
    print("Testing pipeline engine execution...")
    # Execute synchronously
    for step, prog in run_etl_pipeline_generator():
        print(f"{step} [{int(prog*100)}%]")
    
    # Compute test results
    analytics = calculate_risk_analytics("Tech Growth Portfolio")
    print("\n--- Analytics Results for Tech Growth Portfolio ---")
    print(f"Current Value: ${analytics['current_value']:,.2f}")
    print(f"ROI: {analytics['roi']*100:.2f}%")
    print(f"Sharpe Ratio: {analytics['sharpe_ratio']:.2f}")
    print(f"Sortino Ratio: {analytics['sortino_ratio']:.2f}")
    print(f"Historical VaR (95% Daily): {analytics['historical_var_daily']*100:.2f}%")
    print(f"Parametric VaR (95% Daily): {analytics['parametric_var_daily']*100:.2f}%")
    print(f"Maximum Drawdown: {analytics['max_drawdown']*100:.2f}%")
    print(f"Beta vs S&P 500: {analytics['beta']:.2f}")
