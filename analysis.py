"""
KPI computation from a completed simulation run.
"""
import pandas as pd


def pallets_to_dataframe(pallets: list) -> pd.DataFrame:
    rows = []
    for p in pallets:
        rows.append({
            "pallet_id": p.pallet_id,
            "arrival_time": p.arrival_time,
            "weight": p.weight,
            "weight_category": p.category,
            "size": p.size,
            "handle_with_care": p.handle_with_care,
            "required_out_time": p.required_out_time,
            "staging_entry_time": p.staging_entry_time,
            "staging_exit_time": p.staging_exit_time,
            "rack_slot": p.rack_slot,
            "rack_tier": p.rack_slot.split("-")[0] if p.rack_slot else None,
            "retrieved_time": p.retrieved_time,
            "staging_wait_min": (p.staging_wait_seconds / 60) if p.staging_wait_seconds is not None else None,
            "missed_deadline": p.missed_deadline,
            "slack_min_at_retrieval": (p.slack_seconds_at_retrieval / 60) if p.slack_seconds_at_retrieval is not None else None,
            "handling_time_sec": p.handling_time_sec,
            "correctly_sorted": p.correctly_sorted,
        })
    df = pd.DataFrame(rows)
    tier_map = {"T1": "Tier 1", "T2": "Tier 2", "T3": "Tier 3"}
    if "rack_tier" in df.columns:
        df["rack_tier"] = df["rack_tier"].map(tier_map).fillna(df["rack_tier"])
    return df


# ---------------------------------------------------------------------------
# Top KPI cards
# ---------------------------------------------------------------------------
def top_kpis(df: pd.DataFrame, occ_history: pd.DataFrame) -> dict:
    total = len(df)
    retrieved = df["retrieved_time"].notna().sum()
    sorted_known = df["correctly_sorted"].notna()
    accuracy = 100 * df.loc[sorted_known, "correctly_sorted"].mean() if sorted_known.any() else None
    misplacement = 100 - accuracy if accuracy is not None else None

    level_cols = [c for c in occ_history.columns if c.endswith("_occupied")]
    cap_cols = [c.replace("_occupied", "_capacity") for c in level_cols]
    if level_cols:
        total_occupied = occ_history[level_cols].sum(axis=1)
        total_capacity = occ_history[cap_cols].sum(axis=1)
        utilization = 100 * (total_occupied / total_capacity).mean()
    else:
        utilization = None

    avg_handling = df["handling_time_sec"].dropna().mean() if df["handling_time_sec"].notna().any() else None

    return {
        "total_pallets_processed": int(total),
        "sorting_accuracy_pct": round(accuracy, 1) if accuracy is not None else None,
        "hbr_utilization_pct": round(utilization, 1) if utilization is not None else None,
        "avg_handling_time_sec": round(avg_handling, 1) if avg_handling is not None else None,
        "misplacement_rate_pct": round(misplacement, 1) if misplacement is not None else None,
        "retrieved": int(retrieved),
        "missed_deadlines": int(df["missed_deadline"].fillna(False).sum()),
        "avg_staging_wait_min": round(df["staging_wait_min"].dropna().mean(), 1) if df["staging_wait_min"].notna().any() else None,
    }


# ---------------------------------------------------------------------------
# Chart-feeding aggregations (each maps directly to one requested KPI chart)
# ---------------------------------------------------------------------------
def pallets_by_weight_category(df: pd.DataFrame) -> pd.Series:
    """KPI 1: Pallets by Weight Category -- Bar/Pie"""
    return df["weight_category"].value_counts().reindex(["Heavy", "Medium", "Light"]).fillna(0)


def tier_wise_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """KPI 2: Tier-wise Pallet Distribution -- Stacked Bar (Tier x weight category)"""
    pivot = pd.crosstab(df["rack_tier"], df["weight_category"])
    for col in ["Heavy", "Medium", "Light"]:
        if col not in pivot.columns:
            pivot[col] = 0
    return pivot.reindex(["Tier 1", "Tier 2", "Tier 3"]).fillna(0)[["Heavy", "Medium", "Light"]]


def rack_utilization_by_tier_pct(occ_history: pd.DataFrame) -> pd.Series:
    """KPI 3: Rack Utilization by Tier (%) -- Bar. Average utilization across the run."""
    level_cols = [c for c in occ_history.columns if c.endswith("_occupied")]
    result = {}
    for col in level_cols:
        tier = col.replace("_occupied", "")
        cap_col = f"{tier}_capacity"
        result[tier] = round(100 * (occ_history[col] / occ_history[cap_col]).mean(), 1)
    return pd.Series(result)


def throughput_over_time(df: pd.DataFrame, freq: str = "h") -> pd.Series:
    """KPI 4: Pallet Throughput Over Time -- Line. Pallets retrieved per period."""
    retrieved = df.dropna(subset=["retrieved_time"]).copy()
    if retrieved.empty:
        return pd.Series(dtype=int)
    retrieved["bucket"] = retrieved["retrieved_time"].dt.floor(freq)
    return retrieved.groupby("bucket").size()


def avg_handling_time_by_category(df: pd.DataFrame) -> pd.Series:
    """KPI 5: Average Handling Time by Weight Category -- Bar."""
    return df.groupby("weight_category")["handling_time_sec"].mean().reindex(
        ["Heavy", "Medium", "Light"]).round(1)


def rack_utilization_by_tier(df: pd.DataFrame) -> pd.DataFrame:
    """Secondary breakdown: pallet counts + avg wait + missed deadlines per weight category."""
    return df.groupby("weight_category").agg(
        pallets=("pallet_id", "count"),
        avg_staging_wait_min=("staging_wait_min", "mean"),
        missed_deadlines=("missed_deadline", lambda s: s.fillna(False).sum()),
    ).round(1)
