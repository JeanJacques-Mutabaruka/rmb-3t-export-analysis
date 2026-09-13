"""Exporter ranking, with year-on-year movement.

Kept separate from peer benchmarking: ranking asks "who is biggest?", peer
benchmarking asks "who priced well?". They share no logic.

A deliberate design point — the previous year's rank is always computed from
the FULL dataset, never from the user's year filter. Filtering to 2026 alone
would otherwise blank the comparison column exactly when it is most wanted.
No Streamlit imports.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Quantity columns are only meaningful within a single product: adding
# kilograms of tin to kilograms of tantalum produces a number with no meaning.
# Value shares a unit ($) and is always safe to aggregate.
QUANTITY_IS_MEANINGFUL_ONLY_PER_PRODUCT = True


def ranking_by_year(df: pd.DataFrame, product: str | None = None) -> pd.DataFrame:
    """One row per (year, exporter) with value, quantities, share and rank.

    Rank is by export value, descending, computed within each year over the
    WHOLE dataset supplied — so pass the unfiltered frame if you want a
    previous-year rank that survives the user's filter.
    """
    d = df[df["issuance_date"].notna()]
    if product:
        d = d[d["product"] == product]
    if d.empty:
        return pd.DataFrame(columns=["year", "exporter", "value", "quantity",
                                     "pure_qty", "shipments", "share_pct", "rank"])

    g = (
        d.groupby([d["issuance_date"].dt.year.rename("year"), "exporter"],
                  observed=True)
        .agg(value=("shipment_value_usd", "sum"),
             quantity=("quantity_kg", "sum"),
             pure_qty=("pure_quantity_kg", "sum"),
             shipments=("shipment_value_usd", "size"))
        .reset_index()
    )
    g["year"] = g["year"].astype(int)
    totals = g.groupby("year")["value"].transform("sum")
    g["share_pct"] = np.where(totals > 0, g["value"] / totals * 100, np.nan)
    g["rank"] = g.groupby("year")["value"].rank(ascending=False, method="min").astype(int)
    return g.sort_values(["year", "rank"]).reset_index(drop=True)


def ranking_with_movement(df_all: pd.DataFrame, current_year: int,
                          product: str | None = None) -> pd.DataFrame:
    """Current-year ranking joined to the previous year's rank, value and share.

    `df_all` must be the UNFILTERED dataset, so the previous year is available
    even when the user's filter excludes it.
    """
    full = ranking_by_year(df_all, product)
    if full.empty:
        return full

    cur = full[full["year"] == current_year].copy()
    if cur.empty:
        return cur

    prev = (
        full[full["year"] == current_year - 1]
        [["exporter", "rank", "value", "share_pct"]]
        .rename(columns={"rank": "rank_prev", "value": "value_prev",
                         "share_pct": "share_pct_prev"})
    )
    out = cur.merge(prev, on="exporter", how="left")

    # Positive = moved UP the table (rank number got smaller).
    out["rank_change"] = np.where(
        out["rank_prev"].notna(), out["rank_prev"] - out["rank"], np.nan)
    out["value_change_pct"] = np.where(
        out["value_prev"].fillna(0) > 0,
        (out["value"] - out["value_prev"]) / out["value_prev"] * 100, np.nan)
    out["is_new_entrant"] = out["rank_prev"].isna()
    return out.sort_values("rank").reset_index(drop=True)


def movement_label(row) -> str:
    """Compact arrow for the rank move, for display."""
    if bool(row.get("is_new_entrant", False)) or pd.isna(row.get("rank_change")):
        return "new"
    change = int(row["rank_change"])
    if change > 0:
        return f"▲ {change}"
    if change < 0:
        return f"▼ {abs(change)}"
    return "—"
