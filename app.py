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

# 'pathlib.Path' & 'os':
# Why: For clean, cross-platform path navigation to project directories.
import os
from pathlib import Path

from benchmark import load_benchmark_dataframe

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
        font-size: 12px;
        font-weight: 600;
        margin-right: 6px;
    }
</style>
""", unsafe_allow_html=True)


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

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

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
        yaxis_title="Improvement Percentage (%)",
        yaxis_range=[0, 105],
        height=380,
        margin=dict(l=20, r=20, t=30, b=40)
    )
    st.plotly_chart(fig_imp, use_container_width=True)

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
        height=380,
        margin=dict(l=20, r=20, t=30, b=40)
    )
    st.plotly_chart(fig_storage, use_container_width=True)


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

st.markdown("---")
st.caption("Automatic Index Recommendation System — Person 4 Deliverable | DBMS Course Project")
