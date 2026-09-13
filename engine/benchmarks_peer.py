"""Compatibility shim — the peer-benchmarking logic now lives in engine/peer/.

Kept so that existing call sites using
``from engine import benchmarks_peer as bp`` continue to work unchanged.
New code should prefer ``from engine import peer`` instead.

The split, and why:
    engine/peer/panel.py      shaping shipments into the comparison grid
    engine/peer/benchmark.py  what the market did in each product-period
    engine/peer/evaluate.py   how each exporter compares to that benchmark
"""
from __future__ import annotations

from engine.peer import *  # noqa: F401,F403
from engine.peer import __all__  # noqa: F401

# Private helpers that tests or internal callers may still reach for.
from engine.peer.benchmark import _iqr_bounds  # noqa: F401
from engine.peer.panel import _period  # noqa: F401
