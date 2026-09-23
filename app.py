"""
HBR Pallet Sorting — interactive dashboard.

Run with: streamlit run app.py
"""
import streamlit as st
import pandas as pd

from data_generator import generate_pallets
from models import build_rack
from simulation import run_simulation
from analysis import pallets_to_dataframe, summary_kpis, rack_utilization_by_tier

st.set_page_config(page_title="HBR Pallet Sorting", layout="wide")
st.title("Warehouse HBR Pallet Sorting")
st.caption("Weight-based slotting + deadline-driven retrieval scheduling (single-deep racking)")

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
st.sidebar.header("Simulation settings")
n_pallets = st.sidebar.slider("Number of pallets", 20, 500, 200, step=10)
st.sidebar.subheader("Rack capacity (slots per level)")
low_cap = st.sidebar.slider("Low level", 1, 100, 30)
mid_cap = st.sidebar.slider("Mid level", 1, 100, 30)
high_cap = st.sidebar.slider("High level", 1, 100, 30)
st.sidebar.subheader("Arrival & deadline pattern")
arr_min, arr_max = st.sidebar.slider("Arrival interval (min)", 1, 20, (2, 8))
lead_min, lead_max = st.sidebar.slider("Line lead time / deadline window (min)", 5, 300, (30, 180))
hwc_pct = st.sidebar.slider("Handle-with-care %", 0, 50, 15)
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
    rack = build_rack({"Low": low_cap, "Mid": mid_cap, "High": high_cap})
    log, pallets, rack, occupancy_history = run_simulation(pallets, rack)
    df = pallets_to_dataframe(pallets)
    st.session_state["df"] = df
    st.session_state["rack"] = rack
    st.session_state["log"] = log
    st.session_state["occ_history"] = pd.DataFrame(occupancy_history)

df = st.session_state["df"]
rack = st.session_state["rack"]
occ_history = st.session_state["occ_history"]

# ---------------------------------------------------------------------------
# KPI summary
# ---------------------------------------------------------------------------
kpis = summary_kpis(df)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total pallets", kpis["total_pallets"])
c2.metric("On-time retrieval rate", f"{kpis['on_time_rate_pct']}%" if kpis["on_time_rate_pct"] is not None else "—")
c3.metric("Missed deadlines", kpis["missed_deadlines"])
c4.metric("Avg staging wait (min)", kpis["avg_staging_wait_min"])
c5.metric("Max staging wait (min)", kpis["max_staging_wait_min"])

st.divider()

# ---------------------------------------------------------------------------
# Rack utilization by tier
# ---------------------------------------------------------------------------
left, right = st.columns([1, 1])

with left:
    st.subheader("Utilization by weight tier")
    st.dataframe(rack_utilization_by_tier(df), use_container_width=True)

    st.subheader("Peak rack occupancy (during the run)")
    st.caption("The simulation runs until every pallet is retrieved, so the *final* "
               "state is always empty — this shows the busiest point instead.")
    level_cols = [c for c in occ_history.columns if c.endswith("_occupied")]
    if level_cols:
        peak_row = occ_history[level_cols].max()
        cap_row = occ_history[[c.replace("_occupied", "_capacity") for c in level_cols]].iloc[0]
        peak_df = pd.DataFrame({
            "level": [c.replace("_occupied", "") for c in level_cols],
            "peak_occupied": peak_row.values,
            "capacity": cap_row.values,
        })
        peak_df["peak_occupancy_%"] = (100 * peak_df["peak_occupied"] / peak_df["capacity"]).round(1)
        st.dataframe(peak_df.set_index("level"), use_container_width=True)

with right:
    st.subheader("Rack occupancy over time")
    if level_cols and len(occ_history) > 1:
        st.line_chart(occ_history.set_index("time")[level_cols])
    else:
        st.info("Not enough data points to chart.")

    st.subheader("Staging queue length over time")
    if len(occ_history) > 1:
        st.line_chart(occ_history.set_index("time")["staging_count"])

st.divider()

# ---------------------------------------------------------------------------
# At-risk pallets (currently in staging or HBR, deadline approaching)
# ---------------------------------------------------------------------------
st.subheader("Pallet detail")
tier_filter = st.multiselect("Filter by tier", options=sorted(df["tier"].unique()), default=list(df["tier"].unique()))
show_missed_only = st.checkbox("Show missed-deadline pallets only")

filtered = df[df["tier"].isin(tier_filter)]
if show_missed_only:
    filtered = filtered[filtered["missed_deadline"] == True]  # noqa: E712

st.dataframe(
    filtered[["pallet_id", "tier", "weight", "handle_with_care", "arrival_time",
              "hbr_slot", "staging_wait_min", "required_out_time", "retrieved_time",
              "missed_deadline"]],
    use_container_width=True,
    height=400,
)

st.caption(
    "Slotting rule: Heavy -> Low, Medium -> Low/Mid, Light -> Mid/High. "
    "Handle-with-care pallets are restricted to Low/Mid. "
    "Retrieval priority is earliest required_out_time first (single-deep rack, no lane-blocking)."
)
