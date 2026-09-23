"""
Core data models for the HBR (High-Bay Racking) pallet sorting system.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Weight tiers -> allowed rack levels
# Heavy pallets go low (structural safety / ease of forklift handling),
# light pallets go high. Handle-with-care pallets are restricted to
# easily-accessible (Low/Mid) levels regardless of weight tier.
# ---------------------------------------------------------------------------
WEIGHT_TIERS = {
    "Heavy": (500, float("inf")),   # kg, lower bound inclusive
    "Medium": (150, 500),
    "Light": (0, 150),
}

TIER_TO_LEVELS = {
    "Heavy": ["Low"],
    "Medium": ["Low", "Mid"],
    "Light": ["Mid", "High"],
}

HWC_ALLOWED_LEVELS = ["Low", "Mid"]  # handle-with-care never goes to High


def weight_tier(weight_kg: float) -> str:
    for tier, (lo, hi) in WEIGHT_TIERS.items():
        if lo <= weight_kg < hi:
            return tier
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
    hbr_slot: Optional[str] = None
    placed_time: Optional[datetime] = None
    retrieved_time: Optional[datetime] = None

    @property
    def tier(self) -> str:
        return weight_tier(self.weight)

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
    level: str                 # "Low" / "Mid" / "High"
    occupied: bool = False
    pallet_id: Optional[str] = None

    def place(self, pallet_id: str):
        self.occupied = True
        self.pallet_id = pallet_id

    def clear(self):
        self.occupied = False
        self.pallet_id = None


def build_rack(levels_config: dict) -> list:
    """
    levels_config: e.g. {"Low": 20, "Mid": 20, "High": 20}
    Returns a flat list of RackSlot (single-deep: every slot independently
    accessible, no lane-blocking).
    """
    slots = []
    for level, count in levels_config.items():
        for i in range(count):
            slots.append(RackSlot(slot_id=f"{level[0]}{i+1:03d}", level=level))
    return slots
