"""Rwanda realised price vs international benchmark — gaps and losses.

Spec §7.1. No Streamlit imports.
"""
from __future__ import annotations

import pandas as pd

from .benchmarks_intl import lookup


def rwanda_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Volume-weighted realised price and pure volume per mineral-month."""
    d = df[(df["issuance_date"].notna()) & (df["pure_quantity_kg"] > 0)].copy()
    if d.empty:
        return pd.DataFrame(columns=["mineral", "period", "year", "month",
                                     "rwanda_price", "pure_qty", "export_value"])
    d["period"] = d["issuance_date"].dt.to_period("M")

    out = (
        d.groupby(["mineral", "period"], observed=True)
        .agg(pure_qty=("pure_quantity_kg", "sum"),
             export_value=("shipment_value_usd", "sum"))
        .reset_index()
    )
    out["rwanda_price"] = out["export_value"] / out["pure_qty"]
    out["year"] = out["period"].apply(lambda p: p.year)
    out["month"] = out["period"].apply(lambda p: p.month)
    return out


def attach(rw: pd.DataFrame, prices: dict) -> pd.DataFrame:
    """Add benchmark, provenance and the gap/loss columns."""
    if rw.empty:
        return rw.assign(benchmark=[], basis=[], note=[], gap=[], gap_pct=[],
                         loss_signed=[], loss_floored=[])
    rows = []
    for _, r in rw.iterrows():
        price, basis, note = lookup(prices, r["mineral"], int(r["year"]), int(r["month"]))
        rows.append({"benchmark": price, "basis": basis, "note": note})
    out = pd.concat([rw.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    out["gap"] = out["benchmark"] - out["rwanda_price"]
    out["gap_pct"] = out["gap"] / out["benchmark"]
    out["loss_signed"] = out["gap"] * out["pure_qty"]
    out["loss_floored"] = out["loss_signed"].clip(lower=0)
    return out


def annual(gap: pd.DataFrame, floored: bool = True) -> pd.DataFrame:
    if gap.empty:
        return pd.DataFrame()
    col = "loss_floored" if floored else "loss_signed"
    piv = gap.pivot_table(index="year", columns="mineral", values=col,
                          aggfunc="sum").fillna(0)
    piv["Total"] = piv.sum(axis=1)
    piv["Cumulative"] = piv["Total"].cumsum()
    return piv


def loss_share(gap: pd.DataFrame) -> pd.DataFrame:
    """Share of each year's total loss by mineral — the 'where to focus' view."""
    if gap.empty:
        return pd.DataFrame()
    piv = gap.pivot_table(index="year", columns="mineral", values="loss_floored",
                          aggfunc="sum").fillna(0)
    total = piv.sum(axis=1).replace(0, pd.NA)
    return (piv.div(total, axis=0) * 100).fillna(0)
