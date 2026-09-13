"""Benchmark construction — what the MARKET did in each product-period.

One question: *what was the going rate, and how wide was the spread?*

Knows nothing about any individual exporter's performance; that is
evaluate.py's job. No Streamlit imports.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .panel import THIN_MARKET_THRESHOLD

OUTLIER_IQR_FACTOR = 3.0       # multiplier on the interquartile range
OUTLIER_MIN_EXPORTERS = 5      # quartiles are not meaningful below this


def _iqr_bounds(prices: pd.Series) -> tuple[float, float] | None:
    """(lower, upper) fence at OUTLIER_IQR_FACTOR x IQR, or None if too few
    points to make quartiles meaningful."""
    if len(prices) < OUTLIER_MIN_EXPORTERS:
        return None
    q1, q3 = prices.quantile(0.25), prices.quantile(0.75)
    iqr = q3 - q1
    if iqr <= 0:
        # The middle 50% has zero spread (e.g. every price but one is
        # identical). A zero-width IQR must NOT be read as "no meaningful
        # bound" - the correct reading is the opposite: the mainstream cluster
        # is this tight, so anything outside a tiny tolerance around it really
        # is an outlier. A near-zero relative tolerance still allows exact
        # ties without flagging them.
        tol = max(abs(q1) * 1e-9, 1e-9)
        return q1 - tol, q3 + tol
    return q1 - OUTLIER_IQR_FACTOR * iqr, q3 + OUTLIER_IQR_FACTOR * iqr


def peer_stats(ep: pd.DataFrame, grain: str = "month", window: int = 1
              ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Average / Max / Min / Range per product x period over a rolling window.

    Returns (stats, outliers).

    stats carries TWO versions of Max/Min/Range/Avg:
      - peer_avg / peer_max / peer_min / peer_range  — the FULL peer set,
        unchanged. Discount %, Value Forgone and Worst Traders are computed
        from THESE and are not affected by outlier removal.
      - peer_avg_clean / peer_max_clean / peer_min_clean / peer_range_clean —
        the same statistics with extreme exporter-period prices removed
        (see _iqr_bounds). Intended for the Peer Statistics DISPLAY only, so a
        single corrupted record does not make a chart or a range figure
        meaningless.

    outliers lists exactly which exporter-period rows were excluded from the
    _clean columns and why, for the Outliers Excluded tab.

    window_value_sum / window_qty_sum are the raw totals behind peer_avg,
    carried through so discounts() can compute a leave-one-out average
    without re-deriving the window.
    """
    rows: list[dict] = []
    outlier_rows: list[dict] = []

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

            bounds = _iqr_bounds(w["price"])
            if bounds is None:
                clean, flagged = w, w.iloc[0:0]
            else:
                lower, upper = bounds
                is_out = (w["price"] < lower) | (w["price"] > upper)
                clean, flagged = w[~is_out], w[is_out]

            for _, r in flagged.iterrows():
                outlier_rows.append({
                    "product": product, "period": p, "exporter": r["exporter"],
                    "price": r["price"], "pure_qty": r["pure_qty"],
                    "peer_median": w["price"].median(),
                    "fence_low": bounds[0] if bounds else np.nan,
                    "fence_high": bounds[1] if bounds else np.nan,
                })

            use_clean = clean if not clean.empty else w
            rows.append({
                "product": product,
                "period": p,
                "peer_avg": w["value"].sum() / w["pure_qty"].sum(),
                "peer_max": w["price"].max(),
                "peer_min": w["price"].min(),
                "peer_avg_clean": use_clean["value"].sum() / use_clean["pure_qty"].sum(),
                "peer_max_clean": use_clean["price"].max(),
                "peer_min_clean": use_clean["price"].min(),
                "n_outliers_excluded": int(len(flagged)),
                "n_exporters": int(w["exporter"].nunique()),
                "n_shipments": int(w["shipments"].sum()),
                "window_periods": len(window_periods),
                "window_value_sum": w["value"].sum(),
                "window_qty_sum": w["pure_qty"].sum(),
            })

    out = pd.DataFrame(rows)
    if out.empty:
        return out, pd.DataFrame(columns=[
            "product", "period", "exporter", "price", "pure_qty",
            "peer_median", "fence_low", "fence_high"])
    out["peer_range"] = out["peer_max"] - out["peer_min"]
    out["peer_range_clean"] = out["peer_max_clean"] - out["peer_min_clean"]
    out["thin_market"] = out["n_exporters"] < THIN_MARKET_THRESHOLD
    return out, pd.DataFrame(outlier_rows)
