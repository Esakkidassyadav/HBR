"""
HBR Pallet Sorting -- interactive dashboard.

Run with: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import altair as alt

from data_generator import generate_pallets
from models import build_rack
from simulation import run_simulation
from analysis import (
    pallets_to_dataframe, top_kpis, pallets_by_weight_category,
    tier_wise_distribution, rack_utilization_by_tier_pct,
    throughput_over_time,
)

CATEGORY_ORDER = ["Heavy", "Medium", "Light"]
CATEGORY_COLORS = {"Heavy": "#4c78a8", "Medium": "#72b7b2", "Light": "#9ecae9"}


def ordered_bar(series: pd.Series, value_label: str):
    """Bar chart that keeps CATEGORY_ORDER instead of Streamlit's default
    alphabetical sort (which otherwise renders Heavy/Light/Medium)."""
    chart_df = series.reindex(CATEGORY_ORDER).reset_index()
    chart_df.columns = ["weight_category", value_label]
    chart = alt.Chart(chart_df).mark_bar().encode(
        x=alt.X("weight_category", sort=CATEGORY_ORDER, title=None),
        y=alt.Y(value_label, title=None),
        color=alt.Color("weight_category", sort=CATEGORY_ORDER,
                         scale=alt.Scale(domain=CATEGORY_ORDER,
                                          range=[CATEGORY_COLORS[c] for c in CATEGORY_ORDER]),
                         legend=None),
    )
    st.altair_chart(chart, use_container_width=True)


st.set_page_config(page_title="HBR Pallet Sorting", layout="wide")
st.title("Warehouse HBR Pallet Sorting")
st.caption("Weight-based slotting + deadline-driven retrieval scheduling (single-deep racking)")

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
st.sidebar.header("Simulation settings")
n_pallets = st.sidebar.slider("Number of pallets", 20, 1500, 500, step=10)
st.sidebar.subheader("Rack capacity (slots per tier)")
t1_cap = st.sidebar.slider("Tier 1 (heavy)", 1, 150, 8)
t2_cap = st.sidebar.slider("Tier 2 (medium)", 1, 150, 8)
t3_cap = st.sidebar.slider("Tier 3 (light)", 1, 150, 8)
st.sidebar.subheader("Arrival & deadline pattern")
arr_min, arr_max = st.sidebar.slider("Arrival interval (min)", 1, 20, (2, 8))
lead_min, lead_max = st.sidebar.slider("Line lead time / deadline window (min)", 5, 300, (60, 240))
hwc_pct = st.sidebar.slider("Handle-with-care %", 0, 50, 15)
misplacement_pct = st.sidebar.slider("Sorting error rate %", 0.0, 15.0, 3.2, step=0.1)
seed = st.sidebar.number_input("Random seed", value=42, step=1)

run_btn = st.sidebar.button("Run simulation", type="primary")

if run_btn or "df" not in st.session_state:
    pallets = generate_pallets(
        n_pallets=n_pallets,
        arrival_interval_minutes=(arr_min, arr_max),
        line_lead_time_minutes=(lead_min, lead_max),
        hwc_probability=hwc_pct / 100,
        seed=int(seed),
    )
    rack = build_rack({"Tier 1": t1_cap, "Tier 2": t2_cap, "Tier 3": t3_cap})
    log, pallets, rack, occupancy_history = run_simulation(
        pallets, rack, misplacement_probability=misplacement_pct / 100, seed=int(seed),
    )
    df = pallets_to_dataframe(pallets)
    st.session_state["df"] = df
    st.session_state["occ_history"] = pd.DataFrame(occupancy_history)

df = st.session_state["df"]
occ_history = st.session_state["occ_history"]
kpis = top_kpis(df, occ_history)

# ---------------------------------------------------------------------------
# 5 KPI number cards
# ---------------------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Pallets Processed", f"{kpis['total_pallets_processed']:,}")
c2.metric("Sorting Accuracy", f"{kpis['sorting_accuracy_pct']}%" if kpis["sorting_accuracy_pct"] is not None else "—")
c3.metric("HBR Utilization", f"{kpis['hbr_utilization_pct']}%" if kpis["hbr_utilization_pct"] is not None else "—")
c4.metric("Average Handling Time", f"{kpis['avg_handling_time_sec']} sec" if kpis["avg_handling_time_sec"] is not None else "—")
c5.metric("Misplacement Rate", f"{kpis['misplacement_rate_pct']}%" if kpis["misplacement_rate_pct"] is not None else "—")

st.divider()

# ---------------------------------------------------------------------------
# 5 charts
# ---------------------------------------------------------------------------
row1_left, row1_right = st.columns(2)

with row1_left:
    st.subheader("1. Pallets by Weight Category")
    donut_df = pallets_by_weight_category(df).reindex(CATEGORY_ORDER).reset_index()
    donut_df.columns = ["weight_category", "count"]
    donut = alt.Chart(donut_df).mark_arc(innerRadius=60).encode(
        theta="count",
        color=alt.Color("weight_category", sort=CATEGORY_ORDER,
                         scale=alt.Scale(domain=CATEGORY_ORDER,
                                          range=[CATEGORY_COLORS[c] for c in CATEGORY_ORDER])),
        tooltip=["weight_category", "count"],
    )
    st.altair_chart(donut, use_container_width=True)

with row1_right:
    st.subheader("2. Tier-wise Pallet Distribution")
    tier_dist = tier_wise_distribution(df).reset_index().melt(
        id_vars="rack_tier", var_name="weight_category", value_name="count")
    stacked = alt.Chart(tier_dist).mark_bar().encode(
        x=alt.X("rack_tier", title=None),
        y=alt.Y("count", title=None),
        color=alt.Color("weight_category", sort=CATEGORY_ORDER,
                         scale=alt.Scale(domain=CATEGORY_ORDER,
                                          range=[CATEGORY_COLORS[c] for c in CATEGORY_ORDER])),
        order=alt.Order("weight_category", sort="ascending"),
    )
    st.altair_chart(stacked, use_container_width=True)

row2_left, row2_right = st.columns(2)

with row2_left:
    st.subheader("3. Rack Utilization by Tier (%)")
    util = rack_utilization_by_tier_pct(occ_history).reset_index()
    util.columns = ["tier", "utilization_pct"]

    def threshold_color(pct):
        if pct >= 85:
            return "#e15759"   # red -- near capacity, risk of staging overflow
        if pct >= 70:
            return "#f2b134"   # amber -- busy
        return "#59a14f"        # green -- healthy headroom
    util["color"] = util["utilization_pct"].apply(threshold_color)

    util_chart = alt.Chart(util).mark_bar().encode(
        y=alt.Y("tier", sort=None, title=None),
        x=alt.X("utilization_pct", title="% utilized", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("color", scale=None, legend=None),
        tooltip=["tier", "utilization_pct"],
    )
    st.altair_chart(util_chart, use_container_width=True)
    st.caption("🟢 <70%   🟠 70-85%   🔴 85%+ (capacity risk)")

with row2_right:
    st.subheader("5. Handling Time by Weight Category")
    box_df = df[["weight_category", "handling_time_sec"]].dropna()
    box = alt.Chart(box_df).mark_boxplot(extent="min-max").encode(
        x=alt.X("weight_category", sort=CATEGORY_ORDER, title=None),
        y=alt.Y("handling_time_sec", title="seconds"),
        color=alt.Color("weight_category", sort=CATEGORY_ORDER,
                         scale=alt.Scale(domain=CATEGORY_ORDER,
                                          range=[CATEGORY_COLORS[c] for c in CATEGORY_ORDER]),
                         legend=None),
    )
    st.altair_chart(box, use_container_width=True)
    st.caption("Box = middle 50% of pallets, whiskers = full range including outliers (jams/re-attempts)")

st.subheader("4. Pallet Throughput Over Time")
freq_choice = st.radio("Bucket by", ["Hour", "Day"], horizontal=True)
throughput = throughput_over_time(df, freq="h" if freq_choice == "Hour" else "D")
if len(throughput):
    st.line_chart(throughput)
else:
    st.info("No retrieval data yet.")

st.divider()

# ---------------------------------------------------------------------------
# Occupancy over time (operational view)
# ---------------------------------------------------------------------------
st.subheader("Rack occupancy & staging queue over time")
level_cols = [c for c in occ_history.columns if c.endswith("_occupied")]
TIER_COLORS = {"Tier 1": "#e15759", "Tier 2": "#4c78a8", "Tier 3": "#59a14f"}  # distinct hues, not just shades of blue

occ_left, occ_right = st.columns(2)
with occ_left:
    st.caption("% of each tier's capacity in use -- comparable scale regardless of slot count")
    if level_cols and len(occ_history) > 1:
        pct_df = occ_history[["time"]].copy()
        for col in level_cols:
            tier = col.replace("_occupied", "")
            cap_col = f"{tier}_capacity"
            pct_df[tier] = (100 * occ_history[col] / occ_history[cap_col]).round(1)
        pct_long = pct_df.melt(id_vars="time", var_name="tier", value_name="utilization_pct")
        occ_chart = alt.Chart(pct_long).mark_line().encode(
            x=alt.X("time", title=None),
            y=alt.Y("utilization_pct", title="% utilized", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("tier", scale=alt.Scale(domain=list(TIER_COLORS.keys()),
                                                      range=list(TIER_COLORS.values()))),
        )
        st.altair_chart(occ_chart, use_container_width=True)
with occ_right:
    st.caption("Pallets waiting in staging (no open slot yet)")
    if len(occ_history) > 1:
        st.line_chart(occ_history.set_index("time")["staging_count"])

st.divider()

# ---------------------------------------------------------------------------
# Pallet detail table
# ---------------------------------------------------------------------------
st.subheader("Pallet detail")
cat_filter = st.multiselect("Filter by weight category", options=["Heavy", "Medium", "Light"],
                             default=["Heavy", "Medium", "Light"])
show_flagged = st.checkbox("Show only misplaced / late pallets")

filtered = df[df["weight_category"].isin(cat_filter)]
if show_flagged:
    filtered = filtered[(filtered["missed_deadline"] == True) | (filtered["correctly_sorted"] == False)]  # noqa: E712

st.dataframe(
    filtered[["pallet_id", "weight_category", "weight", "handle_with_care", "rack_tier",
              "staging_wait_min", "handling_time_sec", "correctly_sorted",
              "required_out_time", "retrieved_time", "missed_deadline"]],
    use_container_width=True,
    height=400,
)

st.caption(
    "Tier rule: Heavy -> Tier 1 only, Medium -> Tier 1/2, Light -> Tier 2/3. "
    "Handle-with-care restricted to Tier 1/2. A small % of placements are "
    "deliberately simulated as sorting errors (see sidebar) to model real "
    "operational imperfection. Retrieval priority = earliest required_out_time."
)
