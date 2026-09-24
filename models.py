"""
Core data models for the HBR (High-Bay Racking) pallet sorting system.

Two separate classification axes, kept distinct on purpose:
  - weight_category: Heavy / Medium / Light        (a property of the pallet)
  - rack_tier:        Tier 1 / Tier 2 / Tier 3       (a property of the rack slot)
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


WEIGHT_CATEGORIES = {
    "Heavy": (500, float("inf")),   # kg, lower bound inclusive
    "Medium": (150, 500),
    "Light": (0, 150),
}

# Tier 1 = lowest/most structurally robust level (heaviest pallets)
# Tier 3 = highest level (lightest pallets only)
CATEGORY_TO_ALLOWED_TIERS = {
    "Heavy": ["Tier 1"],
    "Medium": ["Tier 1", "Tier 2"],
    "Light": ["Tier 2", "Tier 3"],
}

# The tier each category should fill FIRST -- without this, a naive
# first-open-slot search always favors Tier 1 then Tier 2, leaving Tier 3
# almost empty. This gives every category a natural "home" tier, with the
# others in CATEGORY_TO_ALLOWED_TIERS used only as overflow when full.
PRIMARY_TIER = {
    "Heavy": "Tier 1",
    "Medium": "Tier 2",
    "Light": "Tier 3",
}

HWC_ALLOWED_TIERS = ["Tier 1", "Tier 2"]  # handle-with-care never goes to Tier 3


def weight_category(weight_kg: float) -> str:
    for cat, (lo, hi) in WEIGHT_CATEGORIES.items():
        if lo <= weight_kg < hi:
            return cat
    return "Heavy"


@dataclass
class Pallet:
    pallet_id: str
    arrival_time: datetime
    weight: float                      # kg
    size: str                          # e.g. "1200x1000"
    handle_with_care: bool
    required_out_time: datetime        # driven by line requirement

    staging_entry_time: Optional[datetime] = None
    staging_exit_time: Optional[datetime] = None
    rack_slot: Optional[str] = None
    placed_time: Optional[datetime] = None
    retrieved_time: Optional[datetime] = None
    handling_time_sec: Optional[float] = None
    correctly_sorted: Optional[bool] = None   # False = simulated sorting error

    @property
    def category(self) -> str:
        return weight_category(self.weight)

    @property
    def staging_wait_seconds(self) -> Optional[float]:
        if self.staging_entry_time and self.staging_exit_time:
            return (self.staging_exit_time - self.staging_entry_time).total_seconds()
        return None

    @property
    def missed_deadline(self) -> Optional[bool]:
        if self.retrieved_time is None:
            return None
        return self.retrieved_time > self.required_out_time

    @property
    def slack_seconds_at_retrieval(self) -> Optional[float]:
        if self.retrieved_time is None:
            return None
        return (self.required_out_time - self.retrieved_time).total_seconds()


@dataclass
class RackSlot:
    slot_id: str
    tier: str                 # "Tier 1" / "Tier 2" / "Tier 3"
    occupied: bool = False
    pallet_id: Optional[str] = None

    def place(self, pallet_id: str):
        self.occupied = True
        self.pallet_id = pallet_id

    def clear(self):
        self.occupied = False
        self.pallet_id = None


def build_rack(tier_config: dict) -> list:
    """
    tier_config: e.g. {"Tier 1": 20, "Tier 2": 20, "Tier 3": 20}
    Returns a flat list of RackSlot (single-deep: every slot independently
    accessible, no lane-blocking).
    """
    slots = []
    for tier, count in tier_config.items():
        prefix = tier.replace("Tier ", "T")
        for i in range(count):
            slots.append(RackSlot(slot_id=f"{prefix}-{i+1:03d}", tier=tier))
    return slots
