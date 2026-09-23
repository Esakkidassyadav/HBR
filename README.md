# HBR Pallet Sorting

Warehouse High-Bay Racking (HBR) pallet allocation and retrieval scheduling
system. Solves two coupled problems:

1. **Slotting** — assign each incoming pallet to a rack level based on weight
   (Heavy -> Low, Medium -> Low/Mid, Light -> Mid/High), with
   handle-with-care pallets restricted to Low/Mid.
2. **Retrieval scheduling** — pallets are pulled from the HBR in order of
   `required_out_time` (earliest-deadline-first), which is derived from the
   production line's material requirement, not arrival order.

Rack is modeled as **single-deep**: every slot is independently accessible,
so retrieval is never blocked by other pallets (no lane-sequencing
constraint).

## Project structure

```
models.py           Pallet, RackSlot dataclasses; weight-tier rules
data_generator.py    Synthetic pallet arrival stream generator
slotting.py          Slot-finding logic + retrieval priority queue
simulation.py         SimPy-style discrete-event simulation (staging -> HBR -> retrieval)
analysis.py          KPI computation (staging wait, missed deadlines, utilization)
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
from analysis import pallets_to_dataframe, summary_kpis

pallets = generate_pallets(n_pallets=200)
rack = build_rack({"Low": 30, "Mid": 30, "High": 30})
log, pallets, rack = run_simulation(pallets, rack)

df = pallets_to_dataframe(pallets)
print(summary_kpis(df))
```

## Run the dashboard

```bash
streamlit run app.py
```

Adjust pallet volume, rack capacity per level, arrival rate, and deadline
window from the sidebar and re-run to see how staging wait time and
on-time retrieval rate respond.

## Key design decisions

- **required_out_time** = arrival_time + line lead time. This models the
  fact that retrieval deadlines are driven by the production line's
  material requirement, not by an arbitrary FIFO rule.
- **Single-deep racking** assumed — simplifies slotting to a lookup and
  removes lane-blocking from the retrieval model. If your actual HBR is
  drive-in/lane-based, `slotting.py` and `simulation.py` would need a
  lane-occupancy model instead of independent slots.
- **Weight tiers** (Heavy/Medium/Light) and their allowed levels are
  configurable in `models.py` — adjust thresholds to match your actual
  pallet weight distribution and rack safety ratings.

## Validated behavior

- With generous rack capacity, 0% missed deadlines and 0 staging wait
  (sanity check — no congestion, no delay).
- With constrained capacity, staging wait rises and the Heavy tier (which
  can only use the Low level) becomes the bottleneck first — matches
  expected physical behavior.

## Next steps / extensions

- Replace the greedy "first open slot" placement rule with an optimization
  model (PuLP/OR-Tools) if you want provably optimal slot-fit.
- Add a lane-based (drive-in) rack model if your actual HBR isn't
  single-deep.
- Validate `weight_tier` thresholds and lead-time distributions against
  real Ather pallet/line data.
