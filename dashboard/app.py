"""
Veridi Logistics — Last Mile Delivery Auditor
Streamlit Dashboard
"""

import json
import os
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# Resolve data directory — try repo path first, fall back to /tmp on read-only filesystems
DATA_DIR = Path(__file__).parent.parent / "data"
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except PermissionError:
    DATA_DIR = Path("/tmp/olist_data")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="Veridi Logistics — Delivery Audit",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global constants ──────────────────────────────────────────────────────────
COLOR_MAP  = {"On Time": "#2ecc71", "Late": "#f39c12", "Super Late": "#e74c3c"}
ORDER_CATS = ["On Time", "Late", "Super Late"]
SCORE_COLORS = {"1.0": "#e74c3c", "2.0": "#e67e22", "3.0": "#f1c40f", "4.0": "#82e0aa", "5.0": "#27ae60"}

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Sidebar styling */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
}
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
[data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] {
    background-color: #0f3460 !important;
    border: 1px solid #e94560 !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #ffffff !important; }
.sidebar-brand {
    text-align: center;
    padding: 1rem 0 0.5rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.15);
    margin-bottom: 1.2rem;
}
.sidebar-brand h2 { font-size: 1.2rem; font-weight: 700; margin: 0; color: #fff !important; }
.sidebar-brand p  { font-size: 0.75rem; color: #a0aec0 !important; margin: 0.2rem 0 0 0; }
.filter-label {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #a0aec0 !important;
    margin-bottom: 0.3rem;
}
.stats-box {
    background: rgba(255,255,255,0.07);
    border-radius: 8px;
    padding: 0.8rem 1rem;
    margin-top: 1.2rem;
    border: 1px solid rgba(255,255,255,0.1);
}
.stats-box p { margin: 0.2rem 0; font-size: 0.8rem; }
/* KPI cards */
[data-testid="metric-container"] {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    border-left: 4px solid #667eea;
}
/* Tab styling */
[data-testid="stTabs"] button { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    try:
        df       = pd.read_parquet(DATA_DIR / "05_delivered_cat.parquet")
        state    = pd.read_parquet(DATA_DIR / "03_state_stats.parquet")
        pipeline = pd.read_parquet(DATA_DIR / "06_pipeline.parquet")
    except FileNotFoundError:
        df, state, pipeline = _process_from_csv()
    return df, state, pipeline


def _ensure_csvs():
    """Download Olist dataset from Kaggle if CSVs are not present (Streamlit Cloud first-run)."""
    if (DATA_DIR / "olist_orders_dataset.csv").exists():
        return

    # Read credentials: Streamlit secrets take priority, then environment variables
    try:
        username = st.secrets["kaggle"]["username"]
        key      = st.secrets["kaggle"]["key"]
    except Exception:
        username = os.environ.get("KAGGLE_USERNAME", "")
        key      = os.environ.get("KAGGLE_KEY", "")

    if not username or not key:
        st.error(
            "Dataset not found and no Kaggle credentials configured.  \n"
            "Add `[kaggle]` `username` and `key` to Streamlit Cloud secrets, "
            "or place the CSVs in the `data/` folder locally."
        )
        st.stop()

    os.environ["KAGGLE_USERNAME"] = username
    os.environ["KAGGLE_KEY"]      = key

    with st.spinner("Downloading Olist dataset from Kaggle — first run only, takes ~30 s..."):
        try:
            import kaggle
            kaggle.api.authenticate()
            kaggle.api.dataset_download_files(
                "olistbr/brazilian-ecommerce",
                path=str(DATA_DIR),
                unzip=True,
                quiet=True,
            )
        except Exception as exc:
            st.error(f"Kaggle download failed: {exc}")
            st.stop()


def _process_from_csv():
    _ensure_csvs()
    orders    = pd.read_csv(DATA_DIR / "olist_orders_dataset.csv")
    reviews   = pd.read_csv(DATA_DIR / "olist_order_reviews_dataset.csv")
    customers = pd.read_csv(DATA_DIR / "olist_customers_dataset.csv")
    products  = pd.read_csv(DATA_DIR / "olist_products_dataset.csv")
    items     = pd.read_csv(DATA_DIR / "olist_order_items_dataset.csv")
    transl    = pd.read_csv(DATA_DIR / "product_category_name_translation.csv", encoding="utf-8-sig")

    reviews["review_creation_date"] = pd.to_datetime(reviews["review_creation_date"])
    reviews_dedup = (
        reviews.sort_values("review_creation_date")
               .drop_duplicates(subset="order_id", keep="first")
               [["order_id", "review_score"]]
    )
    master = (
        orders
        .merge(reviews_dedup, on="order_id", how="left")
        .merge(customers[["customer_id", "customer_state", "customer_city"]], on="customer_id", how="left")
    )
    for col in ["order_purchase_timestamp","order_approved_at","order_delivered_carrier_date",
                "order_delivered_customer_date","order_estimated_delivery_date"]:
        master[col] = pd.to_datetime(master[col])

    df = master[
        (~master["order_status"].isin(["canceled", "unavailable"])) &
        master["order_delivered_customer_date"].notna()
    ].copy()

    df["delivery_delay_days"] = (
        df["order_delivered_customer_date"] - df["order_estimated_delivery_date"]
    ).dt.days
    df["delivery_status"] = df["delivery_delay_days"].apply(
        lambda d: "On Time" if d <= 0 else ("Late" if d <= 5 else "Super Late")
    )

    products_en   = products.merge(transl, on="product_category_name", how="left")
    items_primary = items[["order_id","product_id"]].drop_duplicates(subset="order_id", keep="first")
    items_cat     = items_primary.merge(products_en[["product_id","product_category_name_english"]], on="product_id", how="left")
    df = df.merge(items_cat, on="order_id", how="left")
    df["product_category_name_english"] = (
        df["product_category_name_english"].fillna("Unknown").str.replace("_"," ").str.title()
    )

    state = (
        df.groupby("customer_state")
        .agg(total_orders=("order_id","count"),
             late_orders=("delivery_status", lambda x: (x != "On Time").sum()),
             avg_delay=("delivery_delay_days","mean"),
             avg_review=("review_score","mean"))
        .reset_index()
    )
    state["pct_late"]  = (state["late_orders"] / state["total_orders"] * 100).round(1)
    state["avg_delay"] = state["avg_delay"].round(1)
    state["avg_review"]= state["avg_review"].round(2)

    pipeline = df.dropna(subset=["order_approved_at","order_delivered_carrier_date"]).copy()
    pipeline["processing_days"] = (pipeline["order_approved_at"] - pipeline["order_purchase_timestamp"]).dt.total_seconds() / 86400
    pipeline["warehouse_days"]  = (pipeline["order_delivered_carrier_date"] - pipeline["order_approved_at"]).dt.total_seconds() / 86400
    pipeline["transit_days"]    = (pipeline["order_delivered_customer_date"] - pipeline["order_delivered_carrier_date"]).dt.total_seconds() / 86400
    for col in ["processing_days","warehouse_days","transit_days"]:
        pipeline = pipeline[pipeline[col] >= 0]

    return df, state, pipeline


@st.cache_data
def load_geojson():
    url = ("https://raw.githubusercontent.com/codeforamerica/click_that_hood/"
           "master/public/data/brazil-states.geojson")
    with urllib.request.urlopen(url) as r:
        geo = json.load(r)
    for feat in geo["features"]:
        feat["id"] = feat["properties"].get("sigla", feat["properties"].get("uf", ""))
    return geo


# ── Load data ─────────────────────────────────────────────────────────────────
df, state_stats, pipeline = load_data()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
        <h2>📦 Veridi Logistics</h2>
        <p>Last Mile Delivery Auditor</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<p class="filter-label">🌎 Filter by State</p>', unsafe_allow_html=True)
    all_states = sorted(df["customer_state"].dropna().unique())

    # Session state — key must match the multiselect key so buttons can control it
    if "states_multiselect" not in st.session_state:
        st.session_state["states_multiselect"] = list(all_states)

    col_a, col_b = st.columns(2)
    if col_a.button("All", use_container_width=True):
        st.session_state["states_multiselect"] = list(all_states)
    if col_b.button("Clear", use_container_width=True):
        st.session_state["states_multiselect"] = []

    selected_states = st.multiselect(
        "States", all_states,
        key="states_multiselect",
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown('<p class="filter-label">📊 Delivery Status</p>', unsafe_allow_html=True)
    selected_status = st.multiselect(
        "Status", ORDER_CATS,
        default=ORDER_CATS,
        label_visibility="collapsed",
    )

    # Live stats in sidebar
    filtered_preview = df[
        df["customer_state"].isin(selected_states) &
        df["delivery_status"].isin(selected_status)
    ]
    st.markdown("---")
    if len(filtered_preview) > 0:
        on_pct  = (filtered_preview["delivery_status"] == "On Time").mean() * 100
        la_pct  = (filtered_preview["delivery_status"] == "Late").mean() * 100
        sl_pct  = (filtered_preview["delivery_status"] == "Super Late").mean() * 100
        st.markdown(f"""
        <div class="stats-box">
            <p>📋 <b>Filtered orders</b></p>
            <p style="font-size:1.3rem; font-weight:700; color:#fff !important;">
                {len(filtered_preview):,}
            </p>
            <p>🟢 On Time &nbsp; <b>{on_pct:.1f}%</b></p>
            <p>🟡 Late &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <b>{la_pct:.1f}%</b></p>
            <p>🔴 Super Late <b>{sl_pct:.1f}%</b></p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="stats-box">
            <p>⚠️ <b>No data selected</b></p>
            <p style="font-size:0.8rem; color:#a0aec0 !important;">
                Select at least one state and one delivery status to see results.
            </p>
        </div>
        """, unsafe_allow_html=True)

    # How to use guide
    st.markdown("---")
    with st.expander("ℹ️ How to use"):
        st.markdown("""
**Filters (this panel)**
- **States** — narrow to specific Brazilian regions
- **All / Clear** — quick select or reset
- **Delivery Status** — toggle On Time / Late / Super Late

**Tabs (main area)**
- 🗺️ **Geographic** — map + bar showing which states have most late deliveries
- 😊 **Sentiment** — correlation between delay and review scores
- 📦 **Categories** — which product types are shipped late most often
- ⏱️ **Pipeline** — which phase (warehouse vs transit) causes delays

**Tip:** Click a tab then adjust filters — charts update live.
        """)

# ── Apply filters ─────────────────────────────────────────────────────────────
filtered = df[
    df["customer_state"].isin(selected_states) &
    df["delivery_status"].isin(selected_status)
]

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 📦 Veridi Logistics — Last Mile Delivery Audit")
st.caption("Olist Brazilian E-Commerce Dataset · Delivery Performance Analysis")

# Guard: stop rendering charts if no data selected
if filtered.empty:
    st.divider()
    st.warning("No data to display. Select at least one **State** and one **Delivery Status** in the sidebar.")
    st.stop()
st.divider()

# ── KPI row ───────────────────────────────────────────────────────────────────
total      = len(filtered)
pct_ontime = (filtered["delivery_status"] == "On Time").mean() * 100
pct_late   = (filtered["delivery_status"] == "Late").mean() * 100
pct_slat   = (filtered["delivery_status"] == "Super Late").mean() * 100
avg_review = filtered["review_score"].mean()
avg_delay  = filtered["delivery_delay_days"].mean()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Orders",     f"{total:,}")
c2.metric("On Time",          f"{pct_ontime:.1f}%")
c3.metric("Late",             f"{pct_late:.1f}%",  delta=f"{pct_late:.1f}% late",       delta_color="inverse")
c4.metric("Super Late (>5d)", f"{pct_slat:.1f}%",  delta=f"{pct_slat:.1f}% super late", delta_color="inverse")
c5.metric("Avg Review Score", f"{avg_review:.2f}/5" if not np.isnan(avg_review) else "—")
c6.metric("Avg Delay",        f"{avg_delay:.1f} days" if not np.isnan(avg_delay) else "—")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🗺️  Geographic", "😊  Sentiment", "📦  Categories", "⏱️  Pipeline Breakdown"
])

# ── Tab 1: Geographic ─────────────────────────────────────────────────────────
with tab1:
    # Recompute state stats from the filtered dataset so the map reacts to filters
    geo_stats = (
        filtered.groupby("customer_state")
        .agg(
            total_orders  = ("order_id", "count"),
            late_orders   = ("delivery_status", lambda x: (x != "On Time").sum()),
            avg_delay     = ("delivery_delay_days", "mean"),
            avg_review    = ("review_score", "mean"),
        )
        .reset_index()
    )
    geo_stats["pct_late"]  = (geo_stats["late_orders"] / geo_stats["total_orders"] * 100).round(1)
    geo_stats["avg_delay"] = geo_stats["avg_delay"].round(1)
    geo_stats["avg_review"]= geo_stats["avg_review"].round(2)

    n_selected = len(selected_states)
    title_suffix = f"({n_selected} state{'s' if n_selected != 1 else ''} selected)"
    st.subheader(f"Late Delivery Rate by Brazilian State  {title_suffix}")
    col_map, col_bar = st.columns([3, 2])

    with col_map:
        try:
            geo = load_geojson()
            fig_map = px.choropleth(
                geo_stats, geojson=geo, locations="customer_state",
                color="pct_late", color_continuous_scale="RdYlGn_r",
                range_color=(0, geo_stats["pct_late"].max() if not geo_stats.empty else 1),
                hover_data={"total_orders": True, "avg_delay": True, "avg_review": True},
                labels={"pct_late": "% Late", "customer_state": "State",
                        "total_orders": "Orders", "avg_delay": "Avg Delay (d)", "avg_review": "Avg Review"},
                fitbounds="locations", basemap_visible=False,
            )
            fig_map.update_layout(margin={"r":0,"t":10,"l":0,"b":0}, height=450,
                                  coloraxis_colorbar_title="% Late")
            st.plotly_chart(fig_map, use_container_width=True)
        except Exception:
            st.info("Map unavailable (no internet). See bar chart →")

    with col_bar:
        ss_sorted = geo_stats.sort_values("pct_late", ascending=True)
        bar_height = max(300, len(ss_sorted) * 22)
        fig_bar = px.bar(
            ss_sorted, x="pct_late", y="customer_state", orientation="h",
            color="pct_late", color_continuous_scale="RdYlGn_r",
            range_color=(0, ss_sorted["pct_late"].max() if not ss_sorted.empty else 1),
            text_auto=".1f",
            labels={"pct_late": "% Late", "customer_state": "State"},
            height=bar_height,
        )
        fig_bar.update_traces(texttemplate="%{x:.1f}%", textposition="outside")
        fig_bar.update_layout(showlegend=False, coloraxis_showscale=False, margin={"t":10,"b":10})
        st.plotly_chart(fig_bar, use_container_width=True)

    st.caption("Remote northern states (AM, RR, AC, AP) are disproportionately affected due to distance from São Paulo distribution hubs.")

# ── Tab 2: Sentiment ──────────────────────────────────────────────────────────
with tab2:
    st.subheader("Does Late Delivery Cause Bad Reviews?")
    col_avg, col_dist = st.columns(2)

    with col_avg:
        sentiment = (
            filtered.dropna(subset=["review_score"])
            .groupby("delivery_status")["review_score"].mean()
            .reindex(ORDER_CATS).reset_index()
        )
        sentiment.columns = ["delivery_status", "avg_score"]
        fig_avg = px.bar(
            sentiment, x="delivery_status", y="avg_score",
            color="delivery_status", color_discrete_map=COLOR_MAP,
            text_auto=".2f",
            title="Average Review Score by Delivery Status",
            labels={"avg_score": "Avg Review Score (1–5)", "delivery_status": "Status"},
            range_y=[0, 5.5],
            category_orders={"delivery_status": ORDER_CATS},
        )
        fig_avg.update_traces(showlegend=False)
        overall_avg = filtered["review_score"].mean()
        if not np.isnan(overall_avg):
            fig_avg.add_hline(y=overall_avg, line_dash="dash", line_color="grey",
                              annotation_text=f"Overall avg: {overall_avg:.2f}",
                              annotation_position="top right")
        st.plotly_chart(fig_avg, use_container_width=True)

    with col_dist:
        score_dist = (
            filtered.dropna(subset=["review_score"])
            .groupby(["delivery_status", "review_score"]).size()
            .reset_index(name="count")
        )
        score_dist["review_score"] = score_dist["review_score"].astype(int).astype(str)
        fig_stack = px.bar(
            score_dist, x="delivery_status", y="count",
            color="review_score", barmode="stack",
            color_discrete_map={"1": "#e74c3c", "2": "#e67e22", "3": "#f1c40f", "4": "#82e0aa", "5": "#27ae60"},
            title="Review Score Distribution by Status",
            labels={"count": "Orders", "delivery_status": "Status", "review_score": "Score ★"},
            category_orders={"delivery_status": ORDER_CATS, "review_score": ["1","2","3","4","5"]},
        )
        st.plotly_chart(fig_stack, use_container_width=True)

    st.subheader("Delivery Delay vs Review Score")
    bin_df = filtered.dropna(subset=["review_score"]).copy()
    bin_df["delay_bin"] = pd.cut(bin_df["delivery_delay_days"], bins=range(-40, 100, 3), labels=False)
    bin_summary = (
        bin_df.dropna(subset=["delay_bin"])
        .groupby("delay_bin")
        .agg(avg_review=("review_score","mean"), count=("order_id","count"))
        .reset_index()
    )
    bin_summary["delay_midpoint"] = bin_summary["delay_bin"] * 3 - 40 + 1.5
    fig_scatter = px.scatter(
        bin_summary, x="delay_midpoint", y="avg_review",
        size="count", color="avg_review",
        color_continuous_scale="RdYlGn", range_color=[1, 5],
        title="Average Review Score vs Delivery Delay (bubble size = order volume per 3-day bin)",
        labels={"delay_midpoint": "Delay (days, negative = early)", "avg_review": "Avg Review Score"},
        trendline="lowess",
    )
    fig_scatter.add_vline(x=0, line_dash="dash", line_color="black", annotation_text="Estimated date")
    fig_scatter.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig_scatter, use_container_width=True)

# ── Tab 3: Categories ─────────────────────────────────────────────────────────
with tab3:
    st.subheader("Which Product Categories Have the Most Late Deliveries?")

    if "product_category_name_english" not in filtered.columns:
        st.warning("Category data not available. Run the notebooks first.")
    else:
        cat_df = filtered[~filtered["product_category_name_english"].isin(["Unknown", "unknown"])]
        cat_stats = (
            cat_df.groupby("product_category_name_english")
            .agg(total=("order_id","count"),
                 late=("delivery_status", lambda x: (x != "On Time").sum()),
                 avg_review=("review_score","mean"))
            .reset_index()
        )
        cat_stats["pct_late"]   = (cat_stats["late"] / cat_stats["total"] * 100).round(1)
        cat_stats["avg_review"] = cat_stats["avg_review"].round(2)

        col_s1, col_s2 = st.columns(2)
        min_orders = col_s1.slider("Minimum orders per category", 10, 200, 50)
        top_n      = col_s2.slider("Show top N categories", 10, 40, 20)

        top_cat = (
            cat_stats[cat_stats["total"] >= min_orders]
            .nlargest(top_n, "pct_late")
            .sort_values("pct_late")
        )
        fig_cat = px.bar(
            top_cat, x="pct_late", y="product_category_name_english", orientation="h",
            color="avg_review", color_continuous_scale="RdYlGn", range_color=[1, 5],
            text_auto=".1f",
            labels={"pct_late": "% Late Deliveries",
                    "product_category_name_english": "Category",
                    "avg_review": "Avg Review Score"},
            title=f"Top {top_n} Categories by Late Delivery Rate (min {min_orders} orders)",
            height=max(420, top_n * 24),
        )
        fig_cat.update_traces(texttemplate="%{x:.1f}%", textposition="outside")
        fig_cat.update_layout(coloraxis_colorbar_title="Avg Review")
        st.plotly_chart(fig_cat, use_container_width=True)

# ── Tab 4: Pipeline Breakdown ─────────────────────────────────────────────────
with tab4:
    st.subheader("Where Does the Delay Happen? — Pipeline Phase Analysis")
    st.caption("Decomposes total delivery time into three phases to pinpoint the root cause.")

    pipe_filtered = pipeline[
        pipeline["customer_state"].isin(selected_states) &
        pipeline["delivery_status"].isin(selected_status)
    ]

    phase_by_status = (
        pipe_filtered
        .groupby("delivery_status")[["processing_days","warehouse_days","transit_days"]]
        .mean().reindex(ORDER_CATS).round(1).reset_index()
    )
    phase_melt = phase_by_status.melt(id_vars="delivery_status", var_name="Phase", value_name="Days")
    phase_melt["Phase"] = phase_melt["Phase"].map({
        "processing_days": "Payment Processing",
        "warehouse_days":  "Warehouse → Carrier",
        "transit_days":    "Carrier → Customer (Transit)",
    })

    fig_pipeline = px.bar(
        phase_melt, x="delivery_status", y="Days", color="Phase",
        barmode="stack",
        color_discrete_sequence=["#3498db", "#9b59b6", "#e67e22"],
        title="Average Pipeline Phase Duration by Delivery Status",
        labels={"delivery_status": "Status", "Days": "Average Days"},
        category_orders={"delivery_status": ORDER_CATS},
        text_auto=".1f",
    )
    fig_pipeline.update_traces(textposition="inside", insidetextanchor="middle")
    fig_pipeline.update_layout(legend_title="Pipeline Phase", height=420)
    st.plotly_chart(fig_pipeline, use_container_width=True)

    if (not phase_by_status.empty and
        "On Time" in phase_by_status["delivery_status"].values and
        "Super Late" in phase_by_status["delivery_status"].values):

        on  = phase_by_status[phase_by_status["delivery_status"] == "On Time"].iloc[0]
        sl  = phase_by_status[phase_by_status["delivery_status"] == "Super Late"].iloc[0]
        t_d = sl["transit_days"]   - on["transit_days"]
        w_d = sl["warehouse_days"] - on["warehouse_days"]
        dominant = "Carrier → Customer (Transit)" if t_d > w_d else "Warehouse → Carrier"
        rec = ("Negotiate carrier SLAs or explore alternative logistics providers for high-delay routes."
               if t_d > w_d else
               "Audit internal order fulfilment workflows to reduce warehouse dwell time.")
        st.info(
            f"**Primary delay driver: {dominant}** "
            f"(adds {max(t_d, w_d):.1f} extra days for Super Late vs On Time orders)  \n"
            f"**Recommended action:** {rec}"
        )

    st.subheader("Detailed Phase Averages (days)")
    display_table = phase_by_status.rename(columns={
        "delivery_status": "Status",
        "processing_days": "Payment Processing",
        "warehouse_days":  "Warehouse → Carrier",
        "transit_days":    "Carrier → Customer",
    }).set_index("Status")
    st.dataframe(
        display_table.style.format("{:.1f}").background_gradient(cmap="RdYlGn_r", axis=None),
        use_container_width=True,
    )
