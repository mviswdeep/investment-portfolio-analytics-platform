import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import time
import streamlit.components.v1 as components
from pipeline_engine import run_etl_pipeline_generator, calculate_risk_analytics, get_connection, create_run_id
from data_generator import SEC_SECTOR_COMPANIES

# Page configuration
st.set_page_config(
    page_title="Investment Portfolio Analytics & Corporate Financials Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Styling (Dark Mode Financial Dashboard)
def inject_custom_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        
        /* Typography & Core theme override */
        html, body, [class*="css"] {
            font-family: 'Outfit', sans-serif;
        }
        
        /* Card design */
        .metric-card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            transition: transform 0.2s ease, border-color 0.2s ease;
            margin-bottom: 1rem;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            border-color: #6366f1;
        }
        .metric-title {
            font-size: 0.875rem;
            color: #94a3b8;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
        .metric-value {
            font-size: 1.875rem;
            font-weight: 700;
            color: #f8fafc;
            line-height: 1;
        }
        .metric-subtext {
            font-size: 0.8rem;
            color: #64748b;
            margin-top: 0.5rem;
        }
        .text-success { color: #10b981 !important; }
        .text-danger { color: #ef4444 !important; }
        .text-warning { color: #f59e0b !important; }
        .text-info { color: #3b82f6 !important; }

        /* Custom scrollbar for console logs */
        .terminal-console {
            background-color: #0f172a;
            color: #38bdf8;
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.85rem;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #1e293b;
            height: 250px;
            overflow-y: scroll;
            white-space: pre-wrap;
        }

        /* DAG Pipeline Visualization styles */
        .dag-container {
            display: flex;
            flex-direction: column;
            gap: 20px;
            padding: 20px;
            background: #0f172a;
            border-radius: 12px;
            border: 1px solid #1e293b;
            margin-bottom: 20px;
        }
        .dag-row {
            display: flex;
            justify-content: space-around;
            align-items: center;
            width: 100%;
            position: relative;
        }
        .dag-node {
            background: #1e293b;
            border: 2px solid #475569;
            border-radius: 8px;
            padding: 10px 15px;
            min-width: 150px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        .node-pending {
            border-color: #475569;
            color: #64748b;
        }
        .node-running {
            border-color: #f59e0b;
            color: #f59e0b;
            box-shadow: 0 0 12px rgba(245, 158, 11, 0.4);
            animation: pulse 1.5s infinite alternate;
        }
        .node-success {
            border-color: #10b981;
            background: #064e3b;
            color: #a7f3d0;
        }
        .node-failed {
            border-color: #ef4444;
            background: #7f1d1d;
            color: #fca5a5;
        }
        .node-name {
            font-weight: 600;
            font-size: 0.9rem;
        }
        .node-status-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            margin-top: 4px;
            font-weight: 500;
        }
        .dag-connector {
            font-size: 1.5rem;
            color: #475569;
            font-weight: bold;
        }
        @keyframes pulse {
            0% { transform: scale(1); }
            100% { transform: scale(1.05); }
        }
    </style>
    """, unsafe_allow_html=True)

# Helper function to render mermaid
def st_mermaid(code: str, height=500):
    html = f"""
    <div style="background-color: #0f172a; padding: 10px; border-radius: 8px;">
        <pre class="mermaid" style="background-color: #0f172a; color: #cbd5e1; border: none; text-align: center;">
        {code}
        </pre>
    </div>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ 
            startOnLoad: true, 
            theme: 'dark',
            securityLevel: 'loose'
        }});
    </script>
    """
    components.html(html, height=height, scrolling=True)

# Formatting helpers
def format_currency(val):
    if abs(val) >= 1e9:
        return f"${val / 1e9:,.2f} B"
    elif abs(val) >= 1e6:
        return f"${val / 1e6:,.2f} M"
    else:
        return f"${val:,.2f}"

# ==========================================
# PAGE 1: PORTFOLIO RISK & PERFORMANCE ANALYTICS
# ==========================================
def render_portfolio_page():
    inject_custom_css()
    
    st.subheader("📊 Portfolio Risk & Performance Analytics")
    st.markdown("A premium financial risk-modeling workspace detailing holdings and portfolio Value at Risk (VaR).")

    # Check if DB exists
    try:
        conn = get_connection()
        portfolios_df = pd.read_sql_query("SELECT portfolio_name FROM dim_portfolios", conn)
        conn.close()
        if portfolios_df.empty:
            portfolios_list = ["Tech Growth Portfolio", "Crypto Venture Portfolio", "Balanced Retirement Portfolio"]
        else:
            portfolios_list = portfolios_df['portfolio_name'].tolist()
    except Exception:
        portfolios_list = ["Tech Growth Portfolio", "Crypto Venture Portfolio", "Balanced Retirement Portfolio"]

    selected_portfolio = st.sidebar.selectbox("📂 Select Active Portfolio", portfolios_list)
    conf_interval = st.sidebar.slider("🛡️ Value at Risk (VaR) Confidence", 0.90, 0.99, 0.95, 0.01)

    # Setup session states for Pipeline execution
    if "pipeline_phase" not in st.session_state:
        st.session_state.pipeline_phase = 0
    if "pipeline_logs" not in st.session_state:
        st.session_state.pipeline_logs = "Pipeline not started. Click 'Run ETL Pipeline' to begin."
    if "pipeline_run_status" not in st.session_state:
        st.session_state.pipeline_run_status = "PENDING"
    if "pipeline_progress" not in st.session_state:
        st.session_state.pipeline_progress = 0.0

    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Overview Dashboard", 
        "⛓️ ETL DAG Orchestrator", 
        "🗃️ DB Data Schema Explorer", 
        "💻 SQL Query Sandbox"
    ])

    # TAB 1: OVERVIEW DASHBOARD
    with tab1:
        try:
            analytics = calculate_risk_analytics(selected_portfolio, conf_interval)
        except Exception:
            analytics = {}
            st.warning("Database analytical tables not initialized yet. Please navigate to the **ETL DAG Orchestrator** tab and click 'Trigger ETL Pipeline' to generate records.")

        if analytics:
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            with kpi1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Portfolio Market Value</div>
                    <div class="metric-value">${analytics['current_value']:,.2f}</div>
                    <div class="metric-subtext">Cost Basis: ${analytics['total_cost']:,.2f}</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi2:
                roi_val = analytics['roi'] * 100
                roi_class = "text-success" if roi_val >= 0 else "text-danger"
                roi_sign = "+" if roi_val >= 0 else ""
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Return on Investment (ROI)</div>
                    <div class="metric-value {roi_class}">{roi_sign}{roi_val:.2f}%</div>
                    <div class="metric-subtext">Historical Performance Period</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi3:
                sharpe_val = analytics['sharpe_ratio']
                sharpe_class = "text-success" if sharpe_val >= 1.5 else ("text-warning" if sharpe_val >= 1.0 else "text-danger")
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Annualized Sharpe Ratio</div>
                    <div class="metric-value {sharpe_class}">{sharpe_val:.2f}</div>
                    <div class="metric-subtext">Risk-Adjusted Return (Rf=4.0%)</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi4:
                var_val = analytics['historical_var_daily'] * 100
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Daily Value at Risk (VaR)</div>
                    <div class="metric-value text-danger">{var_val:.2f}%</div>
                    <div class="metric-subtext">{int(conf_interval*100)}% Confidence level (Hist)</div>
                </div>
                """, unsafe_allow_html=True)

            kpi5, kpi6, kpi7, kpi8 = st.columns(4)
            with kpi5:
                vol_val = analytics['volatility_annual'] * 100
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Annualized Volatility</div>
                    <div class="metric-value text-info">{vol_val:.2f}%</div>
                    <div class="metric-subtext">Daily standard deviation annualized</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi6:
                sortino_val = analytics['sortino_ratio']
                sortino_class = "text-success" if sortino_val >= 1.5 else ("text-warning" if sortino_val >= 1.0 else "text-danger")
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Annualized Sortino Ratio</div>
                    <div class="metric-value {sortino_class}">{sortino_val:.2f}</div>
                    <div class="metric-subtext">Downside deviation adjustment</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi7:
                max_dd_val = analytics['max_drawdown'] * 100
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Maximum Drawdown</div>
                    <div class="metric-value text-danger">{max_dd_val:.2f}%</div>
                    <div class="metric-subtext">Peak-to-trough maximum drop</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi8:
                beta_val = analytics['beta']
                beta_class = "text-success" if abs(beta_val - 1.0) < 0.2 else "text-info"
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Beta (vs S&P 500 SPY)</div>
                    <div class="metric-value {beta_class}">{beta_val:.2f}</div>
                    <div class="metric-subtext">Systemic market risk sensitivity</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("### 📊 Performance and Allocation Analytics")
            col_c1, col_c2 = st.columns([2, 1])
            df_ts = analytics['time_series']
            
            with col_c1:
                df_returns = df_ts.copy()
                initial_port_val = df_returns.iloc[0]['portfolio_value']
                initial_bench_val = df_returns.iloc[0]['benchmark_price']
                df_returns['Portfolio Returns'] = (df_returns['portfolio_value'] / initial_port_val - 1) * 100
                df_returns['S&P 500 Index (Benchmark)'] = (df_returns['benchmark_price'] / initial_bench_val - 1) * 100
                
                fig_perf = px.line(
                    df_returns, 
                    x='date_string', 
                    y=['Portfolio Returns', 'S&P 500 Index (Benchmark)'],
                    title="Cumulative Returns Comparison (%)",
                    labels={'value': 'Cumulative Return (%)', 'date_string': 'Date', 'variable': 'Asset'},
                    color_discrete_map={'Portfolio Returns': '#6366f1', 'S&P 500 Index (Benchmark)': '#475569'}
                )
                fig_perf.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#cbd5e1',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    xaxis=dict(showgrid=True, gridcolor='#1e293b'), yaxis=dict(showgrid=True, gridcolor='#1e293b')
                )
                st.plotly_chart(fig_perf, use_container_width=True)

            with col_c2:
                conn = get_connection()
                latest_holdings = pd.read_sql_query("""
                    SELECT a.ticker, h.market_value
                    FROM fact_portfolio_holdings h
                    JOIN dim_portfolios p ON h.portfolio_key = p.portfolio_key
                    JOIN dim_assets a ON h.asset_key = a.asset_key
                    JOIN dim_dates d ON h.date_key = d.date_key
                    WHERE p.portfolio_name = ?
                      AND d.date_string = (SELECT MAX(date_string) FROM dim_dates)
                """, conn, params=(selected_portfolio,))
                conn.close()
                
                if not latest_holdings.empty:
                    fig_alloc = px.pie(
                        latest_holdings, values='market_value', names='ticker', 
                        title="Asset Allocation (Market Value)", hole=0.4,
                        color_discrete_sequence=px.colors.sequential.Purples
                    )
                    fig_alloc.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#cbd5e1')
                    st.plotly_chart(fig_alloc, use_container_width=True)
                else:
                    st.info("No holding records found.")

            col_c3, col_c4 = st.columns([1, 1])
            with col_c3:
                df_dd = df_ts.copy()
                df_dd['Drawdown (%)'] = df_dd['drawdown'] * 100
                fig_dd = px.area(df_dd, x='date_string', y='Drawdown (%)', title="Historical Drawdown Curve (%)", color_discrete_sequence=['#ef4444'])
                fig_dd.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#cbd5e1',
                    xaxis=dict(showgrid=True, gridcolor='#1e293b'), yaxis=dict(showgrid=True, gridcolor='#1e293b')
                )
                st.plotly_chart(fig_dd, use_container_width=True)
                
            with col_c4:
                fig_hist = px.histogram(
                    df_ts, x='portfolio_return', title="Daily Returns Distribution & Value at Risk Threshold",
                    labels={'portfolio_return': 'Daily Return'}, color_discrete_sequence=['#10b981'], nbins=50
                )
                fig_hist.add_vline(
                    x=analytics['historical_var_daily'], line_dash="dash", line_color="#ef4444",
                    annotation_text=f"Hist VaR: {analytics['historical_var_daily']*100:.2f}%", annotation_position="top left"
                )
                fig_hist.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#cbd5e1',
                    xaxis=dict(showgrid=True, gridcolor='#1e293b'), yaxis=dict(showgrid=True, gridcolor='#1e293b')
                )
                st.plotly_chart(fig_hist, use_container_width=True)

    # TAB 2: ETL DAG ORCHESTRATOR
    with tab2:
        st.subheader("⛓️ Ingestion & Transformation Orchestrator")
        
        def get_node_class(phase, target_phase):
            if phase < target_phase: return "node-pending"
            elif phase == target_phase: return "node-running"
            else: return "node-success"

        def get_status_label(phase, target_phase):
            if phase < target_phase: return "PENDING"
            elif phase == target_phase: return "RUNNING..."
            else: return "SUCCESS"

        col_o1, col_o2 = st.columns([1, 2])
        with col_o1:
            st.markdown("### 🎛️ Control Panel")
            trigger_pipeline = st.button("🚀 Trigger ETL Pipeline", use_container_width=True)
            status_box = st.empty()
            progress_bar = st.empty()
            
            if trigger_pipeline:
                run_id = create_run_id()
                generator = run_etl_pipeline_generator(run_id)
                log_collector = []
                
                for step_desc, progress_val in generator:
                    if "Step 1" in step_desc: st.session_state.pipeline_phase = 1
                    elif "Step 2" in step_desc: st.session_state.pipeline_phase = 1
                    elif "Step 3" in step_desc: st.session_state.pipeline_phase = 2
                    elif "Step 4" in step_desc: st.session_state.pipeline_phase = 3
                    elif "Step 5" in step_desc: st.session_state.pipeline_phase = 4
                    elif "completed" in step_desc: st.session_state.pipeline_phase = 5
                    
                    st.session_state.pipeline_progress = progress_val
                    st.session_state.pipeline_run_status = "RUNNING"
                    status_box.markdown(f"**Status:** {step_desc}")
                    progress_bar.progress(progress_val)
                    log_collector.append(step_desc)
                    st.session_state.pipeline_logs = "\n".join(log_collector)
                    time.sleep(1.0)
                    
                st.session_state.pipeline_run_status = "SUCCESS"
                status_box.markdown("**Status:** Pipeline finished successfully! ✨")
                st.rerun()

            st.markdown(f"**Current Pipeline Run Status:** `{st.session_state.pipeline_run_status}`")
            
        with col_o2:
            st.markdown("### 🗺️ Pipeline DAG Visualizer")
            ph = st.session_state.pipeline_phase
            dag_html = f"""
            <div class="dag-container">
                <div class="dag-row">
                    <div class="dag-node {get_node_class(ph, 1)}"><div class="node-name">Ingest Yahoo Fin</div><div class="node-status-label">{get_status_label(ph, 1)}</div></div>
                    <div class="dag-node {get_node_class(ph, 1)}"><div class="node-name">Ingest CoinGecko</div><div class="node-status-label">{get_status_label(ph, 1)}</div></div>
                    <div class="dag-node {get_node_class(ph, 1)}"><div class="node-name">Ingest Alpha Vantage</div><div class="node-status-label">{get_status_label(ph, 1)}</div></div>
                    <div class="dag-node {get_node_class(ph, 1)}"><div class="node-name">Ingest SEC EDGAR</div><div class="node-status-label">{get_status_label(ph, 1)}</div></div>
                </div>
                <div class="dag-row"><div class="dag-connector">↓</div></div>
                <div class="dag-row">
                    <div class="dag-node {get_node_class(ph, 2)}"><div class="node-name">Data Quality Profiler</div><div class="node-status-label">{get_status_label(ph, 2)}</div></div>
                </div>
                <div class="dag-row"><div class="dag-connector">↓</div></div>
                <div class="dag-row">
                    <div class="dag-node {get_node_class(ph, 3)}"><div class="node-name">dbt Dimensional Load</div><div class="node-status-label">{get_status_label(ph, 3)}</div></div>
                </div>
                <div class="dag-row"><div class="dag-connector">↓</div></div>
                <div class="dag-row">
                    <div class="dag-node {get_node_class(ph, 4)}"><div class="node-name">Serving Fact Aggregate</div><div class="node-status-label">{get_status_label(ph, 4)}</div></div>
                </div>
            </div>
            """
            st.markdown(dag_html, unsafe_allow_html=True)

        col_l1, col_l2 = st.columns([1, 1])
        with col_l1:
            st.markdown("### 📜 Pipeline Execution Logs")
            st.markdown(f'<div class="terminal-console">{st.session_state.pipeline_logs}</div>', unsafe_allow_html=True)
        with col_l2:
            st.markdown("### 🛡️ Data Quality Report Card")
            try:
                conn = get_connection()
                dq_df = pd.read_sql_query("SELECT timestamp, table_name, rule_name, status, failure_count, details FROM data_quality_logs ORDER BY timestamp DESC LIMIT 10", conn)
                conn.close()
                if not dq_df.empty:
                    def style_status(val):
                        color = '#10b981' if val == 'PASSED' else '#ef4444'
                        return f'<span style="color:{color}; font-weight:bold;">{val}</span>'
                    dq_df['status'] = dq_df['status'].apply(style_status)
                    st.write(dq_df.to_html(escape=False, index=False), unsafe_allow_html=True)
                else:
                    st.info("No pipeline quality checks have run yet.")
            except Exception:
                st.info("Database tables not loaded.")

    # TAB 3: DB SCHEMA EXPLORER
    with tab3:
        st.subheader("🗃️ Star Schema Analytical Data Warehouse Schema")
        st_mermaid("""
        erDiagram
            dim_assets ||--o{ fact_transactions : asset_key
            dim_portfolios ||--o{ fact_transactions : portfolio_key
            dim_dates ||--o{ fact_transactions : date_key
            dim_providers ||--o{ fact_transactions : provider_key
            dim_assets ||--o{ fact_daily_prices : asset_key
            dim_dates ||--o{ fact_daily_prices : date_key
            dim_providers ||--o{ fact_daily_prices : provider_key
            dim_portfolios ||--o{ fact_portfolio_holdings : portfolio_key
            dim_assets ||--o{ fact_portfolio_holdings : asset_key
            dim_dates ||--o{ fact_portfolio_holdings : date_key
            dim_companies ||--o{ fact_company_financials : company_key
            dim_dates ||--o{ fact_company_financials : date_key

            dim_assets {
                int asset_key PK
                string ticker
                string name
                string asset_class
                string sector
            }
            dim_companies {
                int company_key PK
                string ticker
                string name
                string sector
                string industry
                string cik
            }
            fact_company_financials {
                int financial_key PK
                int company_key FK
                int date_key FK
                string form
                int fiscal_year
                string fiscal_quarter
                float revenue
                float gross_profit
                float net_income
                float total_assets
                float total_liabilities
                float total_equity
                float free_cash_flow
            }
        """, height=650)

        st.markdown("### 🔍 Tables Data Browser")
        tables_list = ["dim_assets", "dim_companies", "dim_dates", "dim_portfolios", "dim_providers", "fact_transactions", "fact_daily_prices", "fact_portfolio_holdings", "fact_company_financials", "stg_raw_prices", "stg_raw_transactions", "stg_raw_sec_filings"]
        selected_table = st.selectbox("📋 Select Database Table to Inspect", tables_list)
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({selected_table})")
            schema_info = cursor.fetchall()
            df_schema = pd.DataFrame(schema_info, columns=["CID", "Column Name", "Data Type", "NotNull", "Default Value", "Primary Key"])
            cursor.execute(f"SELECT COUNT(*) FROM {selected_table}")
            count_val = cursor.fetchone()[0]
            df_data = pd.read_sql_query(f"SELECT * FROM {selected_table} LIMIT 100", conn)
            conn.close()
            
            col_s1, col_s2 = st.columns([1, 2])
            with col_s1:
                st.markdown(f"**Table Name:** `{selected_table}`")
                st.markdown(f"**Total Records:** `{count_val:,}`")
                st.dataframe(df_schema[["Column Name", "Data Type", "Primary Key"]], use_container_width=True, hide_index=True)
            with col_s2:
                st.markdown(f"**Data Preview (Top 100 Rows):**")
                st.dataframe(df_data, use_container_width=True)
        except Exception:
            st.info("Database tables not loaded.")

    # TAB 4: SQL QUERY SANDBOX
    with tab4:
        st.subheader("💻 SQL Analytical Query Runner")
        
        templates = {
            "Custom Query": "",
            "🔍 Template 1: Portfolio Holdings Value Snapshot": 
                "SELECT p.portfolio_name, a.ticker, a.name, h.quantity, ROUND(h.cost_basis, 2) AS cost_basis, ROUND(h.market_value, 2) AS market_value FROM fact_portfolio_holdings h JOIN dim_portfolios p ON h.portfolio_key = p.portfolio_key JOIN dim_assets a ON h.asset_key = a.asset_key JOIN dim_dates d ON h.date_key = d.date_key WHERE d.date_string = (SELECT MAX(date_string) FROM dim_dates);",
            "📈 Template 2: Sector Corporate Financial Performance":
                "SELECT c.name, c.ticker, f.fiscal_year, f.fiscal_quarter, ROUND(f.revenue / 1e9, 2) AS rev_billions, ROUND(f.net_income / 1e9, 2) AS net_inc_billions, ROUND((f.net_income / f.revenue)*100, 2) AS net_margin_pct FROM fact_company_financials f JOIN dim_companies c ON f.company_key = c.company_key WHERE c.sector = 'Technology' AND f.fiscal_year = 2025 AND f.fiscal_quarter = 'FY' ORDER BY rev_billions DESC;",
            "🛡️ Template 3: Data Quality Error Audit":
                "SELECT timestamp, table_name, rule_name, status, failure_count, details FROM data_quality_logs ORDER BY timestamp DESC LIMIT 20;"
        }
        
        selected_template = st.selectbox("💡 Choose SQL Query Template", list(templates.keys()))
        sql_input = st.text_area("📝 SQL Query Editor", value=templates[selected_template], height=180)
        
        if st.button("▶️ Execute Query", use_container_width=True) and sql_input.strip() != "":
            try:
                conn = get_connection()
                df_result = pd.read_sql_query(sql_input, conn)
                conn.close()
                st.success(f"Query returned **{len(df_result)}** rows.")
                st.dataframe(df_result, use_container_width=True)
                
                if len(df_result) > 0:
                    cols = df_result.columns.tolist()
                    num_cols = df_result.select_dtypes(include=[np.number]).columns.tolist()
                    non_num_cols = df_result.select_dtypes(exclude=[np.number]).columns.tolist()
                    
                    col_v1, col_v2, col_v3 = st.columns(3)
                    with col_v1: x_col = st.selectbox("X Axis", cols, index=cols.index(non_num_cols[0]) if non_num_cols else 0)
                    with col_v2: y_col = st.selectbox("Y Axis", num_cols if num_cols else cols, index=0)
                    with col_v3: chart_type = st.selectbox("Chart Style", ["Bar", "Line", "Area"])
                    
                    if chart_type == "Bar": fig = px.bar(df_result, x=x_col, y=y_col, color_discrete_sequence=['#6366f1'])
                    elif chart_type == "Line": fig = px.line(df_result, x=x_col, y=y_col, color_discrete_sequence=['#6366f1'])
                    else: fig = px.area(df_result, x=x_col, y=y_col, color_discrete_sequence=['#6366f1'])
                    
                    fig.update_layout(
                        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#cbd5e1',
                        xaxis=dict(showgrid=True, gridcolor='#1e293b'), yaxis=dict(showgrid=True, gridcolor='#1e293b')
                    )
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"SQL execution error: {str(e)}")


# ==========================================
# PAGE 2: SEC EDGAR CORPORATE FINANCIALS ANALYZER
# ==========================================
def render_sec_page():
    inject_custom_css()
    
    st.subheader("🏢 SEC EDGAR Corporate Financials & Competitor comparison")
    st.markdown("Deep dive into normalized company Balance Sheets, Income Statements, and Cash Flows, and compare performance against sector competitors.")

    # Step 1: Sector selection
    st.markdown("### 🔍 Step 1: Choose Sector")
    sectors = sorted(list(SEC_SECTOR_COMPANIES.keys()))
    selected_sector = st.selectbox("📂 Select Industry Sector to View Competitors", sectors)

    # Step 2: Company Selection (Displays the 5 companies for that sector)
    st.markdown("### 🏢 Step 2: Select Company")
    sector_comps = SEC_SECTOR_COMPANIES[selected_sector]
    
    # Format labels
    company_options = [f"{c[1]} ({c[0]})" for c in sector_comps]
    selected_comp_label = st.selectbox("🏢 Select Primary Company for Deep Dive", company_options)
    
    # Extract ticker and clean name
    ticker_index = company_options.index(selected_comp_label)
    primary_ticker = sector_comps[ticker_index][0]
    primary_name = sector_comps[ticker_index][1]

    # Connect DB to check if financial data is loaded
    try:
        conn = get_connection()
        periods_df = pd.read_sql_query("""
            SELECT DISTINCT fiscal_year, fiscal_quarter 
            FROM fact_company_financials f
            JOIN dim_companies c ON f.company_key = c.company_key
            WHERE c.ticker = ?
            ORDER BY fiscal_year DESC, 
                     CASE fiscal_quarter WHEN 'FY' THEN 4 WHEN 'Q3' THEN 3 WHEN 'Q2' THEN 2 WHEN 'Q1' THEN 1 END DESC
        """, conn, params=(primary_ticker,))
        conn.close()
    except Exception:
        periods_df = pd.DataFrame()

    if periods_df.empty:
        st.warning("Database corporate tables are empty. Please head over to the **Portfolio Analytics** page, select the **ETL DAG Orchestrator** tab, and trigger the ETL pipeline to ingest all SEC filing data.")
        return

    # Step 3: Choose Filings & Period
    st.markdown("### 📅 Step 3: Choose Filings Period")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        report_type = st.radio("Form Type", ["10-K (Annual Reports)", "10-Q (Quarterly Reports)"])
        target_form = "10-K" if "10-K" in report_type else "10-Q"
        
    with col_p2:
        # Filter available periods based on chosen form
        conn = get_connection()
        avail_periods = pd.read_sql_query("""
            SELECT DISTINCT fiscal_year, fiscal_quarter
            FROM fact_company_financials f
            JOIN dim_companies c ON f.company_key = c.company_key
            WHERE c.ticker = ? AND f.form = ?
            ORDER BY fiscal_year DESC, fiscal_quarter DESC
        """, conn, params=(primary_ticker, target_form))
        conn.close()
        
        if not avail_periods.empty:
            period_labels = [f"{r['fiscal_year']}-{r['fiscal_quarter']}" for _, r in avail_periods.iterrows()]
            selected_period = st.selectbox("Select Report Period", period_labels)
            sel_year, sel_quarter = selected_period.split("-")
            sel_year = int(sel_year)
        else:
            st.info("No filings found for this form type.")
            return

    # Step 4: Corporate Financial Deep Dive
    st.markdown(f"## 🏢 Deep Dive: {primary_name} ({primary_ticker}) — {selected_period} ({target_form})")
    
    # Query metrics for the primary company
    conn = get_connection()
    df_metrics = pd.read_sql_query("""
        SELECT f.*
        FROM fact_company_financials f
        JOIN dim_companies c ON f.company_key = c.company_key
        WHERE c.ticker = ? AND f.fiscal_year = ? AND f.fiscal_quarter = ?
    """, conn, params=(primary_ticker, sel_year, sel_quarter))
    conn.close()

    if df_metrics.empty:
        st.info("No records found for the selected company and period.")
        return

    row = df_metrics.iloc[0]
    
    # High-level Statement Tabs
    stmt_tab1, stmt_tab2, stmt_tab3 = st.tabs(["📋 Income Statement", "⚖️ Balance Sheet", "💸 Cash Flow Statement"])
    
    with stmt_tab1:
        st.markdown(f"#### Income Statement Summary ({selected_period})")
        inc_data = {
            "Line Item": ["Total Revenue", "Cost of Revenue", "Gross Profit", "Research & Development (R&D)", "Selling, General & Admin (SG&A)", "Net Income"],
            "Amount": [row['revenue'], row['cost_of_revenue'], row['gross_profit'], row['research_development'], row['selling_general_admin'], row['net_income']]
        }
        df_inc = pd.DataFrame(inc_data)
        df_inc['Formatted Amount'] = df_inc['Amount'].apply(format_currency)
        st.dataframe(df_inc[['Line Item', 'Formatted Amount']], use_container_width=True, hide_index=True)
        
    with stmt_tab2:
        st.markdown(f"#### Balance Sheet Statement ({selected_period})")
        bal_data = {
            "Line Item": ["Total Assets", "Total Liabilities", "Total Shareholders' Equity"],
            "Amount": [row['total_assets'], row['total_liabilities'], row['total_equity']]
        }
        df_bal = pd.DataFrame(bal_data)
        df_bal['Formatted Amount'] = df_bal['Amount'].apply(format_currency)
        st.dataframe(df_bal[['Line Item', 'Formatted Amount']], use_container_width=True, hide_index=True)
        st.markdown("*Note: The Balance Sheet equation ($Assets = Liabilities + Equity$) is verified and balanced automatically during ETL transformation.*")
        
    with stmt_tab3:
        st.markdown(f"#### Cash Flow Statement ({selected_period})")
        cf_data = {
            "Line Item": ["Operating Cash Flow", "Capital Expenditures (CapEx)", "Free Cash Flow (FCF)"],
            "Amount": [row['operating_cash_flow'], row['capex'], row['free_cash_flow']]
        }
        df_cf = pd.DataFrame(cf_data)
        df_cf['Formatted Amount'] = df_cf['Amount'].apply(format_currency)
        st.dataframe(df_cf[['Line Item', 'Formatted Amount']], use_container_width=True, hide_index=True)

    # -----------------------------------------
    # Competitor Comparison Section
    # -----------------------------------------
    st.markdown("---")
    st.markdown("### 📊 Competitor Comparison Benchmarks")
    st.markdown(f"Comparing the 5 companies in the **{selected_sector}** sector for **{selected_period}**:")

    # Load all competitor metrics in sector for selected period
    conn = get_connection()
    df_all_sector = pd.read_sql_query("""
        SELECT c.ticker, c.name, f.*
        FROM fact_company_financials f
        JOIN dim_companies c ON f.company_key = c.company_key
        WHERE c.sector = ? AND f.fiscal_year = ? AND f.fiscal_quarter = ?
    """, conn, params=(selected_sector, sel_year, sel_quarter))
    conn.close()

    if len(df_all_sector) < 2:
        st.info("Additional competitor data for this period is not available.")
    else:
        # Calculate key ratios
        df_all_sector['Gross Margin (%)'] = (df_all_sector['gross_profit'] / df_all_sector['revenue']) * 100
        df_all_sector['Net Margin (%)'] = (df_all_sector['net_income'] / df_all_sector['revenue']) * 100
        df_all_sector['R&D Intensity (%)'] = (df_all_sector['research_development'] / df_all_sector['revenue']) * 100
        df_all_sector['Debt to Equity'] = df_all_sector['total_liabilities'] / df_all_sector['total_equity']
        
        # Grid layout for charts
        col_ch1, col_ch2 = st.columns(2)
        
        with col_ch1:
            # Revenue Comparison Bar chart
            fig_rev = px.bar(
                df_all_sector, x='ticker', y='revenue', 
                title="Topline Revenue Comparison ($)",
                labels={'revenue': 'Revenue ($)', 'ticker': 'Company Ticker'},
                color='ticker', color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_rev.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#cbd5e1')
            st.plotly_chart(fig_rev, use_container_width=True)

            # R&D intensity chart
            fig_rd = px.bar(
                df_all_sector, x='ticker', y='R&D Intensity (%)',
                title="Research & Development Intensity (% of Revenue)",
                labels={'R&D Intensity (%)': 'R&D/Revenue (%)'},
                color='ticker', color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_rd.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#cbd5e1')
            st.plotly_chart(fig_rd, use_container_width=True)

        with col_ch2:
            # Profit Margin comparison
            fig_marg = px.bar(
                df_all_sector, x='ticker', y='Net Margin (%)', 
                title="Net Profit Margin Comparison (%)",
                labels={'Net Margin (%)': 'Net Margin (%)', 'ticker': 'Company Ticker'},
                color='ticker', color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_marg.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#cbd5e1')
            st.plotly_chart(fig_marg, use_container_width=True)

            # Debt to Equity risk ratio
            fig_debt = px.bar(
                df_all_sector, x='ticker', y='Debt to Equity',
                title="Leverage Ratio (Debt-to-Equity)",
                labels={'Debt to Equity': 'Debt-to-Equity Ratio'},
                color='ticker', color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_debt.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#cbd5e1')
            st.plotly_chart(fig_debt, use_container_width=True)

        # Tabular comparative grid
        st.markdown("#### Competitors Metrics Reference Table")
        grid_df = df_all_sector[['ticker', 'name', 'revenue', 'net_income', 'GrossMargin' if 'GrossMargin' in df_all_sector.columns else 'Gross Margin (%)', 'Net Margin (%)', 'Debt to Equity', 'free_cash_flow']].copy()
        
        # Format metrics
        grid_df['Revenue'] = grid_df['revenue'].apply(format_currency)
        grid_df['Net Income'] = grid_df['net_income'].apply(format_currency)
        grid_df['Free Cash Flow'] = grid_df['free_cash_flow'].apply(format_currency)
        grid_df['Net Margin'] = grid_df['Net Margin (%)'].apply(lambda x: f"{x:.2f}%")
        grid_df['Gross Margin'] = grid_df['Gross Margin (%)'].apply(lambda x: f"{x:.2f}%")
        grid_df['Debt-to-Equity'] = grid_df['Debt to Equity'].apply(lambda x: f"{x:.2f}")
        
        st.dataframe(
            grid_df[['ticker', 'name', 'Revenue', 'Net Income', 'GrossMargin' if 'GrossMargin' in grid_df.columns else 'Gross Margin', 'Net Margin', 'Debt-to-Equity', 'Free Cash Flow']], 
            use_container_width=True, hide_index=True
        )

    # SEC Edgar Ingestion validation reports
    st.markdown("---")
    st.markdown("### 🛡️ SEC Edgar Tag Quality & Correction Audit")
    st.markdown("Review of validation check logs from corporate filing parsing operations:")
    
    try:
        conn = get_connection()
        sec_logs = pd.read_sql_query("""
            SELECT timestamp, rule_name, status, failure_count, details
            FROM data_quality_logs
            WHERE table_name = 'stg_raw_sec_filings'
            ORDER BY timestamp DESC
            LIMIT 5
        """, conn)
        conn.close()
        
        if not sec_logs.empty:
            def style_sec_status(val):
                color = '#10b981' if val == 'PASSED' else '#ef4444'
                return f'<span style="color:{color}; font-weight:bold;">{val}</span>'
            sec_logs['status'] = sec_logs['status'].apply(style_sec_status)
            st.write(sec_logs.to_html(escape=False, index=False), unsafe_allow_html=True)
            st.markdown("*Note: Unbalanced Balance Sheets and Gross Profit mismatches are corrected during the ETL load. Negative Assets or invalid Net Income reports are automatically skipped from loading.*")
        else:
            st.info("No validation logs available. Run the ETL pipeline to profile SEC raw filings data.")
    except Exception:
        st.info("Database error loading logs.")

# ==========================================
# SIDEBAR NAVIGATION ROUTING
# ==========================================
def main():
    st.sidebar.title("🧭 Navigation")
    page = st.sidebar.radio("Go to Page", ["📊 Portfolio Analytics Workspace", "🏢 SEC Edgar Financials"])
    st.sidebar.markdown("---")

    if page == "📊 Portfolio Analytics Workspace":
        render_portfolio_page()
    else:
        render_sec_page()

if __name__ == "__main__":
    main()
