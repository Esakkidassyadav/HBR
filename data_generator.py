"""
Synthetic pallet arrival stream generator -- deliberately messy, not a clean
uniform distribution, so it resembles real operational data:

  - Weight has occasional outliers (oversized/undersized pallets)
  - Arrivals are bursty (clusters + quiet gaps), not evenly spaced
  - A small fraction of pallets have unusually tight or slack deadlines
"""
import random
from datetime import datetime, timedelta
from models import Pallet


def _sample_weight(rng: random.Random) -> float:
    """Weight distribution with a small tail of outliers on both ends."""
    r = rng.random()
    if r < 0.03:
        # extreme outlier: oversized/overweight pallet (rare, e.g. machine part)
        return round(rng.uniform(1200, 2000), 1)
    if r < 0.06:
        # extreme outlier: near-empty / small parts pallet
        return round(rng.uniform(2, 15), 1)
    # normal operating range, roughly split across the three bands
    band = rng.choices(["Light", "Medium", "Heavy"], weights=[0.40, 0.35, 0.25])[0]
    if band == "Light":
        return round(rng.uniform(20, 150), 1)
    if band == "Medium":
        return round(rng.uniform(150, 500), 1)
    return round(rng.uniform(500, 1150), 1)


def generate_pallets(
    n_pallets: int = 200,
    start_time: datetime = None,
    arrival_interval_minutes: tuple = (2, 8),
    line_lead_time_minutes: tuple = (30, 180),
    hwc_probability: float = 0.15,
    burst_probability: float = 0.08,
    seed: int = 42,
) -> list:
    """
    required_out_time = arrival_time + line lead time (how soon the line
    needs this pallet's contents after it arrives).
    """
    rng = random.Random(seed)
    if start_time is None:
        start_time = datetime(2026, 1, 1, 6, 0, 0)

    pallets = []
    t = start_time
    sizes = ["1200x1000", "1200x800", "1000x1000"]

    for i in range(n_pallets):
        # bursty arrivals: most of the time normal spacing, occasionally a
        # cluster (almost simultaneous) or a long quiet gap
        r = rng.random()
        if r < burst_probability:
            gap = rng.choice([0, 1])              # burst: back-to-back
        elif r > 1 - burst_probability:
            gap = round(rng.uniform(20, 45))       # gap: line stoppage / delay upstream
        else:
            gap = round(rng.uniform(*arrival_interval_minutes))
        t += timedelta(minutes=gap)

        weight = _sample_weight(rng)

        # deadline: mostly normal lead time, occasional urgent (tight) pallet
        if rng.random() < 0.05:
            lead = timedelta(minutes=round(rng.uniform(5, 15)))   # urgent/expedited
        else:
            lead = timedelta(minutes=round(rng.uniform(*line_lead_time_minutes)))

        hwc = rng.random() < hwc_probability

        pallets.append(Pallet(
            pallet_id=f"P{i+1:04d}",
            arrival_time=t,
            weight=weight,
            size=rng.choice(sizes),
            handle_with_care=hwc,
            required_out_time=t + lead,
        ))

    return pallets


if __name__ == "__main__":
    pallets = generate_pallets(20)
    for p in pallets[:8]:
        print(p.pallet_id, p.arrival_time, round(p.weight, 1), p.category,
              p.handle_with_care, p.required_out_time)
