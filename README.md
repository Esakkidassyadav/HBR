# HBR Pallet Sorting

Warehouse High-Bay Racking (HBR) pallet allocation and retrieval scheduling
system. Solves two coupled problems:

1. **Slotting** — assign each incoming pallet to a rack **Tier** based on
   weight category (Heavy -> Tier 1 only, Medium -> Tier 1/2, Light -> Tier
   2/3), with handle-with-care pallets restricted to Tier 1/2. A small
   percentage of placements are deliberately simulated as sorting errors
   (configurable), since real operations aren't 100% rule-compliant.
2. **Retrieval scheduling** — pallets are pulled from the HBR in order of
   `required_out_time` (earliest-deadline-first), derived from the
   production line's material requirement, not arrival order.

Rack is modeled as **single-deep**: every slot is independently accessible,
so retrieval is never blocked by other pallets.

## Project structure

```
models.py           Pallet, RackSlot dataclasses; weight-category -> tier rules
data_generator.py    Synthetic pallet stream: weight outliers, bursty arrivals, urgent deadlines
slotting.py          Slot decision (incl. simulated misplacement), handling-time model, retrieval queue
simulation.py         Discrete-event simulation (staging -> HBR -> retrieval), occupancy time series
analysis.py          KPI computation: 5 top-line numbers + 5 chart-ready aggregations
app.py               Streamlit dashboard
```

## Setup

```bash
pip install simpy streamlit pandas faker
```

## Run the simulation (script)

```python
from data_generator import generate_pallets
from models import build_rack
from simulation import run_simulation
from analysis import pallets_to_dataframe, top_kpis
import pandas as pd

pallets = generate_pallets(n_pallets=300)
rack = build_rack({"Tier 1": 25, "Tier 2": 25, "Tier 3": 25})
log, pallets, rack, occupancy_history = run_simulation(pallets, rack, misplacement_probability=0.032)

df = pallets_to_dataframe(pallets)
occ_df = pd.DataFrame(occupancy_history)
print(top_kpis(df, occ_df))
```

## Run the dashboard

```bash
streamlit run app.py
```

## KPIs implemented

**Top cards:** Total Pallets Processed, Sorting Accuracy, HBR Utilization,
Average Handling Time, Misplacement Rate.

**Charts:**
1. Pallets by Weight Category (bar)
2. Tier-wise Pallet Distribution (stacked bar, Tier x weight category)
3. Rack Utilization by Tier (%) (bar)
4. Pallet Throughput Over Time (line, hourly or daily)
5. Average Handling Time by Weight Category (bar)

Plus operational views: rack occupancy over time, staging queue length over
time, and a filterable pallet detail table.

## What makes the data realistic, not uniform

- **Weight**: ~6% of pallets are outliers (oversized >1200kg or
  near-empty <15kg), rest split across Heavy/Medium/Light bands.
- **Arrivals**: bursty — occasional back-to-back clusters and occasional
  20-45 min gaps (upstream line stoppages), not evenly spaced.
- **Deadlines**: ~5% of pallets are "urgent" (5-15 min lead time) instead
  of the normal 30-180 min window.
- **Sorting errors**: a configurable % of placements (default 3.2%) ignore
  the weight rule entirely, simulating operator/system error — this feeds
  Sorting Accuracy / Misplacement Rate.
- **Handling time**: scales with weight, plus random noise, plus a ~6%
  chance of an outlier delay (jam, re-attempt), plus a penalty for
  handle-with-care and for misplaced pallets (double-handling).

## Key design decisions

- **required_out_time** = arrival_time + line lead time — retrieval
  deadlines are driven by the production line's material requirement.
- **Single-deep racking** — simplifies slotting to a lookup, no
  lane-blocking. If your real HBR is drive-in/lane-based, this needs a
  lane-occupancy model instead.
- All noise/error parameters (misplacement rate, outlier frequency, burst
  probability) are adjustable in `data_generator.py` / `slotting.py`, and
  misplacement rate is also a live slider in the dashboard.

## Next steps / extensions

- Replace the greedy "first open slot" placement rule with an optimization
  model (PuLP/OR-Tools) for provably optimal slot-fit.
- Add a lane-based (drive-in) rack model if your actual HBR isn't
  single-deep.
- Validate weight/lead-time distributions and error rates against real
  Ather pallet/line data.
