"""Peer panel construction — shaping raw shipments into the comparison grid.

One question: *who traded what, when, and at what realised price?*

Everything downstream (benchmark.py, evaluate.py) consumes the frame this
module produces. No Streamlit imports.

Window model: a period GRAIN ('month' or 'quarter') plus a WINDOW SIZE N.
  Current month    = grain 'month',   N=1
  Moving month     = grain 'month',   N configurable (default 3)
  Current quarter  = grain 'quarter', N=1
  Moving quarter   = grain 'quarter', N configurable (default 2)
"""
from __future__ import annotations

import pandas as pd

THIN_MARKET_THRESHOLD = 3  # spec §7.3 — confirmed

BASIS_PRESETS = {
    "Current month": ("month", 1),
    "Moving month (3)": ("month", 3),
    "Current quarter": ("quarter", 1),
    "Moving quarter (2)": ("quarter", 2),
}


def _period(df: pd.DataFrame, grain: str) -> pd.Series:
    freq = "M" if grain == "month" else "Q"
    return df["issuance_date"].dt.to_period(freq)


def exporter_periods(df: pd.DataFrame, grain: str = "month") -> pd.DataFrame:
    """Volume-weighted price per exporter x product x period."""
    d = df[df["issuance_date"].notna()].copy()
    d = d[d["pure_quantity_kg"] > 0]
    d["period"] = _period(d, grain)

    g = (
        d.groupby(["product", "period", "exporter"], observed=True)
        .agg(value=("shipment_value_usd", "sum"),
             pure_qty=("pure_quantity_kg", "sum"),
             shipments=("shipment_value_usd", "size"))
        .reset_index()
    )
    g["price"] = g["value"] / g["pure_qty"]
    # Map product -> mineral using the DOMINANT label for that product, not the
    # first occurrence: the source contains a few single-row mineral/product
    # mismatches (e.g. one 'Tungsten concentrate' row labelled Cassiterite) and
    # first-occurrence mapping silently mislabels the whole peer group.
    # The mismatched rows themselves are surfaced by exclusions.suggest().
    dominant = (
        d.groupby(["product", "mineral"], observed=True)["shipment_value_usd"]
        .sum().reset_index()
        .sort_values("shipment_value_usd", ascending=False)
        .drop_duplicates("product").set_index("product")["mineral"]
    )
    g["mineral"] = g["product"].map(dominant)
    return g


def product_mineral_map(df: pd.DataFrame) -> pd.Series:
    """Dominant mineral per product, by exported value."""
    return (
        df.groupby(["product", "mineral"], observed=True)["shipment_value_usd"]
        .sum().reset_index()
        .sort_values("shipment_value_usd", ascending=False)
        .drop_duplicates("product").set_index("product")["mineral"]
    )
