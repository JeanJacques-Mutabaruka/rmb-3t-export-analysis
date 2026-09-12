"""Canonical column schema and input-file validation.

Spec §3.1, §4.2. No Streamlit imports — this module is unit-testable directly.
"""
from __future__ import annotations

import pandas as pd

# Source header -> canonical name (spec §3.1)
COLUMN_MAP: dict[str, str] = {
    "Mineral": "mineral",
    "Product": "product",
    "Shipment Number": "shipment_no",
    "Issuance Date": "issuance_date",
    "Exporter": "exporter_raw",
    "Certificate Number": "certificate_no",
    "Grade": "grade_pct",
    "Quantity(Kg)": "quantity_kg",
    "Buyer": "buyer_raw",
    "Destination": "destination_raw",
    "Export Tax($)": "export_tax_usd",
    "Shipment Value($)": "shipment_value_usd",
    "Traceability Fees": "traceability_fees_usd",
}

EXPECTED_SOURCE_COLUMNS = list(COLUMN_MAP.keys())

NUMERIC_COLUMNS = [
    "grade_pct", "quantity_kg", "export_tax_usd",
    "shipment_value_usd", "traceability_fees_usd",
]

NAME_FIELDS = {
    "exporter": "exporter_raw",
    "buyer": "buyer_raw",
    "destination": "destination_raw",
}

MAIN_MINERALS = ["Cassiterite", "Coltan", "Wolframite"]
SUBTOTAL_MARKER = "Total"

# Display labels
MINERAL_LABEL = {
    "Cassiterite": "Cassiterite (Tin)",
    "Coltan": "Coltan (Tantalum)",
    "Wolframite": "Wolframite (Tungsten)",
}


class FileRejected(Exception):
    """Raised when an uploaded file fails validation (spec §4.2)."""


def validate_source(df: pd.DataFrame | None, filename: str) -> None:
    """Raise FileRejected with the spec §4.2 message if the file is unusable."""
    if df is None:
        raise FileRejected("File is corrupt or not a readable Excel workbook")

    missing = [c for c in EXPECTED_SOURCE_COLUMNS if c not in df.columns]
    if missing:
        raise FileRejected(
            "Not an MCIS 3T export extract — missing columns: " + ", ".join(missing)
        )

    if len(df) == 0:
        raise FileRejected("File contains no data rows")

    certs = df["Certificate Number"].astype(str).str.strip()
    if not (certs.notna() & (certs != "") & (certs.str.lower() != "nan")).any():
        raise FileRejected("No certificate numbers found — cannot establish record keys")


def check_extension(filename: str) -> None:
    if not filename.lower().endswith((".xls", ".xlsx")):
        raise FileRejected("Unsupported file type — expected .xls or .xlsx")
