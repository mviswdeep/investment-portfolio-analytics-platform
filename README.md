# Investment Portfolio Analytics Platform

A high-fidelity financial analytics dashboard and robust ETL pipeline orchestrator built in Python, SQL, and Streamlit. This project is a dedicated showcase of **Data Engineering** expertise, featuring data integration from multiple mock APIs, automated data validation checks, structured star-schema analytical database modeling (dbt simulator in SQLite), and real-time pipeline visualizers alongside quantitative finance risk calculations.

---

## 🚀 Key Features

1. **Executive Portfolio Dashboard**:
   - Live performance tracking (Total Value, ROI, Annualized Volatility, Beta vs. S&P 500).
   - Core risk modeling metrics (Parametric & Historical Value at Risk (VaR), Maximum Drawdown, Sharpe Ratio, Sortino Ratio).
   - Interactive charts: Cumulative Returns Growth, Asset Allocation Weights, Drawdown Curve, and Returns Distribution.
2. **Automated ETL Ingestion & Pipeline Orchestrator**:
   - Ingestion from 5 sources (Yahoo Finance, Alpha Vantage, CoinGecko, SEC EDGAR, and local files).
   - Custom **Data Quality Layer** executing null checks, positive value assertions, and outlier price scrubbing (e.g., catching fat-finger price spikes).
   - Interactive DAG visualizer animating task execution states (Pending ➔ Running ➔ Success).
   - Detailed Data Quality Report Card logging and cleaning raw data errors before analytical load.
3. **Star Schema Data Warehouse Explorer**:
   - Star Schema dimensional layout separating fact tables (transactions, daily prices, portfolio holdings) and dimension tables (assets, portfolios, dates, providers).
   - Physical schema descriptions, column data types, and primary/foreign keys layout.
   - Interactive database tables preview.
4. **Analytical SQL Workbench Sandbox**:
   - Live text editor to execute arbitrary SQL queries (joins, window functions, CTEs) directly against the database.
   - Dynamic auto-visualization: Chart query results (Bar, Line, Area) instantly.

---

## 🗃️ Analytical Data Warehouse Model (Star Schema)

The platform models raw transactions and pricing data into an optimized analytical star schema for rapid reporting and calculation:

```
                  +-------------------+
                  |    dim_assets     |
                  +-------------------+
                            | 1
                            |
                            | *
+-----------------+       +-------------------------+       +-------------------+
| dim_portfolios  |-------|    fact_transactions    |-------|     dim_dates     |
+-----------------+ 1   * +-------------------------+ *   1 +-------------------+
        |                                                           |
        | 1                                                         | 1
        |                                                           |
        | *                                                         | *
        |                 +-------------------------+               |
        +-----------------| fact_portfolio_holdings |---------------+
                          +-------------------------+
                                        | *
                                        |
                                        | 1
                               +-----------------+
                               |   dim_assets    |
                               +-----------------+
```

### Table Definitions
- **`dim_assets`**: Asset master metadata (ticker, company name, asset class, sector).
- **`dim_portfolios`**: Managed investment portfolios (description, target ROI threshold).
- **`dim_dates`**: Standard calendar dimensions (year, month, quarter, day, weekend checks).
- **`dim_providers`**: Source feed metadata (reliability tracking, protocol type).
- **`fact_transactions`**: Individual trade history (portfolio, asset, date, buy/sell action, quantity, price).
- **`fact_daily_prices`**: Historical closing asset prices and daily log returns (asset, date, close price, volume).
- **`fact_portfolio_holdings`**: Aggregated daily snapshots of asset quantities, average cost basis, market value, and unrealized gains.

---

## 🛡️ Data Quality & Cleaning
Raw datasets include realistic data anomalies designed to test the validation layer:
- **Null Prices**: Missing close prices are logged as warnings and skipped.
- **Negative Prices**: Price inputs $\le 0$ are discarded.
- **Fat-finger Spikes**: Price entries $> 3 \times$ median of the asset are flagged as anomalies and filtered out.
- **Invalid Quantities**: Transactions with transaction volume $\le 0$ are flagged as invalid and excluded from the fact table.

---

## 📈 Quantitative Formulas

The quantitative analytics engine calculates metrics dynamically over the historical price series:

- **Sharpe Ratio** (Risk-Adjusted Return):
  $$\text{Sharpe} = \frac{\overline{R}_p - R_f}{\sigma_p} \times \sqrt{252}$$
  *Where $\overline{R}_p$ is the mean daily portfolio return, $R_f$ is the daily risk-free rate (assumed 4% annually), and $\sigma_p$ is the standard deviation of daily portfolio returns.*

- **Sortino Ratio** (Adjusted for Downside Risk):
  $$\text{Sortino} = \frac{\overline{R}_p - R_f}{\sigma_{d}} \times \sqrt{252}$$
  *Where $\sigma_d$ is the downside semi-standard deviation calculated only on returns below the risk-free rate threshold.*

- **Value at Risk (VaR)** (Historical Simulation, 95% Confidence):
  $$\text{VaR}_{95\%} = \text{Percentile}(R_p, 5)$$
  *Represents the 5th percentile of historical daily portfolio returns, indicating that there is a 5% chance the daily portfolio loss will exceed this value.*

- **Maximum Drawdown**:
  $$\text{Max Drawdown} = \min \left( \frac{V_t - \max_{0 \le s \le t} V_s}{\max_{0 \le s \le t} V_s} \right)$$
  *Finds the largest peak-to-trough drop in total portfolio market value over the entire timeframe.*

---

## 🛠️ Setup and Installation Instructions

Follow these steps to run the application locally:

### 1. Prerequisites
Ensure you have Python 3.9+ installed:
```bash
python3 --version
```

### 2. Configure Virtual Environment & Install Dependencies
Initialize a clean Python environment and load dependencies:
```bash
# Create environment
python3 -m venv .venv

# Activate environment (Mac/Linux)
source .venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 3. Run the Database Initialization & Pipeline Check
Run the orchestrator script to build the analytical SQLite database and compute baseline holding metrics:
```bash
python3 pipeline_engine.py
```

### 4. Launch the Streamlit Web Application
Start the Streamlit dashboard server:
```bash
streamlit run app.py
```
A browser tab will automatically open at `http://localhost:8501`.
