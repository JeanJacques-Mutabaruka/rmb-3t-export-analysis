"""Peer (internal) benchmarking — exporters vs their Rwandan peers.

Spec §7.2, §7.3. Peer group = same `product` in the same period.
No Streamlit imports.

Window model: a period GRAIN ('month' or 'quarter') plus a WINDOW SIZE N.
  Current month    = grain 'month',   N=1
  Moving month     = grain 'month',   N configurable (default 3)
  Current quarter  = grain 'quarter', N=1
  Moving quarter   = grain 'quarter', N configurable (default 2)
"""
from __future__ import annotations

import numpy as np
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


def peer_stats(ep: pd.DataFrame, grain: str = "month", window: int = 1) -> pd.DataFrame:
    """Average / Max / Min / Range per product x period over a rolling window.

    Average is volume-weighted across the window. Max and Min are taken over
    exporter-level prices within the window (spec §7.2).
    """
    rows = []
    for product, sub in ep.groupby("product", observed=True):
        periods = sorted(sub["period"].unique())
        if not periods:
            continue
        full = pd.period_range(min(periods), max(periods),
                               freq=periods[0].freqstr)
        by_period = {p: sub[sub["period"] == p] for p in periods}

        for i, p in enumerate(full):
            lo = max(0, i - window + 1)
            window_periods = list(full[lo:i + 1])
            frames = [by_period[w] for w in window_periods if w in by_period]
            if not frames:
                continue
            w = pd.concat(frames)
            if w.empty or w["pure_qty"].sum() <= 0:
                continue
            rows.append({
                "product": product,
                "period": p,
                "peer_avg": w["value"].sum() / w["pure_qty"].sum(),
                "peer_max": w["price"].max(),
                "peer_min": w["price"].min(),
                "n_exporters": int(w["exporter"].nunique()),
                "window_periods": len(window_periods),
            })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["peer_range"] = out["peer_max"] - out["peer_min"]
    out["thin_market"] = out["n_exporters"] < THIN_MARKET_THRESHOLD
    return out


def discounts(ep: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    """Attach peer benchmarks to each exporter-period and compute gaps.

    Spec §7.3. Min is deliberately NOT a loss basis — it is a statistic and an
    error-detection aid only.
    """
    if stats.empty:
        return ep.assign(peer_avg=np.nan, peer_max=np.nan, peer_min=np.nan)

    d = ep.merge(stats, on=["product", "period"], how="left")
    d["disc_vs_avg_pct"] = (d["peer_avg"] - d["price"]) / d["peer_avg"]
    d["disc_vs_max_pct"] = (d["peer_max"] - d["price"]) / d["peer_max"]
    d["forgone_vs_avg"] = ((d["peer_avg"] - d["price"]) * d["pure_qty"]).clip(lower=0)
    d["forgone_vs_max"] = ((d["peer_max"] - d["price"]) * d["pure_qty"]).clip(lower=0)
    d["below_avg"] = d["price"] < d["peer_avg"]
    d["year"] = d["period"].apply(lambda p: p.year)
    return d


def scorecard(disc: pd.DataFrame) -> pd.DataFrame:
    """Annual per-exporter scorecard, aggregated from periods to mineral level.

    Carries both the aggregate figures and the RANGE across periods, because a
    single volume-weighted price hides how much an exporter's realised price
    moved during the year.

    `pct_qty_below_avg` is the volume-weighted counterpart of `consistency`:
    the share of an exporter's contained tonnage sold in periods where its
    price sat below the peer average. It matters more than the count of
    periods, because one large under-priced consignment outweighs several
    small well-priced ones.
    """
    if disc.empty:
        return pd.DataFrame()

    a = (
        disc.groupby(["mineral", "year", "exporter"], observed=True)
        .apply(lambda x: pd.Series({
            "pure_qty": x["pure_qty"].sum(),
            "value": x["value"].sum(),
            "shipments": x["shipments"].sum(),
            "periods_active": x["period"].nunique(),
            "periods_below_avg": int(x["below_avg"].sum()),
            "exporter_price": x["value"].sum() / x["pure_qty"].sum(),
            "price_min": x["price"].min(),
            "price_max": x["price"].max(),
            "disc_min": x["disc_vs_avg_pct"].min(),
            "disc_max": x["disc_vs_avg_pct"].max(),
            "qty_below_avg": x.loc[x["below_avg"], "pure_qty"].sum(),
            "peer_avg": (x["peer_avg"] * x["pure_qty"]).sum() / x["pure_qty"].sum(),
            "peer_max": (x["peer_max"] * x["pure_qty"]).sum() / x["pure_qty"].sum(),
            "forgone_vs_avg": x["forgone_vs_avg"].sum(),
            "forgone_vs_max": x["forgone_vs_max"].sum(),
            "thin_periods": int(x["thin_market"].sum()),
        }), include_groups=False)
        .reset_index()
    )
    a["disc_vs_avg_pct"] = (a["peer_avg"] - a["exporter_price"]) / a["peer_avg"]
    a["disc_vs_max_pct"] = (a["peer_max"] - a["exporter_price"]) / a["peer_max"]
    a["consistency"] = a["periods_below_avg"] / a["periods_active"].replace(0, np.nan)
    a["pct_qty_below_avg"] = a["qty_below_avg"] / a["pure_qty"].replace(0, np.nan)
    a["volume_share"] = a["pure_qty"] / a.groupby(["mineral", "year"])["pure_qty"].transform("sum")
    return a


def worst_traders(sc: pd.DataFrame, mineral: str, year: int, n: int = 5,
                  rank_by: str = "forgone_vs_avg",
                  min_pure_qty: float = 0.0) -> pd.DataFrame:
    s = sc[(sc["mineral"] == mineral) & (sc["year"] == year)]
    if min_pure_qty:
        s = s[s["pure_qty"] >= min_pure_qty]
    if s.empty:
        return s
    return s.nlargest(n, rank_by)
