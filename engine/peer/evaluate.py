"""Per-exporter evaluation — how each exporter compares to the benchmark.

One question: *did this exporter beat the market or trail it, and by how much?*

The forgone (under-performance) and gained (out-performance) sides are exact
mirrors of each other and are computed together so they cannot drift apart.
No Streamlit imports.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

def discounts(ep: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    """Attach peer benchmarks to each exporter-period and compute gaps.

    Spec §7.3. Min is deliberately NOT a loss basis — it is a statistic and an
    error-detection aid only.

    `peer_avg_excl_self` is a LEAVE-ONE-OUT average: the volume-weighted price
    of every OTHER exporter in the same product/period, recomputed by removing
    this exporter's own value and quantity from the window total. This matters
    for a large exporter, where `peer_avg` (which includes the exporter
    itself) understates how far it actually sits from the rest of the market.
    It is informational only — Discount %, Value Forgone and Worst Traders
    keep using `peer_avg` (the full set), unchanged.
    """
    if stats.empty:
        return ep.assign(peer_avg=np.nan, peer_max=np.nan, peer_min=np.nan,
                         peer_avg_excl_self=np.nan)

    d = ep.merge(stats, on=["product", "period"], how="left")
    d["disc_vs_avg_pct"] = (d["peer_avg"] - d["price"]) / d["peer_avg"]
    d["disc_vs_max_pct"] = (d["peer_max"] - d["price"]) / d["peer_max"]
    d["forgone_vs_avg"] = ((d["peer_avg"] - d["price"]) * d["pure_qty"]).clip(lower=0)
    d["forgone_vs_max"] = ((d["peer_max"] - d["price"]) * d["pure_qty"]).clip(lower=0)
    d["below_avg"] = d["price"] < d["peer_avg"]
    # Mirror of forgone_vs_avg: revenue actually EARNED above the peer average.
    # Together they are exhaustive - for any period, exactly one of the two is
    # non-zero (or both are zero at price == peer_avg).
    d["above_avg"] = d["price"] > d["peer_avg"]
    d["gained_vs_avg"] = ((d["price"] - d["peer_avg"]) * d["pure_qty"]).clip(lower=0)
    d["year"] = d["period"].apply(lambda p: p.year)

    rem_value = d["window_value_sum"] - d["value"]
    rem_qty = d["window_qty_sum"] - d["pure_qty"]
    d["peer_avg_excl_self"] = np.where(rem_qty > 0, rem_value / rem_qty, np.nan)
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

    `gained_vs_avg` / `pct_qty_above_avg` / `premium_consistency` are the exact
    mirror of `forgone_vs_avg` / `pct_qty_below_avg` / `consistency`, for
    identifying BEST traders rather than worst — see best_traders() below.
    """
    if disc.empty:
        return pd.DataFrame()

    a = (
        disc.groupby(["mineral", "year", "exporter"], observed=True)
        .apply(_aggregate_exporter_year, include_groups=False)
        .reset_index()
    )
    a = _underperformance_metrics(a)
    a = _outperformance_metrics(a)
    a = _relative_metrics(a)
    return a


def _aggregate_exporter_year(x: pd.DataFrame) -> pd.Series:
    """Collapse one exporter's periods within a mineral-year into one row.

    Grouped by concern rather than listed flat, so the below/above symmetry is
    visible and a new field lands in an obvious place.
    """
    qty = x["pure_qty"].sum()
    return pd.Series({
        # --- volume and activity ---
        "pure_qty": qty,
        "value": x["value"].sum(),
        "shipments": x["shipments"].sum(),
        "periods_active": x["period"].nunique(),
        "thin_periods": int(x["thin_market"].sum()),

        # --- this exporter's own realised price ---
        "exporter_price": x["value"].sum() / qty,
        "price_min": x["price"].min(),
        "price_max": x["price"].max(),
        "disc_min": x["disc_vs_avg_pct"].min(),
        "disc_max": x["disc_vs_avg_pct"].max(),

        # --- the benchmark it was measured against ---
        "peer_avg": (x["peer_avg"] * x["pure_qty"]).sum() / qty,
        "peer_max": (x["peer_max"] * x["pure_qty"]).sum() / qty,
        "peer_avg_excl_self": weighted_mean_skip_na(
            x["peer_avg_excl_self"], x["pure_qty"]),

        # --- under-performance (Worst Traders) ---
        "periods_below_avg": int(x["below_avg"].sum()),
        "qty_below_avg": x.loc[x["below_avg"], "pure_qty"].sum(),
        "forgone_vs_avg": x["forgone_vs_avg"].sum(),
        "forgone_vs_max": x["forgone_vs_max"].sum(),
        "months_below_avg": _period_list(x, "below_avg"),

        # --- out-performance (Best Traders) — exact mirror of the block above ---
        "periods_above_avg": int(x["above_avg"].sum()),
        "qty_above_avg": x.loc[x["above_avg"], "pure_qty"].sum(),
        "gained_vs_avg": x["gained_vs_avg"].sum(),
        "months_above_avg": _period_list(x, "above_avg"),
    })


def _period_list(x: pd.DataFrame, flag_col: str) -> str:
    """The periods matching a flag, as a sorted comma-separated string.

    Stored as text rather than a list so it survives Excel export and
    st.dataframe unchanged. Drives the 'Months' column on the Worst/Best
    Traders tabs, so a user can jump straight to those periods in Exporter
    Detail or Compare Exporters.
    """
    hit = x.loc[x[flag_col], "period"]
    if hit.empty:
        return ""
    return ", ".join(str(p) for p in sorted(hit.unique()))


def _underperformance_metrics(a: pd.DataFrame) -> pd.DataFrame:
    """Worst-Traders ratios: how far below, how often, how much of the tonnage."""
    a["disc_vs_avg_pct"] = (a["peer_avg"] - a["exporter_price"]) / a["peer_avg"]
    a["disc_vs_max_pct"] = (a["peer_max"] - a["exporter_price"]) / a["peer_max"]
    a["consistency"] = a["periods_below_avg"] / a["periods_active"].replace(0, np.nan)
    a["pct_qty_below_avg"] = a["qty_below_avg"] / a["pure_qty"].replace(0, np.nan)
    return a


def _outperformance_metrics(a: pd.DataFrame) -> pd.DataFrame:
    """Best-Traders ratios — the mirror of _underperformance_metrics()."""
    a["premium_consistency"] = a["periods_above_avg"] / a["periods_active"].replace(0, np.nan)
    a["pct_qty_above_avg"] = a["qty_above_avg"] / a["pure_qty"].replace(0, np.nan)
    return a


def _relative_metrics(a: pd.DataFrame) -> pd.DataFrame:
    """Metrics that depend on the exporter's standing among its peers."""
    a["volume_share"] = a["pure_qty"] / a.groupby(["mineral", "year"])["pure_qty"].transform("sum")
    return a


def weighted_mean_skip_na(values: pd.Series, weights: pd.Series) -> float:
    """Volume-weighted mean, ignoring rows where `values` is NaN (e.g. a
    period where the exporter was the only one in the market, so leave-one-out
    is undefined). Returns NaN only if every row is NaN."""
    mask = values.notna()
    if not mask.any() or weights[mask].sum() <= 0:
        return np.nan
    return float((values[mask] * weights[mask]).sum() / weights[mask].sum())


def worst_traders(sc: pd.DataFrame, mineral: str, year: int, n: int = 5,
                  rank_by: str = "forgone_vs_avg",
                  min_pure_qty: float = 0.0) -> pd.DataFrame:
    s = sc[(sc["mineral"] == mineral) & (sc["year"] == year)]
    if min_pure_qty:
        s = s[s["pure_qty"] >= min_pure_qty]
    if s.empty:
        return s
    return s.nlargest(n, rank_by)


def best_traders(sc: pd.DataFrame, mineral: str, year: int, n: int = 5,
                 rank_by: str = "gained_vs_avg",
                 min_pure_qty: float = 0.0) -> pd.DataFrame:
    """Mirror of worst_traders(): exporters who realised MORE than their peers.

    rank_by='gained_vs_avg' ranks by revenue actually earned above the peer
    average (nlargest — prioritises where the extra money is).
    rank_by='disc_vs_avg_pct' ranks by the size of the premium regardless of
    volume (nsmallest — the discount is negative when price exceeds the
    average, so the most negative value is the largest premium).
    """
    s = sc[(sc["mineral"] == mineral) & (sc["year"] == year)]
    if min_pure_qty:
        s = s[s["pure_qty"] >= min_pure_qty]
    if s.empty:
        return s
    if rank_by == "disc_vs_avg_pct":
        return s.nsmallest(n, rank_by)
    return s.nlargest(n, rank_by)
