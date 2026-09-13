"""Peer (internal) benchmarking — exporters vs their Rwandan peers.

Spec §7.2, §7.3. Peer group = same `product` in the same period.

Split into three modules by the question each answers:

    panel.py      who traded what, when, at what realised price
    benchmark.py  what the market did in each product-period
    evaluate.py   how each exporter compares to that benchmark

This package re-exports the full public API, so
``from engine.peer import peer_stats`` and the legacy
``from engine import benchmarks_peer as bp`` both keep working unchanged.
"""
from __future__ import annotations

from .benchmark import (
    OUTLIER_IQR_FACTOR,
    OUTLIER_MIN_EXPORTERS,
    peer_stats,
)
from .evaluate import (
    best_traders,
    discounts,
    scorecard,
    weighted_mean_skip_na,
    worst_traders,
)
from .panel import (
    BASIS_PRESETS,
    THIN_MARKET_THRESHOLD,
    exporter_periods,
    product_mineral_map,
)

__all__ = [
    # panel
    "BASIS_PRESETS",
    "THIN_MARKET_THRESHOLD",
    "exporter_periods",
    "product_mineral_map",
    # benchmark
    "OUTLIER_IQR_FACTOR",
    "OUTLIER_MIN_EXPORTERS",
    "peer_stats",
    # evaluate
    "discounts",
    "scorecard",
    "worst_traders",
    "best_traders",
    "weighted_mean_skip_na",
]
