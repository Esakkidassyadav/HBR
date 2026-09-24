"""
Slotting (placement), handling-time modeling, and retrieval scheduling.

Single-deep rack: every slot is independently accessible, so retrieval
priority is driven purely by required_out_time (no lane-blocking).

Real operations aren't 100% rule-compliant -- a small fraction of pallets
get placed in a tier that violates the weight rule (operator error, rushed
handling, mislabeled pallet). That's modeled explicitly here via
`misplacement_probability`, and tracked on the pallet so it feeds the
Sorting Accuracy / Misplacement Rate KPIs.
"""
import heapq
import itertools
import random
from models import CATEGORY_TO_ALLOWED_TIERS, HWC_ALLOWED_TIERS


def allowed_tiers(pallet):
    tiers = set(CATEGORY_TO_ALLOWED_TIERS[pallet.category])
    if pallet.handle_with_care:
        tiers &= set(HWC_ALLOWED_TIERS)
        if not tiers:
            tiers = {"Tier 1"}
    return tiers


def decide_slot(pallet, slots: list, rng: random.Random, misplacement_probability: float = 0.032):
    """
    Returns (slot_or_None, correctly_sorted_bool).

    With probability `misplacement_probability`, ignores the weight rule
    and places the pallet in any open slot (simulated sorting error).
    Otherwise places it in an open slot matching its allowed tiers.
    """
    open_slots = [s for s in slots if not s.occupied]
    if not open_slots:
        return None, None

    if rng.random() < misplacement_probability:
        return rng.choice(open_slots), False

    candidates = [s for s in open_slots if s.tier in allowed_tiers(pallet)]
    if not candidates:
        return None, None
    return candidates[0], True


def handling_time_seconds(pallet, correctly_sorted: bool, rng: random.Random) -> float:
    """
    Base handling time scales with weight (heavier = slower to
    move/position), plus random noise, plus an occasional outlier
    (equipment issue, re-attempt, awkward placement) and a penalty if the
    pallet was misplaced (extra time correcting / double-handling).
    """
    base = 25 + (pallet.weight / 1000) * 35          # ~25s light, up to ~65s heavy
    noise = rng.gauss(0, 6)
    outlier = 0
    if rng.random() < 0.06:
        outlier = rng.uniform(40, 120)                # jam / re-attempt / congestion
    care_penalty = 8 if pallet.handle_with_care else 0
    error_penalty = 15 if not correctly_sorted else 0
    total = base + noise + outlier + care_penalty + error_penalty
    return round(max(total, 8), 1)


class RetrievalQueue:
    """Min-heap priority queue ordered by required_out_time."""

    def __init__(self):
        self._heap = []
        self._counter = itertools.count()

    def push(self, pallet):
        heapq.heappush(self._heap, (pallet.required_out_time, next(self._counter), pallet))

    def pop_due(self, current_time):
        due = []
        while self._heap and self._heap[0][0] <= current_time:
            _, _, pallet = heapq.heappop(self._heap)
            due.append(pallet)
        return due

    def peek_next_deadline(self):
        return self._heap[0][0] if self._heap else None

    def __len__(self):
        return len(self._heap)
