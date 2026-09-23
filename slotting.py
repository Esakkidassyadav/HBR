"""
Slotting (placement) and scheduling (retrieval) logic.

Single-deep rack: every slot is independently accessible, so slotting is a
simple constrained lookup, and retrieval priority is driven purely by
required_out_time (no lane-blocking to account for).
"""
import heapq
import itertools
from models import TIER_TO_LEVELS, HWC_ALLOWED_LEVELS


def allowed_levels(pallet):
    levels = set(TIER_TO_LEVELS[pallet.tier])
    if pallet.handle_with_care:
        levels &= set(HWC_ALLOWED_LEVELS)
        if not levels:
            # fallback: HWC pallets always get at least "Low" priority
            levels = {"Low"}
    return levels


def find_slot(pallet, slots: list):
    """Return the first open slot matching the pallet's allowed levels, or
    None if the rack is full for that tier/HWC combination."""
    candidates = [s for s in slots if not s.occupied and s.level in allowed_levels(pallet)]
    if not candidates:
        return None
    # simple heuristic: fill lowest-index slot first (could be replaced with
    # a smarter packing rule later)
    return candidates[0]


class RetrievalQueue:
    """Min-heap priority queue ordered by required_out_time."""

    def __init__(self):
        self._heap = []
        self._counter = itertools.count()  # tie-breaker for stable ordering

    def push(self, pallet):
        heapq.heappush(self._heap, (pallet.required_out_time, next(self._counter), pallet))

    def pop_due(self, current_time):
        """Pop and return all pallets whose required_out_time <= current_time."""
        due = []
        while self._heap and self._heap[0][0] <= current_time:
            _, _, pallet = heapq.heappop(self._heap)
            due.append(pallet)
        return due

    def peek_next_deadline(self):
        return self._heap[0][0] if self._heap else None

    def __len__(self):
        return len(self._heap)
