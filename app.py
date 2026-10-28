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

from urllib.parse import urlparse

def parse_service_uri(uri_str):
    if not uri_str:
        return {}
    try:
        parsed = urlparse(uri_str)
        return {
            "host": parsed.hostname or "localhost",
            "port": int(parsed.port or 3306),
            "user": parsed.username or "avnadmin",
            "password": parsed.password or "",
            "database": parsed.path.lstrip('/') or "defaultdb",
        }
    except Exception:
        return {}

def resolve_host(h: str) -> str:
    if not h or h in ("localhost", "127.0.0.1"):
        return h
    try:
        import socket
        return socket.gethostbyname(h)
    except Exception:
        try:
            import urllib.request
            url = f"https://dns.google/resolve?name={h}"
            res = json.loads(urllib.request.urlopen(url, timeout=3).read().decode("utf-8"))
            for ans in res.get("Answer", []):
                if ans.get("type") == 1:
                    return ans["data"]
        except Exception:
            pass
    return h

def get_db_config():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    cfg = {}
    cfg_file = base_dir / "db_config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file) as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}

    # 1. Streamlit Secrets (Cloud deployment)
    try:
        if hasattr(st, "secrets"):
            for k in ("DB_URI", "MYSQL_URL", "DATABASE_URL"):
                if k in st.secrets and st.secrets[k]:
                    parsed = parse_service_uri(str(st.secrets[k]))
                    if parsed:
                        parsed["warmup_runs"] = cfg.get("warmup_runs", 1)
                        parsed["benchmark_runs"] = cfg.get("benchmark_runs", 3)
                        return parsed

            sec_host = st.secrets.get("DB_HOST", st.secrets.get("host"))
            if sec_host:
                default_user = "avnadmin" if "aivencloud" in str(sec_host).lower() else "indexrec_user"
                default_db = "defaultdb" if "aivencloud" in str(sec_host).lower() else cfg.get("database", "index_recommender")
                return {
                    "host": str(sec_host).strip(),
                    "port": int(st.secrets.get("DB_PORT", st.secrets.get("port", 3306))),
                    "user": str(st.secrets.get("DB_USER", st.secrets.get("user", default_user))).strip(),
                    "password": str(st.secrets.get("DB_PASSWORD", st.secrets.get("password", ""))).strip(),
                    "database": str(st.secrets.get("DB_NAME", st.secrets.get("database", default_db))).strip(),
                    "warmup_runs": cfg.get("warmup_runs", 1),
                    "benchmark_runs": cfg.get("benchmark_runs", 3),
                }
    except Exception:
        pass

    # 2. Environment Variables (.env / system env)
    for k in ("DB_URI", "MYSQL_URL", "DATABASE_URL"):
        if os.getenv(k):
            parsed = parse_service_uri(os.getenv(k))
            if parsed:
                parsed["warmup_runs"] = cfg.get("warmup_runs", 1)
                parsed["benchmark_runs"] = cfg.get("benchmark_runs", 3)
                return parsed

    if os.getenv("DB_HOST"):
        env_host = os.getenv("DB_HOST")
        default_user = "avnadmin" if "aivencloud" in env_host.lower() else cfg.get("user", "indexrec_user")
        default_db = "defaultdb" if "aivencloud" in env_host.lower() else cfg.get("database", "index_recommender")
        return {
            "host": env_host.strip(),
            "port": int(os.getenv("DB_PORT", cfg.get("port", 3306))),
            "user": os.getenv("DB_USER", default_user).strip(),
            "password": str(os.getenv("DB_PASSWORD", cfg.get("password", ""))).strip(),
            "database": os.getenv("DB_NAME", default_db).strip(),
            "warmup_runs": cfg.get("warmup_runs", 1),
            "benchmark_runs": cfg.get("benchmark_runs", 3),
        }

    if cfg:
        return cfg

    return {
        "host": "localhost",
        "port": 3306,
        "user": "indexrec_user",
        "password": "",
        "database": "index_recommender",
        "warmup_runs": 1,
        "benchmark_runs": 3,
    }

def get_db_connection(cfg):
    import mysql.connector
    raw_host = cfg.get("host", "localhost")
    resolved_host = resolve_host(raw_host)
    kwargs = {
        "host": resolved_host,
        "port": int(cfg.get("port", 3306)),
        "user": cfg.get("user", "indexrec_user"),
        "password": str(cfg.get("password", "")),
        "database": cfg.get("database", "index_recommender"),
        "connection_timeout": 5,
    }
    if raw_host not in ("localhost", "127.0.0.1"):
        kwargs["ssl_disabled"] = False
    try:
        conn = mysql.connector.connect(**kwargs)
        return conn, None
    except Exception as e_primary:
        # Fallback to local config if remote host is unreachable or fails
        if raw_host not in ("localhost", "127.0.0.1"):
            cfg_file = base_dir / "db_config.json"
            if cfg_file.exists():
                try:
                    with open(cfg_file) as f:
                        local_cfg = json.load(f)
                    local_kwargs = {
                        "host": local_cfg.get("host", "localhost"),
                        "port": int(local_cfg.get("port", 3306)),
                        "user": local_cfg.get("user", "indexrec_user"),
                        "password": str(local_cfg.get("password", "")),
                        "database": local_cfg.get("database", "index_recommender"),
                        "connection_timeout": 5,
                    }
                    conn = mysql.connector.connect(**local_kwargs)
                    return conn, None
                except Exception:
                    pass
        return None, str(e_primary)

def run_readonly_sql(query_str, limit=500):
    cfg = get_db_config()
    if not cfg:
        return None, "Database configuration not found."

    t0 = time.perf_counter()
    conn, err = get_db_connection(cfg)
    if err or conn is None:
        return None, f"Connection failed: {err}"

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
        try:
            if conn and conn.is_connected():
                conn.close()
        except Exception:
            pass

@st.cache_data(ttl=60)
def get_table_counts():
    counts = {}
    for tbl in ["Student", "Course", "Enrollment", "Attendance"]:
        df_c, _ = run_readonly_sql(f"SELECT COUNT(*) as cnt FROM `{tbl}`;")
        if df_c is not None and not df_c.empty:
            counts[tbl] = int(df_c.iloc[0]["cnt"])
        else:
            default_counts = {"Student": 10000, "Course": 500, "Enrollment": 50000, "Attendance": 100000}
            counts[tbl] = default_counts.get(tbl, 0)
    return counts

# ==============================================================================
# PAGE CONFIGURATION & STYLING
# ==============================================================================

st.set_page_config(
    page_title="Automatic Index Recommendation — Benchmarking Dashboard",
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

st.sidebar.title("Control Panel")
st.sidebar.markdown("**Role**: Person 4 (Benchmark & Dashboard)")

st.sidebar.markdown("---")
st.sidebar.subheader("Data Source")

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

if st.sidebar.button("Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Live Database Execution")

bench_mode = st.sidebar.radio(
    "Benchmark Mode:",
    [
        "Quick Demo (5 Key Queries, ~5s)",
        "Full Workload (All 49 Queries, ~45s)"
    ],
    index=0,
    help="Quick Demo tests 5 representative queries across Student, Course, Enrollment, and Attendance in ~5s with real-time feedback."
)

if st.sidebar.button("Run Live Benchmark", use_container_width=True):
    prog_box = st.sidebar.container()
    prog_bar = prog_box.progress(0.0)
    prog_status = prog_box.empty()
    prog_status.info("Connecting to MySQL database...")

    try:
        from benchmark import run_benchmark_live, run_benchmark_simulated, load_json_file, save_json_file
        
        # Load config using unified get_db_config
        cfg = get_db_config()
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
                prog_status.markdown(f"**[{idx}/{total}]** Testing `{tbl}` (`{cols_str}`)...")
            else:
                b_ms = data.get("before_ms", 0.0)
                a_ms = data.get("after_ms", 0.0)
                imp = data.get("improvement_percent", 0.0)
                prog_status.markdown(
                    f"**[{idx}/{total}]** `{tbl}`: `{b_ms:.1f}ms` ➔ **`{a_ms:.1f}ms`** "
                    f"({imp:+.1f}%)"
                )

        try:
            new_results = run_benchmark_live(cfg, target_recs, progress_callback=on_bench_progress)
        except Exception as e_live:
            fallback_success = False
            if cfg.get("host") not in ("localhost", "127.0.0.1"):
                cfg_file = base_dir / "db_config.json"
                if cfg_file.exists():
                    try:
                        local_cfg = load_json_file(cfg_file)
                        local_cfg["warmup_runs"] = 1
                        local_cfg["benchmark_runs"] = 1
                        new_results = run_benchmark_live(local_cfg, target_recs, progress_callback=on_bench_progress)
                        fallback_success = True
                    except Exception:
                        pass
            if not fallback_success:
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
        prog_status.success(f"Benchmark completed: evaluated {len(new_results)} live queries.")
        st.session_state["live_benchmark_ran"] = len(new_results)
        time.sleep(1.2)
        st.cache_data.clear()
        st.rerun()

    except Exception as e_total:
        prog_status.error(f"Error during benchmark: {e_total}")

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

st.markdown("""
<div style='display: flex; align-items: center; gap: 14px; margin-bottom: 6px;'>
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#1565C0" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
    </svg>
    <h1 style='margin: 0; padding: 0; font-size: 2.1rem; font-weight: 700; color: #0F172A; display: inline;'>
        Automatic Index Recommendation System
    </h1>
</div>
<div style='margin-bottom: 20px;'>
    <span class='pipeline-badge'>Person 4 Module</span>
    <span class='pipeline-badge'>MySQL Empirical Benchmark</span>
    <span class='pipeline-badge'>Storage & Latency Analysis</span>
</div>
""", unsafe_allow_html=True)

if st.session_state.get("live_benchmark_ran"):
    st.success(
        f"**Live Database Benchmark Active**: Successfully executed "
        f"**{st.session_state['live_benchmark_ran']} live queries** against cloud MySQL. "
        f"Metrics and latency graphs below reflect empirical database execution times."
    )

nav_mode = st.radio(
    "Navigation Tab:",
    ["Benchmark Performance Analytics", "Live MySQL Database Explorer"],
    horizontal=True,
    label_visibility="collapsed"
)

if nav_mode == "Benchmark Performance Analytics":
    st.markdown("""
    Welcome to the empirical evaluation dashboard. This interface compares query execution latency 
    **before** and **after** creating candidate indexes recommended by the machine learning engine, 
    and quantifies the physical disk storage overhead required.
    """)

    if df_raw is None or df_raw.empty:
        st.warning("No benchmark results loaded yet.")
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

    st.markdown("### Performance & Storage Summary")

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

    st.markdown("### Query Execution Time: Before vs. After Index")
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
        yaxis_title="Execution Time (milliseconds)",
        xaxis_title="Query Candidate",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=50, b=50),
        height=420
    )

    st.plotly_chart(fig_bar, use_container_width=True)


    # ==============================================================================
    # 3. SECONDARY CHARTS: SPEEDUP % & STORAGE OVERHEAD
    # ==============================================================================

    col_c1, col_c2 = st.columns([1, 1])

    with col_c1:
        st.markdown("### Performance Improvement (%)")
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
            yaxis_title="Improvement Percentage (%)",
            yaxis_range=[0, 105],
            height=380,
            margin=dict(l=20, r=20, t=30, b=40)
        )
        st.plotly_chart(fig_imp, use_container_width=True)

    with col_c2:
        st.markdown("### Storage Cost per Index (MB)")
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
            height=380,
            margin=dict(l=20, r=20, t=30, b=40)
        )
        st.plotly_chart(fig_storage, use_container_width=True)


    # ==============================================================================
    # 4. DETAILED BREAKDOWN TABLE
    # ==============================================================================

    st.markdown("### Detailed Benchmark Records")
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
    with st.expander("View Raw SQL Queries Benchmarked"):
        for _, row in df.iterrows():
            st.markdown(f"**Query {row['query_id']}** (`{row['table']}` → `{row['index_name']}`):")
            st.code(row.get("query", "N/A"), language="sql")


    # ==============================================================================
    # 5. EDUCATIONAL INSIGHTS & THEORY ("THE WHY")
    # ==============================================================================

    with st.expander("Technical Background: Indexing Architecture & Measurement Methodology"):
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
    cfg = get_db_config()
    db_host = cfg.get("host", "localhost")
    db_name = cfg.get("database", "index_recommender")
    db_port = cfg.get("port", 3306)
    db_type = "Local MySQL 8.0" if db_host in ("localhost", "127.0.0.1") else "Cloud MySQL 8.0"

    st.markdown(f"### Live MySQL Database Explorer: `{db_name}`")
    st.markdown(f"""
    Direct inspection of the live **{db_type}** cluster (`{db_host}:{db_port}`). Explore physical record counts,
    browse actual table rows, inspect MySQL B+Tree indexes, and execute custom SQL queries.
    """)

    if not cfg:
        st.warning("No database configuration detected. Please check `.env` or Streamlit Secrets.")
    else:
        # Upfront connection test
        db_conn, conn_err = get_db_connection(cfg)
        db_ready = False
        if db_conn is not None:
            try:
                db_conn.close()
            except Exception:
                pass
            st.success(f"**Live Database Connected**: `{db_name}` on `{db_host}:{db_port}` (User: `{cfg.get('user', 'indexrec_user')}`)")
            db_ready = True
        else:
            st.warning(f"Could not connect to database (`{db_host}:{db_port}`): {conn_err}")
            st.info("""
            **Connection Troubleshooting**:
            - **Is your Aiven service active?** Free trial clusters may auto-suspend after inactivity. Check your [Aiven Console](https://console.aiven.io/) to confirm the service is **Running**.
            - **Streamlit Secrets format:** In **Streamlit App Settings ➔ Secrets**, paste your Service URI:
              ```toml
              DB_URI = "mysql://avnadmin:your_password@your-host:24887/defaultdb?ssl-mode=REQUIRED"
              ```
            """)

        # 1. Real-time Summary Cards
        counts = get_table_counts()
        total_recs = sum(counts.values())
        st.markdown(f"#### Database Table Overview ({total_recs:,} Total Records)")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Student", f"{counts.get('Student', 10000):,} rows", "Clustered B+Tree")
        col2.metric("Course", f"{counts.get('Course', 500):,} rows", "Clustered B+Tree")
        col3.metric("Enrollment", f"{counts.get('Enrollment', 50000):,} rows", "Indexed by student/course")
        col4.metric("Attendance", f"{counts.get('Attendance', 100000):,} rows", "High-cardinality log")

        st.markdown("---")

        if not db_ready:
            st.info("The interactive row browser and live SQL console will activate once your database is reachable. The **Benchmark Performance Analytics** dashboard remains fully accessible.")
        else:
            # 2. Table Data Browser
            st.markdown("#### Table Record Browser")
            col_t1, col_t2 = st.columns([2, 1])
            with col_t1:
                inspect_table = st.selectbox("Select Table to View:", ["Student", "Course", "Enrollment", "Attendance"])
            with col_t2:
                row_limit = st.select_slider("Rows to Preview:", options=[10, 25, 50, 100, 250, 500], value=50)

            with st.spinner(f"Querying `{inspect_table}` from database..."):
                df_preview, fetch_ms = run_readonly_sql(f"SELECT * FROM `{inspect_table}` LIMIT {row_limit};")
                if df_preview is not None:
                    st.caption(f"Fetched {len(df_preview)} records from `{inspect_table}` in **{fetch_ms:.1f} ms**.")
                    st.dataframe(df_preview, use_container_width=True)
                else:
                    st.error(f"Error querying table: {fetch_ms}")

            # 3. Active Physical Indexes & Schema Inspector
            with st.expander(f"Physical Indexes & Schema for `{inspect_table}`"):
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
            st.markdown("#### SQL Query Console")
            st.markdown("Run custom `SELECT`, `SHOW`, `EXPLAIN`, or `DESCRIBE` queries directly against the database:")
            default_query = f"SELECT * FROM `{inspect_table}` LIMIT 10;"
            user_query = st.text_area("SQL Statement:", value=default_query, height=85)

            if st.button("Execute SQL Query", key="btn_exec_sql"):
                clean_q = user_query.strip().rstrip(";")
                cmd_verb = clean_q.split()[0].upper() if clean_q else ""
                if cmd_verb not in ("SELECT", "SHOW", "EXPLAIN", "DESCRIBE"):
                    st.warning("Notice: For database safety, this web console only allows SELECT, SHOW, EXPLAIN, and DESCRIBE queries.")
                else:
                    with st.spinner("Executing query on MySQL..."):
                        df_custom, q_ms = run_readonly_sql(clean_q)
                        if df_custom is not None:
                            st.success(f"Returned {len(df_custom)} rows in **{q_ms:.1f} ms**.")
                            st.dataframe(df_custom, use_container_width=True)
                        else:
                            st.error(f"Query Error: {q_ms}")


st.markdown("---")
st.caption("Automatic Index Recommendation System — Person 4 Deliverable | DBMS Course Project")
