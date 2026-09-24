"""
Discrete-event simulation of the HBR pallet flow:
    arrival -> staging area -> HBR slot placement -> retrieval (line pull)

Single-deep rack: retrieval never blocked by other pallets, so priority is
driven purely by required_out_time via the RetrievalQueue min-heap.
"""
import random
import simpy
from datetime import timedelta
from slotting import decide_slot, handling_time_seconds, RetrievalQueue


def run_simulation(pallets: list, rack_slots: list, tick_minutes: int = 1,
                    sim_duration_minutes: int = None, misplacement_probability: float = 0.032,
                    seed: int = 7):
    """
    Mutates pallets/rack_slots in place with simulation results and returns
    (event_log, pallets, rack_slots, occupancy_history).
    """
    rng = random.Random(seed)
    start_time = min(p.arrival_time for p in pallets)
    if sim_duration_minutes is None:
        latest_deadline = max(p.required_out_time for p in pallets)
        sim_duration_minutes = int((latest_deadline - start_time).total_seconds() / 60) + 180

    env = simpy.Environment()
    staging = []
    retrieval_queue = RetrievalQueue()
    log = []
    occupancy_history = []

    arrivals_sorted = sorted(pallets, key=lambda p: p.arrival_time)

    def to_dt(sim_minutes):
        return start_time + timedelta(minutes=sim_minutes)

    def tick_process(env):
        idx = 0
        while True:
            current_dt = to_dt(env.now)

            # 1. Arrivals due -> enter staging
            while idx < len(arrivals_sorted) and arrivals_sorted[idx].arrival_time <= current_dt:
                p = arrivals_sorted[idx]
                p.staging_entry_time = current_dt
                staging.append(p)
                log.append({"time": current_dt, "event": "ARRIVE", "pallet_id": p.pallet_id})
                idx += 1

            # 2. Try to place staged pallets into open slots
            still_staged = []
            for p in staging:
                slot, correct = decide_slot(p, rack_slots, rng, misplacement_probability)
                if slot:
                    slot.place(p.pallet_id)
                    p.rack_slot = slot.slot_id
                    p.placed_time = current_dt
                    p.staging_exit_time = current_dt
                    p.correctly_sorted = correct
                    p.handling_time_sec = handling_time_seconds(p, correct, rng)
                    retrieval_queue.push(p)
                    log.append({"time": current_dt, "event": "PLACE",
                                "pallet_id": p.pallet_id, "slot": slot.slot_id,
                                "correctly_sorted": correct})
                else:
                    still_staged.append(p)
            staging[:] = still_staged

            # 3. Retrievals due (line pull based on required_out_time)
            due = retrieval_queue.pop_due(current_dt)
            for p in due:
                p.retrieved_time = current_dt
                slot = next(s for s in rack_slots if s.slot_id == p.rack_slot)
                slot.clear()
                log.append({"time": current_dt, "event": "RETRIEVE",
                            "pallet_id": p.pallet_id,
                            "status": "LATE" if p.missed_deadline else "ON_TIME"})

            # 4. Snapshot occupancy this tick (dashboard needs the time series,
            # not just the final -- always empty -- state)
            by_tier = {}
            for s in rack_slots:
                by_tier.setdefault(s.tier, {"occupied": 0, "capacity": 0})
                by_tier[s.tier]["capacity"] += 1
                if s.occupied:
                    by_tier[s.tier]["occupied"] += 1
            occupancy_history.append({
                "time": current_dt,
                "staging_count": len(staging),
                **{f"{tier}_occupied": v["occupied"] for tier, v in by_tier.items()},
                **{f"{tier}_capacity": v["capacity"] for tier, v in by_tier.items()},
            })

            if idx >= len(arrivals_sorted) and not staging and len(retrieval_queue) == 0:
                break
            if env.now > sim_duration_minutes:
                break

            yield env.timeout(tick_minutes)

    env.process(tick_process(env))
    env.run()

    return log, pallets, rack_slots, occupancy_history
