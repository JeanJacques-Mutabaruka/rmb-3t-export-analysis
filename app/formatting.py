"""Display formatting. Comma thousands separators (confirmed override).

RMB_UI_Design_System.md §4 — centralised so there is one place to change.
"""
from __future__ import annotations

import pandas as pd

NA = "—"


def fmt(value, decimals: int = 0) -> str:
    """Comma-grouped number: 1250000 -> '1,250,000'."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return NA
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return NA


def fmt_money(value, decimals: int = 2) -> str:
    """'$' + fmt(), minus sign kept OUTSIDE the '$'."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return NA
    try:
        v = float(value)
    except (TypeError, ValueError):
        return NA
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.{decimals}f}"


def fmt_money_m(value, decimals: int = 1) -> str:
    """Millions, for headline metrics."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return NA
    return fmt_money(float(value) / 1e6, decimals) + "M"


def fmt_pct(value, decimals: int = 1, already_pct: bool = False) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return NA
    try:
        v = float(value)
    except (TypeError, ValueError):
        return NA
    if not already_pct:
        v *= 100
    return f"{v:,.{decimals}f}%"


def fmt_date(value) -> str:
    """dd-mmm-yyyy — never an ambiguous numeric format (R8.2)."""
    if value is None or pd.isna(value):
        return NA
    try:
        return pd.Timestamp(value).strftime("%d-%b-%Y")
    except (TypeError, ValueError):
        return NA


# Column -> pandas Styler format string, applied by style_table()
MONEY_COLS = {
    "value", "export_value", "shipment_value_usd", "export_tax_usd",
    "traceability_fees_usd", "forgone_vs_avg", "forgone_vs_max",
    "loss_signed", "loss_floored", "Total", "Cumulative",
}
PRICE_COLS = {
    "price", "exporter_price", "peer_avg", "peer_max", "peer_min", "peer_range",
    "rwanda_price", "benchmark", "gap", "unit_value_usd_kg",
}
PCT_COLS = {
    "disc_vs_avg_pct", "disc_vs_max_pct", "gap_pct", "consistency",
    "volume_share", "share_pct", "cumulative_pct",
}
QTY_COLS = {"pure_qty", "quantity_kg", "pure_quantity_kg", "Quantity"}


def table_formats(df) -> dict:
    """Build a Styler format map from column names."""
    fmts: dict[str, str] = {}
    for c in df.columns:
        lc = str(c)
        if lc in MONEY_COLS:
            fmts[c] = "${:,.0f}"
        elif lc in PRICE_COLS:
            fmts[c] = "${:,.2f}"
        elif lc in PCT_COLS:
            fmts[c] = "{:.1%}"
        elif lc in QTY_COLS:
            fmts[c] = "{:,.0f}"
    return fmts


def style_breach_rows(df, mask_col: str, colour: str = "#FDECEA"):
    """Row-level highlight. Works on st.dataframe, NOT on st.data_editor."""
    def _row(row):
        hit = bool(row.get(mask_col))
        return [f"background-color: {colour}" if hit else ""] * len(row)
    return df.style.apply(_row, axis=1)
