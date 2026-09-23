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
            "tier": p.tier,
            "size": p.size,
            "handle_with_care": p.handle_with_care,
            "required_out_time": p.required_out_time,
            "staging_entry_time": p.staging_entry_time,
            "staging_exit_time": p.staging_exit_time,
            "hbr_slot": p.hbr_slot,
            "retrieved_time": p.retrieved_time,
            "staging_wait_min": (p.staging_wait_seconds / 60) if p.staging_wait_seconds is not None else None,
            "missed_deadline": p.missed_deadline,
            "slack_min_at_retrieval": (p.slack_seconds_at_retrieval / 60) if p.slack_seconds_at_retrieval is not None else None,
        })
    return pd.DataFrame(rows)


def summary_kpis(df: pd.DataFrame) -> dict:
    total = len(df)
    retrieved = df["retrieved_time"].notna().sum()
    placed = df["hbr_slot"].notna().sum()
    missed = df["missed_deadline"].fillna(False).sum()

    return {
        "total_pallets": total,
        "placed_in_hbr": int(placed),
        "retrieved": int(retrieved),
        "still_in_staging_or_hbr": int(total - retrieved),
        "missed_deadlines": int(missed),
        "on_time_rate_pct": round(100 * (retrieved - missed) / retrieved, 1) if retrieved else None,
        "avg_staging_wait_min": round(df["staging_wait_min"].dropna().mean(), 1) if df["staging_wait_min"].notna().any() else None,
        "max_staging_wait_min": round(df["staging_wait_min"].dropna().max(), 1) if df["staging_wait_min"].notna().any() else None,
        "avg_slack_min_at_retrieval": round(df["slack_min_at_retrieval"].dropna().mean(), 1) if df["slack_min_at_retrieval"].notna().any() else None,
    }


def rack_utilization_by_tier(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("tier").agg(
        pallets=("pallet_id", "count"),
        avg_staging_wait_min=("staging_wait_min", "mean"),
        missed_deadlines=("missed_deadline", lambda s: s.fillna(False).sum()),
    ).round(1)
