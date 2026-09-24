"""
HBR Pallet Sorting -- interactive dashboard.

Run with: streamlit run app.py
"""
import streamlit as st
import pandas as pd

from data_generator import generate_pallets
from models import build_rack
from simulation import run_simulation
from analysis import (
    pallets_to_dataframe, top_kpis, pallets_by_weight_category,
    tier_wise_distribution, rack_utilization_by_tier_pct,
    throughput_over_time, avg_handling_time_by_category,
)

st.set_page_config(page_title="HBR Pallet Sorting", layout="wide")
st.title("Warehouse HBR Pallet Sorting")
st.caption("Weight-based slotting + deadline-driven retrieval scheduling (single-deep racking)")

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
st.sidebar.header("Simulation settings")
n_pallets = st.sidebar.slider("Number of pallets", 20, 1500, 300, step=10)
st.sidebar.subheader("Rack capacity (slots per tier)")
t1_cap = st.sidebar.slider("Tier 1 (heavy)", 1, 150, 25)
t2_cap = st.sidebar.slider("Tier 2 (medium)", 1, 150, 25)
t3_cap = st.sidebar.slider("Tier 3 (light)", 1, 150, 25)
st.sidebar.subheader("Arrival & deadline pattern")
arr_min, arr_max = st.sidebar.slider("Arrival interval (min)", 1, 20, (2, 8))
lead_min, lead_max = st.sidebar.slider("Line lead time / deadline window (min)", 5, 300, (30, 180))
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
    weight_counts = pallets_by_weight_category(df)
    st.bar_chart(weight_counts)

with row1_right:
    st.subheader("2. Tier-wise Pallet Distribution")
    st.bar_chart(tier_wise_distribution(df))  # stacked by default with multiple columns

row2_left, row2_right = st.columns(2)

with row2_left:
    st.subheader("3. Rack Utilization by Tier (%)")
    st.bar_chart(rack_utilization_by_tier_pct(occ_history))

with row2_right:
    st.subheader("5. Avg Handling Time by Weight Category")
    st.bar_chart(avg_handling_time_by_category(df))

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
occ_left, occ_right = st.columns(2)
with occ_left:
    if level_cols and len(occ_history) > 1:
        st.line_chart(occ_history.set_index("time")[level_cols])
with occ_right:
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
