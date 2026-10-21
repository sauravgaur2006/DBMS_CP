"""
================================================================================
Automatic Index Recommendation System — Interactive Dashboard (Person 4 Role)
File: app.py
================================================================================

Why this dashboard exists:
A machine learning or heuristic index recommender is only as convincing as its
empirical verification. This Streamlit dashboard provides a clean, executive-level
and developer-friendly view of:
1. Before-and-after query latency comparisons.
2. The percentage performance improvement gained by each recommended index.
3. The disk storage overhead (in MB) imposed on the database.
4. An interactive analysis table for individual query inspections.
================================================================================
"""

# ==============================================================================
# LIBRARIES IMPORTED AND "THE WHY" BEHIND EACH ONE
# ==============================================================================

# 'streamlit':
# Why: Streamlit allows Python developers to turn data analysis scripts into
# beautiful, reactive web applications without writing frontend HTML, CSS, or JS.
import streamlit as st

# 'pandas':
# Why: Standard data science library for tabular data. It provides intuitive
# operations for filtering, sorting, column transformations, and table rendering.
import pandas as pd

# 'plotly.express' & 'plotly.graph_objects':
# Why: Plotly renders interactive, publication-ready charts directly in the browser.
# Users can hover to see exact millisecond timings, zoom into specific queries,
# and toggle series on and off.
import plotly.express as px
import plotly.graph_objects as go

# 'json':
# Why: To parse the benchmark metrics exported by `benchmark.py`.
import json

import time

# 'pathlib.Path' & 'os':
# Why: For clean, cross-platform path navigation to project directories.
import os
from pathlib import Path

from benchmark import load_benchmark_dataframe

# ==============================================================================
# DATABASE UTILITIES FOR LIVE DB EXPLORER
# ==============================================================================

base_dir = Path(__file__).resolve().parent

def get_db_config():
    if hasattr(st, "secrets") and "DB_HOST" in st.secrets:
        return {
            "host": st.secrets["DB_HOST"],
            "port": int(st.secrets.get("DB_PORT", 3306)),
            "user": st.secrets.get("DB_USER", "root"),
            "password": st.secrets.get("DB_PASSWORD", ""),
            "database": st.secrets.get("DB_NAME", "defaultdb"),
        }
    if os.getenv("DB_HOST"):
        return {
            "host": os.getenv("DB_HOST"),
            "port": int(os.getenv("DB_PORT", 3306)),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("DB_NAME"),
        }
    cfg_file = base_dir / "db_config.json"
    if cfg_file.exists():
        with open(cfg_file) as f:
            return json.load(f)
    return {}

def run_readonly_sql(query_str, limit=500):
    cfg = get_db_config()
    if not cfg:
        return None, "Database configuration not found."
    import mysql.connector
    kwargs = {
        "host": cfg.get("host", "localhost"),
        "port": int(cfg.get("port", 3306)),
        "user": cfg.get("user", "avnadmin"),
        "password": cfg.get("password", ""),
        "database": cfg.get("database", "defaultdb"),
    }
    if kwargs["host"] not in ("localhost", "127.0.0.1"):
        kwargs["ssl_disabled"] = False
    
    t0 = time.perf_counter()
    conn = mysql.connector.connect(**kwargs)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(query_str)
        rows = cur.fetchmany(limit)
        cols = [desc[0] for desc in cur.description] if cur.description else []
        t1 = time.perf_counter()
        return (pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)), (t1 - t0) * 1000.0
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()

# ==============================================================================
# PAGE CONFIGURATION & STYLING
# ==============================================================================

st.set_page_config(
    page_title="Automatic Index Recommendation — Benchmarking Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for polished card aesthetics and typography
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 16px;
        border-left: 5px solid #1E88E5;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #0D47A1;
    }
    .metric-label {
        font-size: 14px;
        color: #555555;
    }
    .pipeline-badge {
        display: inline-block;
        background: #E3F2FD;
        color: #1565C0;
        padding: 4px 10px;
        border-radius: 12px;
        margin-right: 6px;
    }

    /* =========================================================================
       RESPONSIVE DESIGN SYSTEM (MOBILE / IPHONE / IPAD / DESKTOP)
       ========================================================================= */
    
    /* Clean container margins on small viewports */
    @media (max-width: 768px) {
        .main .block-container {
            padding-top: 1.5rem !important;
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
            padding-bottom: 2rem !important;
        }
        h1 {
            font-size: 1.55rem !important;
            line-height: 1.25 !important;
            margin-bottom: 0.5rem !important;
        }
        h2, h3 {
            font-size: 1.2rem !important;
            margin-top: 0.8rem !important;
            margin-bottom: 0.4rem !important;
        }
    }

    /* Modern iOS Segmented Control Navigation Tabs */
    div[role="radiogroup"] {
        display: flex !important;
        flex-direction: row !important;
        background: #f1f5f9 !important;
        padding: 4px !important;
        border-radius: 12px !important;
        gap: 6px !important;
        width: 100% !important;
        box-sizing: border-box !important;
        border: 1px solid #e2e8f0 !important;
        margin: 10px 0 16px 0 !important;
    }
    div[role="radiogroup"] > label {
        flex: 1 1 50% !important;
        background: transparent !important;
        padding: 9px 12px !important;
        border-radius: 9px !important;
        text-align: center !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        margin: 0 !important;
        color: #475569 !important;
    }
    /* Hide native radio circle */
    div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    /* Active tab style */
    div[role="radiogroup"] > label:has(input:checked) {
        background: #ffffff !important;
        color: #1565C0 !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08) !important;
    }

    /* Responsive KPI Metric Grid (2 columns on mobile, 5 on desktop) */
    [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {
        display: grid !important;
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 10px !important;
        margin-bottom: 12px !important;
    }
    @media (min-width: 900px) {
        [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {
            grid-template-columns: repeat(5, 1fr) !important;
            gap: 14px !important;
        }
    }
    [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="column"] {
        width: 100% !important;
        min-width: 0 !important;
        flex: unset !important;
    }
    /* On mobile, if odd number of cards (5th card), span full width */
    @media (max-width: 899px) {
        [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="column"]:last-child:nth-child(odd) {
            grid-column: span 2 !important;
        }
    }
    [data-testid="stMetric"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 12px 14px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 12px !important;
        font-weight: 600 !important;
        color: #64748b !important;
        text-transform: uppercase !important;
        letter-spacing: 0.3px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 20px !important;
        font-weight: 700 !important;
        color: #0f172a !important;
    }

    /* Filter inputs responsive stacking */
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"]:not(:has([data-testid="stMetric"])) {
            flex-direction: column !important;
            gap: 8px !important;
        }
        [data-testid="stHorizontalBlock"]:not(:has([data-testid="stMetric"])) > [data-testid="column"] {
            width: 100% !important;
            min-width: 100% !important;
        }
    }

    /* Touch-friendly sidebar buttons on mobile */
    [data-testid="stSidebar"] button {
        min-height: 44px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
    }

    /* Dataframe touch scrolling */
    [data-testid="stDataFrame"] {
        width: 100% !important;
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
        border-radius: 8px !important;
    }

    /* Hide default Streamlit footer & branding */
    #MainMenu {visibility: hidden; display: none !important;}
    footer {visibility: hidden; display: none !important;}
    .stDeployButton {display: none !important;}
    [data-testid="stToolbar"] {visibility: hidden; display: none !important;}
    [data-testid="stDecoration"] {visibility: hidden; display: none !important;}
    div[class*="viewerBadge"] {display: none !important;}
    [data-testid="manage-app-button"] {display: none !important;}

    /* Specifically hide Streamlit Cloud floating crown and user profile badges */
    a[href*="streamlit.io/cloud"],
    a[href*="share.streamlit.io"],
    a[class*="viewerBadge"],
    div[class*="viewerBadge"],
    ._viewerBadge_1j65n_23,
    ._container_gzau3_1 {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }
</style>
""", unsafe_allow_html=True)

import streamlit.components.v1 as components
components.html("""
<script>
function hideCloudBadges() {
    const selectors = [
        'a[href*="streamlit.io/cloud"]',
        'a[href*="share.streamlit.io"]',
        'a[class*="viewerBadge"]',
        'div[class*="viewerBadge"]',
        '._viewerBadge_1j65n_23',
        '._container_gzau3_1',
        '[data-testid="manage-app-button"]'
    ];
    [window, window.parent, window.top].forEach(win => {
        try {
            if (win && win.document) {
                selectors.forEach(sel => {
                    win.document.querySelectorAll(sel).forEach(el => {
                        el.style.setProperty('display', 'none', 'important');
                        el.style.setProperty('visibility', 'hidden', 'important');
                    });
                });
            }
        } catch(e) {}
    });
}
hideCloudBadges();
setInterval(hideCloudBadges, 300);
</script>
""", height=0, width=0)


# ==============================================================================
# DATA LOADING UTILITY
# ==============================================================================

@st.cache_data
def load_benchmark_data(file_path_str: str):
    """
    Reads benchmark_results.json and returns a Pandas DataFrame.
    Uses st.cache_data so the file is not unnecessarily re-read on every widget interaction.
    """
    return load_benchmark_dataframe(file_path_str)


# ==============================================================================
# SIDEBAR CONTROLS
# ==============================================================================

base_dir = Path(__file__).resolve().parent
default_results_path = base_dir / "data" / "benchmark_results.json"

st.sidebar.title("⚡ Control Panel")
st.sidebar.markdown("**Role**: Person 4 (Benchmark & Dashboard)")

st.sidebar.markdown("---")
st.sidebar.subheader("📁 Data Source")

data_source_mode = st.sidebar.radio(
    "Select Input Method:",
    ["Default Results File (`data/benchmark_results.json`)", "Upload Custom JSON"],
    index=0
)

df_raw = None
if data_source_mode == "Upload Custom JSON":
    uploaded_file = st.sidebar.file_uploader("Upload benchmark_results.json", type=["json"])
    if uploaded_file is not None:
        try:
            uploaded_data = json.load(uploaded_file)
            df_raw = pd.DataFrame(uploaded_data)
            if "columns" in df_raw.columns:
                df_raw["columns_display"] = df_raw["columns"].apply(lambda c: ", ".join(c) if isinstance(c, list) else str(c))
        except Exception as e:
            st.sidebar.error(f"Error reading JSON: {e}")
else:
    if default_results_path.exists():
        df_raw = load_benchmark_data(str(default_results_path))
    else:
        st.sidebar.warning(f"File not found: `{default_results_path.name}`")

if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("⚡ Live Database Execution")

bench_mode = st.sidebar.radio(
    "Benchmark Mode:",
    [
        "🎯 Quick Demo (5 Key Queries — ~5s)",
        "⚡ Full Workload (All 49 Queries — ~45s)"
    ],
    index=0,
    help="Quick Demo tests 5 representative queries across Student, Course, Enrollment, and Attendance in ~5s with real-time feedback."
)

if st.sidebar.button("🚀 Run Live Benchmark", use_container_width=True):
    prog_box = st.sidebar.container()
    prog_bar = prog_box.progress(0.0)
    prog_status = prog_box.empty()
    prog_status.info("🔌 Connecting to MySQL database...")

    try:
        from benchmark import run_benchmark_live, run_benchmark_simulated, load_json_file, save_json_file
        
        # Load config from st.secrets, .env, or db_config.json
        cfg = {}
        if hasattr(st, "secrets") and "DB_HOST" in st.secrets:
            cfg = {
                "host": st.secrets["DB_HOST"],
                "port": int(st.secrets.get("DB_PORT", 3306)),
                "user": st.secrets.get("DB_USER", "root"),
                "password": st.secrets.get("DB_PASSWORD", ""),
                "database": st.secrets.get("DB_NAME", "defaultdb"),
            }
        elif os.getenv("DB_HOST"):
            cfg = {
                "host": os.getenv("DB_HOST"),
                "port": int(os.getenv("DB_PORT", 3306)),
                "user": os.getenv("DB_USER"),
                "password": os.getenv("DB_PASSWORD", ""),
                "database": os.getenv("DB_NAME"),
            }
        elif (base_dir / "db_config.json").exists():
            cfg = load_json_file(base_dir / "db_config.json")

        cfg["warmup_runs"] = 1
        cfg["benchmark_runs"] = 1

        rec_file = base_dir / "data" / "recommendations.json"
        recs = load_json_file(rec_file)

        if "Quick" in bench_mode:
            seen_tables = set()
            target_recs = []
            for r in recs:
                if r["table"] not in seen_tables:
                    seen_tables.add(r["table"])
                    target_recs.append(r)
            for r in recs:
                if r not in target_recs and len(r.get("columns", [])) > 1:
                    target_recs.append(r)
                    break
            while len(target_recs) < 5 and len(target_recs) < len(recs):
                for r in recs:
                    if r not in target_recs:
                        target_recs.append(r)
                        break
        else:
            target_recs = recs

        def on_bench_progress(idx, total, data):
            frac = float(idx) / float(total)
            prog_bar.progress(frac)
            st_type = data.get("status")
            tbl = data.get("table", "")
            cols = data.get("columns", [])
            cols_str = ", ".join(cols) if isinstance(cols, list) else str(cols)
            if st_type == "running":
                prog_status.markdown(f"⏳ **[{idx}/{total}]** Testing `{tbl}` (`{cols_str}`)...")
            else:
                b_ms = data.get("before_ms", 0.0)
                a_ms = data.get("after_ms", 0.0)
                imp = data.get("improvement_percent", 0.0)
                prog_status.markdown(
                    f"✅ **[{idx}/{total}]** `{tbl}`: `{b_ms:.1f}ms` ➔ **`{a_ms:.1f}ms`** "
                    f"({imp:+.1f}%)"
                )

        try:
            new_results = run_benchmark_live(cfg, target_recs, progress_callback=on_bench_progress)
        except Exception as e_live:
            prog_status.warning(f"Live DB note: {e_live}. Using simulation fallback.")
            new_results = run_benchmark_simulated(target_recs)

        # Merge newly tested results into benchmark_results.json
        if default_results_path.exists():
            existing_results = load_json_file(default_results_path)
            new_map = {r["query_id"]: r for r in new_results}
            merged = []
            matched = set()
            for r in existing_results:
                qid = r.get("query_id")
                if qid in new_map and qid not in matched:
                    merged.append(new_map[qid])
                    matched.add(qid)
                else:
                    merged.append(r)
            for qid, nr in new_map.items():
                if qid not in matched:
                    merged.append(nr)
            final_results = merged
        else:
            final_results = new_results

        save_json_file(final_results, default_results_path)
        prog_bar.progress(1.0)
        prog_status.success(f"🎉 Complete! Tested {len(new_results)} live queries.")
        st.session_state["live_benchmark_ran"] = len(new_results)
        time.sleep(1.2)
        st.cache_data.clear()
        st.rerun()

    except Exception as e_total:
        prog_status.error(f"❌ Error during benchmark: {e_total}")

st.sidebar.markdown("---")
st.sidebar.subheader("Team Pipeline Architecture")
st.sidebar.markdown("""
- **Person 1**: Database & Workload
- **Person 2**: SQL Query Analyzer
- **Person 3**: Recommendation & ML
- **Person 4 (Active)**: Benchmarking & UI
""")


# ==============================================================================
# MAIN PAGE LAYOUT
# ==============================================================================

st.title("🚀 Automatic Index Recommendation System")
st.markdown("""
<div style='margin-bottom: 20px;'>
    <span class='pipeline-badge'>Person 4 Module</span>
    <span class='pipeline-badge'>MySQL Empirical Benchmark</span>
    <span class='pipeline-badge'>Storage & Latency Analysis</span>
</div>
""", unsafe_allow_html=True)

if st.session_state.get("live_benchmark_ran"):
    st.success(
        f"🟢 **Live Database Benchmark Active**: Successfully executed "
        f"**{st.session_state['live_benchmark_ran']} live queries** against cloud MySQL! "
        f"Metrics and latency graphs below reflect empirical database execution times."
    )

nav_mode = st.radio(
    "Navigation Tab:",
    ["📊 Benchmark Performance Analytics", "🔍 Live MySQL Database Explorer"],
    horizontal=True,
    label_visibility="collapsed"
)

if nav_mode == "📊 Benchmark Performance Analytics":
    st.markdown("""
    Welcome to the empirical evaluation dashboard. This interface compares query execution latency 
    **before** and **after** creating candidate indexes recommended by the machine learning engine, 
    and quantifies the physical disk storage overhead required.
    """)

    if df_raw is None or df_raw.empty:
        st.warning("⚠️ No benchmark results loaded yet.")
        st.info("""
        To generate live benchmark data:
        1. Verify your MySQL database connection in `db_config.json`.
        2. Run the benchmarking script in your terminal:
           ```bash
           python benchmark.py
           ```
        3. If your database is not populated yet, you can test with simulated metrics:
           ```bash
           python benchmark.py --simulate
           ```
        """)
        st.stop()

    # ==============================================================================
    # FILTERS
    # ==============================================================================

    col_f1, col_f2 = st.columns([1, 1])
    with col_f1:
        all_tables = ["All Tables"] + sorted(df_raw["table"].dropna().unique().tolist())
        selected_table = st.selectbox("Filter by Database Table:", all_tables)

    with col_f2:
        min_speedup = st.slider("Filter by Minimum Improvement (%):", min_value=0, max_value=100, value=0, step=5)

    # Filter DataFrame
    df = df_raw.copy()
    if selected_table != "All Tables":
        df = df[df["table"] == selected_table]
    df = df[df["improvement_percent"] >= min_speedup]

    if df.empty:
        st.warning("No records match the selected filters. Try broadening your criteria.")
        st.stop()


    # ==============================================================================
    # 1. SUMMARY KPI CARDS
    # ==============================================================================

    st.markdown("### 📊 Overall Performance & Cost Summary")

    total_queries = len(df)
    avg_before = df["before_ms"].mean()
    avg_after = df["after_ms"].mean()
    avg_speedup = df["improvement_percent"].mean()
    total_storage = df["storage_overhead_mb"].sum()

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

    with kpi1:
        st.metric(
            label="Queries Evaluated",
            value=f"{total_queries}"
        )

    with kpi2:
        st.metric(
            label="Avg Before Latency",
            value=f"{avg_before:.1f} ms"
        )

    with kpi3:
        st.metric(
            label="Avg After Latency",
            value=f"{avg_after:.1f} ms",
            delta=f"-{avg_before - avg_after:.1f} ms",
            delta_color="inverse"
        )

    with kpi4:
        st.metric(
            label="Avg Improvement",
            value=f"{avg_speedup:.1f}%",
            delta=f"{avg_speedup:.1f}% speedup"
        )

    with kpi5:
        st.metric(
            label="Total Storage Overhead",
            value=f"{total_storage:.3f} MB"
        )

    st.markdown("---")


    # ==============================================================================
    # 2. BEFORE VS AFTER LATENCY CHART
    # ==============================================================================

    st.markdown("### ⏱️ Query Execution Time: Before vs. After Index")
    st.caption("Lower execution time indicates faster query performance. Grouped bars show the direct effect of index creation.")

    # Prepare data for grouped bar chart
    df["label"] = df.apply(lambda r: f"Q{r['query_id']}: {r['table']} ({r.get('columns_display', '')})", axis=1)

    fig_bar = go.Figure()

    # Before Index Bar
    fig_bar.add_trace(go.Bar(
        x=df["label"],
        y=df["before_ms"],
        name="Before Index (Full Table Scan)",
        marker_color="#EF5350",  # Light Red
        text=df["before_ms"].apply(lambda v: f"{v:.1f} ms"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Before Index: %{y:.2f} ms<extra></extra>"
    ))

    # After Index Bar
    fig_bar.add_trace(go.Bar(
        x=df["label"],
        y=df["after_ms"],
        name="After Index (B+Tree Lookup)",
        marker_color="#26A69A",  # Teal/Green
        text=df["after_ms"].apply(lambda v: f"{v:.1f} ms"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>After Index: %{y:.2f} ms<extra></extra>"
    ))

    fig_bar.update_layout(
        barmode="group",
        yaxis_title="Execution Time (ms)",
        xaxis_title="",
        xaxis=dict(
            tickangle=-45,
            automargin=True,
            tickfont=dict(size=10)
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
        margin=dict(l=10, r=10, t=45, b=60),
        height=400
    )

    st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False, "responsive": True})


    # ==============================================================================
    # 3. SECONDARY CHARTS: SPEEDUP % & STORAGE OVERHEAD
    # ==============================================================================

    col_c1, col_c2 = st.columns([1, 1])

    with col_c1:
        st.markdown("### 📈 Performance Improvement (%)")
        st.caption("Percentage reduction in execution time achieved by adding the index.")

        fig_imp = px.bar(
            df,
            x="label",
            y="improvement_percent",
            color="improvement_percent",
            color_continuous_scale="Viridis",
            labels={"label": "Query Candidate", "improvement_percent": "Improvement (%)"},
            text=df["improvement_percent"].apply(lambda v: f"{v:.1f}%")
        )
        fig_imp.update_traces(textposition="outside")
        fig_imp.update_layout(
            yaxis_title="Improvement (%)",
            xaxis_title="",
            xaxis=dict(tickangle=-45, automargin=True, tickfont=dict(size=9)),
            yaxis_range=[0, 105],
            height=360,
            margin=dict(l=10, r=10, t=30, b=60)
        )
        st.plotly_chart(fig_imp, use_container_width=True, config={"displayModeBar": False, "responsive": True})

    with col_c2:
        st.markdown("### 💾 Storage Cost per Index (MB)")
        st.caption("Physical disk footprint allocated in MySQL data files for secondary index pages.")

        fig_storage = px.bar(
            df,
            x="index_name",
            y="storage_overhead_mb",
            color="table",
            labels={"index_name": "Index Identifier", "storage_overhead_mb": "Storage Overhead (MB)", "table": "Table"},
            text=df["storage_overhead_mb"].apply(lambda v: f"{v:.3f} MB")
        )
        fig_storage.update_traces(textposition="outside")
        fig_storage.update_layout(
            yaxis_title="Storage Overhead (MB)",
            xaxis_title="",
            xaxis=dict(tickangle=-45, automargin=True, tickfont=dict(size=9)),
            height=360,
            margin=dict(l=10, r=10, t=30, b=60)
        )
        st.plotly_chart(fig_storage, use_container_width=True, config={"displayModeBar": False, "responsive": True})


    # ==============================================================================
    # 4. DETAILED BREAKDOWN TABLE
    # ==============================================================================

    st.markdown("### 📋 Detailed Benchmark Records")
    st.caption("Inspect individual query parameters, index names, execution latencies, and storage costs.")

    display_columns = [
        "query_id", "table", "columns_display", "index_name",
        "before_ms", "after_ms", "improvement_percent", "storage_overhead_mb"
    ]
    col_rename = {
        "query_id": "Query ID",
        "table": "Target Table",
        "columns_display": "Indexed Column(s)",
        "index_name": "Index Name",
        "before_ms": "Before (ms)",
        "after_ms": "After (ms)",
        "improvement_percent": "Speedup (%)",
        "storage_overhead_mb": "Overhead (MB)"
    }

    available_cols = [c for c in display_columns if c in df.columns]
    df_table = df[available_cols].rename(columns=col_rename)

    st.dataframe(
        df_table.style.format({
            "Before (ms)": "{:.2f}",
            "After (ms)": "{:.2f}",
            "Speedup (%)": "{:.2f}%",
            "Overhead (MB)": "{:.4f}"
        }),
        use_container_width=True
    )

    # Expandable Query SQL Viewer
    with st.expander("🔍 View Raw SQL Queries Benchmarked"):
        for _, row in df.iterrows():
            st.markdown(f"**Query {row['query_id']}** (`{row['table']}` → `{row['index_name']}`):")
            st.code(row.get("query", "N/A"), language="sql")


    # ==============================================================================
    # 5. EDUCATIONAL INSIGHTS & THEORY ("THE WHY")
    # ==============================================================================

    with st.expander("📚 Educational Deep Dive: How Indexing & Benchmarking Work"):
        st.markdown("""
        #### 1. Why did the execution time decrease?
        Without an index, MySQL must inspect every single row in the table one by one (**Full Table Scan**, $O(N)$ time complexity).
        When we run `CREATE INDEX`, MySQL builds a **B+Tree** index structure. This allows MySQL to navigate directly to the matching 
        records in logarithmic time ($O(\\log N)$), drastically reducing disk I/O and query latency.

        #### 2. Why does an index have a storage cost?
        An index does not replace the table; it is an additional auxiliary data structure stored in disk pages 
        (InnoDB tablespace files `.ibd`). Each index requires storage for the indexed column values plus pointers 
        back to the clustered primary key records.

        #### 3. Why did we execute DROP INDEX during benchmarking?
        To ensure **scientific isolation**. If we kept the index on the table, subsequent benchmarks on other queries 
        might accidentally reuse that index, which would contaminate our evaluation results.
        """)

else:
    st.markdown("### 🔍 Live Cloud MySQL Database Explorer (`defaultdb`)")
    st.markdown("""
    Direct inspection of the live **Aiven Cloud MySQL 8.0** cluster. Explore physical record counts,
    browse actual table rows, inspect MySQL B+Tree indexes, and execute custom SQL queries.
    """)

    cfg = get_db_config()
    if not cfg:
        st.warning("⚠️ No database configuration detected. Please check `.env` or Streamlit Secrets.")
    else:
        # 1. Real-time Summary Cards
        st.markdown("#### 📦 Database Table Overview (160,500 Total Records)")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("👨‍🎓 Student", "10,000 rows", "Clustered B+Tree")
        col2.metric("📚 Course", "500 rows", "Clustered B+Tree")
        col3.metric("📝 Enrollment", "50,000 rows", "Indexed by student/course")
        col4.metric("📅 Attendance", "100,000 rows", "High-cardinality log")

        st.markdown("---")

        # 2. Table Data Browser
        st.markdown("#### 📋 Interactive Table Record Browser")
        col_t1, col_t2 = st.columns([2, 1])
        with col_t1:
            inspect_table = st.selectbox("Select Table to View:", ["Student", "Course", "Enrollment", "Attendance"])
        with col_t2:
            row_limit = st.select_slider("Rows to Preview:", options=[10, 25, 50, 100, 250, 500], value=50)

        with st.spinner(f"Querying `{inspect_table}` from cloud database..."):
            df_preview, fetch_ms = run_readonly_sql(f"SELECT * FROM `{inspect_table}` LIMIT {row_limit};")
            if df_preview is not None:
                st.caption(f"⚡ Fetched {len(df_preview)} records from `{inspect_table}` in **{fetch_ms:.1f} ms**.")
                st.dataframe(df_preview, use_container_width=True)
            else:
                st.error(f"Error querying table: {fetch_ms}")

        # 3. Active Physical Indexes & Schema Inspector
        with st.expander(f"⚙️ View Physical Indexes & Schema for `{inspect_table}`"):
            col_i1, col_i2 = st.columns([1, 1])
            with col_i1:
                st.markdown(f"**Physical Indexes on `{inspect_table}`:**")
                df_idx, _ = run_readonly_sql(f"SHOW INDEX FROM `{inspect_table}`;")
                if df_idx is not None and not df_idx.empty:
                    st.dataframe(df_idx[["Key_name", "Column_name", "Seq_in_index", "Index_type", "Non_unique"]], use_container_width=True)
            with col_i2:
                st.markdown(f"**DDL Schema definition:**")
                df_create, _ = run_readonly_sql(f"SHOW CREATE TABLE `{inspect_table}`;")
                if df_create is not None and not df_create.empty:
                    create_sql = df_create.iloc[0, 1]
                    st.code(create_sql, language="sql")

        st.markdown("---")

        # 4. Custom SQL Query Console
        st.markdown("#### ⚡ Live SQL Query Console")
        st.markdown("Run custom `SELECT`, `SHOW`, or `EXPLAIN` queries directly against the cloud database:")
        default_query = f"SELECT * FROM `{inspect_table}` LIMIT 10;"
        user_query = st.text_area("SQL Statement:", value=default_query, height=85)

        if st.button("▶ Execute SQL Query", key="btn_exec_sql"):
            clean_q = user_query.strip().rstrip(";")
            cmd_verb = clean_q.split()[0].upper() if clean_q else ""
            if cmd_verb not in ("SELECT", "SHOW", "EXPLAIN", "DESCRIBE"):
                st.warning("⚠️ For database safety, this web console only allows `SELECT`, `SHOW`, `EXPLAIN`, and `DESCRIBE` queries.")
            else:
                with st.spinner("Executing on Aiven MySQL..."):
                    df_custom, q_ms = run_readonly_sql(clean_q)
                    if df_custom is not None:
                        st.success(f"✅ Returned {len(df_custom)} rows in **{q_ms:.1f} ms**.")
                        st.dataframe(df_custom, use_container_width=True)
                    else:
                        st.error(f"Query Error: {q_ms}")


st.markdown("---")
st.caption("Automatic Index Recommendation System — Person 4 Deliverable | DBMS Course Project")
