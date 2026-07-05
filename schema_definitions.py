import sqlite3
import os

DB_PATH = "portfolio.db"

def get_connection():
    """Returns a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)

def init_database():
    """Initializes all database tables, both staging and star schema."""
    conn = get_connection()
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # ==========================================
    # 1. STAGING TABLES (RAW INGESTION)
    # ==========================================
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stg_raw_prices (
        ticker TEXT,
        date TEXT,
        close_price REAL,
        volume REAL,
        provider TEXT,
        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stg_raw_transactions (
        transaction_id TEXT,
        portfolio_name TEXT,
        ticker TEXT,
        transaction_type TEXT,
        quantity REAL,
        price REAL,
        transaction_date TEXT,
        provider TEXT,
        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stg_raw_assets (
        ticker TEXT,
        name TEXT,
        asset_class TEXT,
        sector TEXT,
        provider TEXT,
        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stg_raw_sec_filings (
        ticker TEXT,
        company_name TEXT,
        form TEXT,
        fiscal_year INTEGER,
        fiscal_quarter TEXT,
        line_item TEXT,
        value REAL,
        filing_date TEXT,
        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)


    # ==========================================
    # 2. DIMENSION TABLES (STAR SCHEMA)
    # ==========================================
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dim_assets (
        asset_key INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT UNIQUE,
        name TEXT,
        asset_class TEXT,
        sector TEXT,
        last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dim_dates (
        date_key INTEGER PRIMARY KEY AUTOINCREMENT,
        date_string TEXT UNIQUE, -- YYYY-MM-DD
        year INTEGER,
        quarter INTEGER,
        month INTEGER,
        day INTEGER,
        is_weekend INTEGER
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dim_portfolios (
        portfolio_key INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_name TEXT UNIQUE,
        description TEXT,
        target_roi REAL,
        last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dim_providers (
        provider_key INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_name TEXT UNIQUE,
        reliability_score REAL,
        type TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dim_companies (
        company_key INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT UNIQUE,
        name TEXT,
        sector TEXT,
        industry TEXT,
        cik TEXT,
        last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)


    # ==========================================
    # 3. FACT TABLES (STAR SCHEMA)
    # ==========================================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fact_transactions (
        transaction_key INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT UNIQUE,
        portfolio_key INTEGER,
        asset_key INTEGER,
        date_key INTEGER,
        transaction_type TEXT,
        quantity REAL,
        price REAL,
        total_amount REAL,
        provider_key INTEGER,
        FOREIGN KEY (portfolio_key) REFERENCES dim_portfolios(portfolio_key),
        FOREIGN KEY (asset_key) REFERENCES dim_assets(asset_key),
        FOREIGN KEY (date_key) REFERENCES dim_dates(date_key),
        FOREIGN KEY (provider_key) REFERENCES dim_providers(provider_key)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fact_daily_prices (
        price_key INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_key INTEGER,
        date_key INTEGER,
        close_price REAL,
        volume REAL,
        daily_return REAL,
        provider_key INTEGER,
        FOREIGN KEY (asset_key) REFERENCES dim_assets(asset_key),
        FOREIGN KEY (date_key) REFERENCES dim_dates(date_key),
        FOREIGN KEY (provider_key) REFERENCES dim_providers(provider_key),
        UNIQUE(asset_key, date_key)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fact_portfolio_holdings (
        holding_key INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_key INTEGER,
        asset_key INTEGER,
        date_key INTEGER,
        quantity REAL,
        cost_basis REAL,
        market_value REAL,
        unrealized_gain_loss REAL,
        FOREIGN KEY (portfolio_key) REFERENCES dim_portfolios(portfolio_key),
        FOREIGN KEY (asset_key) REFERENCES dim_assets(asset_key),
        FOREIGN KEY (date_key) REFERENCES dim_dates(date_key),
        UNIQUE(portfolio_key, asset_key, date_key)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fact_company_financials (
        financial_key INTEGER PRIMARY KEY AUTOINCREMENT,
        company_key INTEGER,
        date_key INTEGER,
        form TEXT,
        fiscal_year INTEGER,
        fiscal_quarter TEXT,
        revenue REAL,
        cost_of_revenue REAL,
        gross_profit REAL,
        research_development REAL,
        selling_general_admin REAL,
        net_income REAL,
        total_assets REAL,
        total_liabilities REAL,
        total_equity REAL,
        operating_cash_flow REAL,
        capex REAL,
        free_cash_flow REAL,
        FOREIGN KEY (company_key) REFERENCES dim_companies(company_key),
        FOREIGN KEY (date_key) REFERENCES dim_dates(date_key),
        UNIQUE(company_key, fiscal_year, fiscal_quarter)
    );
    """)


    # ==========================================
    # 4. ORCHESTRATION & METADATA TABLES
    # ==========================================
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data_quality_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        table_name TEXT,
        rule_name TEXT,
        status TEXT, -- PASSED, FAILED
        failure_count INTEGER,
        details TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        run_id TEXT PRIMARY KEY,
        start_time TEXT,
        end_time TEXT,
        status TEXT, -- SUCCESS, FAILED, RUNNING
        records_processed INTEGER,
        logs TEXT
    );
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_database()
