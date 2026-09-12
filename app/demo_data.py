"""Synthetic demo data — FinIntel R13.

Plausible but entirely fictional Rwandan 3T export declarations spanning six
years. Exporter, buyer and destination names are invented; any resemblance to
real companies is coincidental. Deliberately seeded with the same KINDS of
data problems the real extracts contain, so the cleaning and anomaly workflows
can be demonstrated without real data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SEED = 20260912

EXPORTERS = [
    "Kivu Ridge Minerals Ltd", "Akagera Resources Ltd", "Nyungwe Mining Co",
    "Virunga Trading Ltd", "Muhazi Minerals SARL", "Rusizi Ore Exporters Ltd",
    "Gishwati Metals Ltd", "Bugesera Commodities Ltd", "Karongi Mining Ltd",
    "Rwamagana Ore Ltd", "Nyabarongo Minerals Ltd", "Sebeya Resources Ltd",
]
BUYERS = [
    "Helvetia Metals S.A", "Orient Alloy Trading Ltd", "Pacific Ore Partners Pte",
    "Meridian Commodities FZE", "Anhui Rare Metals Co., Ltd",
    "Northstar Refining Inc.", "Baltic Metal Works GmbH", "Sunrise Tungsten Ltd",
]
# Deliberate spelling variants, for the harmonisation workflow
BUYER_VARIANTS = {
    "Helvetia Metals S.A": ["Helvetia Metals S.A.", "HELVETIA METALS S.A",
                            "Helvetia  Metals S.A"],
    "Orient Alloy Trading Ltd": ["ORIENT ALLOY TRADING LTD",
                                 "Orient Alloy Trading Limited"],
    "Anhui Rare Metals Co., Ltd": ["ANHUI RARE METALS CO.,LTD",
                                   "Anhui Rare Metals Co.,Ltd "],
}
DESTINATIONS = ["China", "United Arab Emirates", "Thailand", "Singapore",
                "Malaysia", "Netherlands", "Belgium", "India"]

PRODUCTS = {
    "Cassiterite": ("Tin concentrate", 62.0, 4.0, 14.0),
    "Coltan": ("Tantalum concentrate", 27.0, 3.5, 120.0),
    "Wolframite": ("Tungsten concentrate", 57.0, 8.0, 16.0),
}
PREFIX = {"Cassiterite": "SN", "Coltan": "TA", "Wolframite": "WO"}

# Rough price trajectory multipliers by year, so trends are visible
YEAR_FACTOR = {2020: 1.00, 2021: 1.55, 2022: 1.60, 2023: 1.42,
               2024: 1.60, 2025: 1.85, 2026: 2.90}


def generate() -> pd.DataFrame:
    """Return a frame with the same SOURCE column names as a real MCIS extract."""
    rng = np.random.default_rng(SEED)
    rows: list[dict] = []
    cert = 1000
    ship = 100

    for year, factor in YEAR_FACTOR.items():
        n_months = 12 if year < 2026 else 9
        for month in range(1, n_months + 1):
            for mineral, (product, g_mean, g_sd, base_price) in PRODUCTS.items():
                n = int(rng.integers(4, 11))
                for _ in range(n):
                    cert += 1
                    ship += 1
                    exporter = str(rng.choice(EXPORTERS))
                    buyer = str(rng.choice(BUYERS))
                    if buyer in BUYER_VARIANTS and rng.random() < 0.35:
                        buyer = str(rng.choice(BUYER_VARIANTS[buyer]))

                    grade = float(np.clip(rng.normal(g_mean, g_sd), 1.0, 99.0))
                    qty = float(rng.uniform(8_000, 30_000))
                    day = int(rng.integers(1, 28))

                    # exporter-specific persistent discount, so peer analysis bites
                    skew = 1.0 - (EXPORTERS.index(exporter) % 5) * 0.035
                    price = base_price * factor * skew * float(rng.normal(1.0, 0.05))
                    price = max(price, 1.0)
                    pure = qty * grade / 100
                    value = pure * price

                    rows.append({
                        "Mineral": mineral,
                        "Product": product,
                        "Shipment Number": f"{PREFIX[mineral]}/RW/{ship:07d}",
                        "Issuance Date": f"{month}/{day}/{year} 10:30:00 AM",
                        "Exporter": exporter,
                        "Certificate Number": f"RWD{cert:06d}",
                        "Grade": round(grade, 2),
                        "Quantity(Kg)": round(qty, 2),
                        "Buyer": buyer,
                        "Destination": str(rng.choice(DESTINATIONS)),
                        "Export Tax($)": round(value * 0.04, 2),
                        "Shipment Value($)": round(value, 2),
                        "Traceability Fees": round(qty * 0.18, 2),
                    })

    df = pd.DataFrame(rows)

    # --- seeded data problems, mirroring the real extracts -------------------
    # 1. a corrupted value twin (same shipment, absurd value)
    twin = df.iloc[10].copy()
    twin["Certificate Number"] = "RWD900001"
    twin["Shipment Value($)"] = twin["Shipment Value($)"] * 300
    twin["Export Tax($)"] = twin["Shipment Value($)"] * 0.04
    # 2. a misplaced decimal in grade
    gtwin = df.iloc[40].copy()
    gtwin["Certificate Number"] = "RWD900002"
    gtwin["Grade"] = round(float(gtwin["Grade"]) / 100, 4)
    # 3. a placeholder/test record
    test = df.iloc[70].copy()
    test["Certificate Number"] = "RWD900003"
    test["Shipment Number"] = "999/qqqqq/2222222"
    # 4. identical grade+quantity declared at two different values
    vtwin = df.iloc[95].copy()
    vtwin["Certificate Number"] = "RWD900004"
    vtwin["Shipment Value($)"] = round(float(vtwin["Shipment Value($)"]) * 1.4, 2)
    # 5. a subtotal row, as the source files contain
    subtotal = {c: "" for c in df.columns}
    subtotal.update({
        "Mineral": "Total",
        "Quantity(Kg)": df["Quantity(Kg)"].sum(),
        "Export Tax($)": df["Export Tax($)"].sum(),
        "Shipment Value($)": df["Shipment Value($)"].sum(),
        "Traceability Fees": df["Traceability Fees"].sum(),
    })

    extras = pd.DataFrame([twin, gtwin, test, vtwin, pd.Series(subtotal)])
    return pd.concat([df, extras], ignore_index=True)
