"""International benchmark prices and the Rwanda price gap.

Spec §7.1. No Streamlit imports.

PROVENANCE MATTERS. Tin is exchange-traded and continuous. Tantalum and
tungsten concentrate are not — the public record is annual USGS averages plus a
few spot points. Every point carries a tag and every tag is shown in the UI.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REAL = "REAL"
INTERPOLATED = "INTERPOLATED"
ASSUMPTION = "ASSUMPTION"
OVERRIDE = "USER OVERRIDE"

BASIS_LABEL = {
    "Cassiterite": "$/kg contained Sn — vs LME tin",
    "Coltan": "$/kg contained Ta2O5 — vs tantalite concentrate",
    "Wolframite": "$/kg contained WO3 — vs tungsten concentrate",
}

# --- LME tin cash settlement, monthly averages, $/tonne (westmetall.com) -----
LME_TIN = {
    2019: [20480.00, 21268.00, 21444.29, 20683.75, 19530.95, 19176.50,
           17991.30, 16577.14, 16839.76, 16603.04, 16369.29, 17093.25],
    2020: [17071.14, 16456.50, 15321.41, 15039.35, 15408.53, 16806.27,
           17452.96, 17671.90, 17945.95, 18154.09, 18567.90, 19727.33],
    2021: [21955.45, 26717.30, 27396.30, 28508.10, 32524.26, 32677.73,
           34183.00, 35252.62, 35048.23, 37962.38, 39332.73, 39573.81],
    2022: [41807.00, 44117.75, 44248.91, 43121.58, 35944.76, 31776.75,
           25173.10, 24511.36, 21257.95, 19406.19, 21136.36, 24099.00],
    2023: [28080.71, 27069.50, 24014.35, 25886.11, 25609.75, 27262.73,
           28751.43, 25995.23, 25558.57, 24617.73, 24221.14, 24606.32],
    2024: [25211.36, 26156.67, 27446.00, 31844.76, 33153.33, 32228.75,
           32003.91, 31512.14, 31643.81, 32217.17, 29768.33, 28877.75],
    2025: [29618.18, 31876.25, 34026.19, 32691.25, 32143.50, 32475.48,
           33693.48, 33870.00, 34540.00, 36045.87, 37015.75, 41352.14],
    2026: [49903.81, 48675.00, 47515.45, 48941.75, 53687.37, 53357.50,
           53101.74, 55654.00, 54572.78],
}

# --- Tantalum: USGS / CRU annual averages, $/kg Ta2O5 ------------------------
TA_ANNUAL = {2019: 161.0, 2020: 158.0, 2021: 158.0, 2022: 206.5,
             2023: 190.0, 2024: 167.0}
TA_2025_NOV = 180.0     # USGS MCS2026 Nov-2025 figure
TA_2026_JAN = 230.0     # back-calculated from Argus "+43% YTD by 19 Feb 2026"
TA_2026_FEB = 336.0     # Argus concentrate spot, 19 Feb 2026

# --- Tungsten: USGS annual averages, $/mtu WO3 in-warehouse Rotterdam --------
W_ANNUAL_MTU = {2019: 198.0, 2020: 172.0, 2021: 225.0, 2022: 275.0,
                2023: 258.0, 2024: 252.0, 2025: 380.0}
W_2026_START = 80.0     # Fastmarkets $750-850/mtu midpoint, start of 2026
W_2026_MAY = 265.0      # Fastmarkets $2,500-2,800/mtu, held since 29 May 2026


def _tin():
    out = {}
    for y, vals in LME_TIN.items():
        for m, v in enumerate(vals, start=1):
            out[(y, m)] = (v / 1000.0, REAL,
                           "LME tin cash settlement, monthly average (westmetall.com)")
    return out


def _tantalum():
    out = {}
    for y, v in TA_ANNUAL.items():
        for m in range(1, 13):
            out[(y, m)] = (v, REAL, f"USGS/CRU annual average tantalite {y}, $/kg Ta2O5")
    start = TA_ANNUAL[2024]
    for m in range(1, 13):
        if m <= 11:
            out[(2025, m)] = (start + (TA_2025_NOV - start) * (m / 11), INTERPOLATED,
                              "Interpolated Dec-2024 to the USGS Nov-2025 anchor ($180/kg)")
        else:
            out[(2025, m)] = (TA_2025_NOV, INTERPOLATED, "Held at the USGS Nov-2025 anchor")
    out[(2026, 1)] = (TA_2026_JAN, INTERPOLATED,
                      "Back-calculated from Argus '+43% YTD by 19 Feb 2026'")
    out[(2026, 2)] = (TA_2026_FEB, REAL, "Argus tantalite concentrate spot, 19 Feb 2026")
    for m in range(3, 13):
        out[(2026, m)] = (TA_2026_FEB, ASSUMPTION,
                          "NO public data found after Feb-2026 — held flat. Very likely an "
                          "UNDERESTIMATE; override if you have a better figure.")
    return out


def _tungsten():
    out = {}
    for y, mtu in W_ANNUAL_MTU.items():
        for m in range(1, 13):
            out[(y, m)] = (mtu / 10.0, REAL,
                           f"USGS annual average concentrate {y}, ${mtu:g}/mtu WO3 "
                           "in-warehouse Rotterdam")
    for m in range(1, 5):
        out[(2026, m)] = (W_2026_START, REAL,
                          "Fastmarkets concentrate $750-850/mtu at start of 2026 "
                          "(midpoint), applied flat Jan-Apr pending monthly detail")
    for m in range(5, 13):
        out[(2026, m)] = (W_2026_MAY, REAL,
                          "Fastmarkets concentrate $2,500-2,800/mtu (midpoint), "
                          "held at this range since 29 May 2026")
    return out


SERIES = {"Cassiterite": _tin(), "Coltan": _tantalum(), "Wolframite": _tungsten()}


def default_price_file() -> dict:
    out = {}
    for mineral, series in SERIES.items():
        out[mineral] = {
            f"{y}-{m:02d}": {"price": round(v, 4), "basis": tag, "note": note}
            for (y, m), (v, tag, note) in sorted(series.items())
        }
    return out


def load_prices(path: Path | str) -> dict:
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text())
    return default_price_file()


def lookup(prices: dict, mineral: str, year: int, month: int):
    entry = prices.get(mineral, {}).get(f"{year}-{month:02d}")
    if not entry:
        return np.nan, ASSUMPTION, "No benchmark available for this month"
    return entry.get("price", np.nan), entry.get("basis", ASSUMPTION), entry.get("note", "")


def set_override(prices: dict, mineral: str, year: int, month: int,
                 price: float) -> dict:
    prices.setdefault(mineral, {})[f"{year}-{month:02d}"] = {
        "price": float(price), "basis": OVERRIDE,
        "note": f"Set manually in the app on "
                f"{pd.Timestamp.now().isoformat(timespec='minutes')}",
    }
    return prices
