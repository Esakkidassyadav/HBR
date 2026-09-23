"""
Synthetic pallet arrival stream generator.

Simulates pallets arriving over a shift/day, with weight, size, HWC flag,
and a required_out_time derived from a line-consumption pattern (i.e. the
line needs one pallet of a given SKU every N minutes).
"""
import random
from datetime import datetime, timedelta
from models import Pallet


def generate_pallets(
    n_pallets: int = 200,
    start_time: datetime = None,
    arrival_interval_minutes: tuple = (2, 8),
    line_lead_time_minutes: tuple = (30, 180),
    hwc_probability: float = 0.15,
    seed: int = 42,
) -> list:
    """
    Generates a list of Pallet objects with realistic arrival spacing.

    required_out_time = arrival_time + line_lead_time
    (i.e. how soon after arrival the line actually needs this pallet's
    contents -- short lead time = urgent pallet, long lead time = pallet
    can sit longer before it must be retrieved).
    """
    random.seed(seed)
    if start_time is None:
        start_time = datetime(2026, 1, 1, 6, 0, 0)  # shift start

    pallets = []
    t = start_time
    sizes = ["1200x1000", "1200x800", "1000x1000"]

    for i in range(n_pallets):
        # round to whole minutes so arrival/deadline events land on the
        # simulation's tick boundaries (avoids fractional-minute artifacts)
        t += timedelta(minutes=round(random.uniform(*arrival_interval_minutes)))
        weight = round(random.choice([
            random.uniform(20, 150),    # Light
            random.uniform(150, 500),   # Medium
            random.uniform(500, 1200),  # Heavy
        ]), 1)
        lead = timedelta(minutes=round(random.uniform(*line_lead_time_minutes)))
        hwc = random.random() < hwc_probability

        pallets.append(Pallet(
            pallet_id=f"P{i+1:04d}",
            arrival_time=t,
            weight=weight,
            size=random.choice(sizes),
            handle_with_care=hwc,
            required_out_time=t + lead,
        ))

    return pallets


if __name__ == "__main__":
    pallets = generate_pallets(20)
    for p in pallets[:5]:
        print(p.pallet_id, p.arrival_time, round(p.weight, 1), p.tier,
              p.handle_with_care, p.required_out_time)
