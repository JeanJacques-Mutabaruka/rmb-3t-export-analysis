"""Read, validate, normalise and enrich an MCIS extract.

Spec §3.2, §4.2. No Streamlit imports.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

from .schema import (
    COLUMN_MAP, NUMERIC_COLUMNS, SUBTOTAL_MARKER, FileRejected,
    check_extension, validate_source,
)


def read_workbook(data: bytes | str, filename: str) -> pd.DataFrame:
    """Read an .xls/.xlsx workbook into a raw DataFrame, or raise FileRejected."""
    check_extension(filename)
    src: io.BytesIO | str = io.BytesIO(data) if isinstance(data, bytes) else data

    last_err: Exception | None = None
    for engine in (None, "xlrd", "openpyxl"):
        try:
            if isinstance(src, io.BytesIO):
                src.seek(0)
            kwargs = {"sheet_name": 0}
            if engine:
                kwargs["engine"] = engine
            return pd.read_excel(src, **kwargs)
        except FileRejected:
            raise
        except Exception as exc:  # noqa: BLE001 - try the next engine
            last_err = exc
    raise FileRejected(
        f"File is corrupt or not a readable Excel workbook ({type(last_err).__name__})"
    )


def normalise(raw: pd.DataFrame, filename: str, batch_id: str):
    """Return (records, subtotals).

    records   — analysis rows with canonical + derived columns
    subtotals — source 'Total' rows, kept separately (spec §3.3)
    """
    validate_source(raw, filename)

    df = raw.rename(columns=COLUMN_MAP).copy()
    df = df[[c for c in COLUMN_MAP.values() if c in df.columns]]

    subtotals = df[df["mineral"].astype(str).str.strip() == SUBTOTAL_MARKER].copy()
    d = df[df["mineral"].astype(str).str.strip() != SUBTOTAL_MARKER].copy()
    d = d.reset_index(drop=True)

    # --- types ---
    d["issuance_date"] = pd.to_datetime(d["issuance_date"], errors="coerce")
    for c in NUMERIC_COLUMNS:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    for c in ("mineral", "product", "shipment_no", "certificate_no",
              "exporter_raw", "buyer_raw", "destination_raw"):
        d[c] = d[c].astype(str).str.strip().replace({"nan": ""})

    # --- derived (spec §3.2) ---
    d["year"] = d["issuance_date"].dt.year
    d["year_month"] = d["issuance_date"].dt.to_period("M").astype(str)
    d.loc[d["issuance_date"].isna(), "year_month"] = np.nan
    q = d["issuance_date"].dt.to_period("Q")
    d["quarter"] = q.astype(str)
    d.loc[d["issuance_date"].isna(), "quarter"] = np.nan

    d["pure_quantity_kg"] = d["quantity_kg"] * d["grade_pct"] / 100
    with np.errstate(divide="ignore", invalid="ignore"):
        d["unit_value_usd_kg"] = d["shipment_value_usd"] / d["pure_quantity_kg"]
    d.loc[~np.isfinite(d["unit_value_usd_kg"]), "unit_value_usd_kg"] = np.nan

    d["record_key"] = d["shipment_no"] + "·" + d["certificate_no"]
    d["source_file"] = filename
    d["first_seen_batch"] = batch_id

    # harmonised names default to raw until rules are applied
    d["exporter"] = d["exporter_raw"]
    d["buyer"] = d["buyer_raw"]
    d["destination"] = d["destination_raw"]

    d["exclusion_note"] = ""

    if len(subtotals):
        subtotals = subtotals.copy()
        subtotals["source_file"] = filename

    return d, subtotals


def file_date_range(records: pd.DataFrame):
    """Earliest / latest issuance date in a normalised frame (for ordering)."""
    dates = records["issuance_date"].dropna()
    if dates.empty:
        return None, None
    return dates.min(), dates.max()
