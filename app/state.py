"""Session state and the recompute pipeline.

Session keys are prefixed `t3i_` (FinIntel R10, confirmed).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
DATASET_XLSX = DATA / "dataset.xlsx"
DATASET_JSON = DATA / "dataset.json"
RULES_HARM = DATA / "rules_harmonisation.json"
RULES_EXCL = DATA / "rules_exclusions.json"
INTL_PRICES = DATA / "intl_prices.json"

from engine import benchmarks_intl, exclusions, harmonise  # noqa: E402


def _read_json(path: Path, fallback):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return fallback


def _load_dataset() -> pd.DataFrame:
    """Load the committed baseline dataset (spec §4.1)."""
    if DATASET_JSON.exists():
        try:
            df = pd.read_json(DATASET_JSON, orient="records")
            if not df.empty and "issuance_date" in df.columns:
                df["issuance_date"] = pd.to_datetime(df["issuance_date"], errors="coerce")
            return df
        except (ValueError, OSError):
            pass
    if DATASET_XLSX.exists():
        try:
            df = pd.read_excel(DATASET_XLSX)
            if "issuance_date" in df.columns:
                df["issuance_date"] = pd.to_datetime(df["issuance_date"], errors="coerce")
            return df
        except (ValueError, OSError):
            pass
    return pd.DataFrame()


def init_state() -> None:
    ss = st.session_state
    if ss.get("t3i_ready"):
        return

    ss["t3i_dataset"] = _load_dataset()
    ss["t3i_baseline_rows"] = len(ss["t3i_dataset"])
    ss["t3i_subtotals"] = pd.DataFrame()
    ss["t3i_rules_harm"] = _read_json(RULES_HARM, harmonise.empty_rules())
    ss["t3i_rules_excl"] = _read_json(RULES_EXCL, exclusions.empty_rules())
    ss["t3i_prices"] = _read_json(INTL_PRICES, benchmarks_intl.default_price_file())
    ss["t3i_batches"] = []
    ss["t3i_dirty"] = False
    ss["t3i_demo"] = False
    ss["t3i_pending"] = None          # staged upload awaiting conflict resolution
    ss["t3i_honour"] = None           # exclusion categories honoured (None = all)
    ss["t3i_basis"] = "Current month"
    ss["t3i_grain"] = "month"
    ss["t3i_window"] = 3
    ss["t3i_prev_grain"] = "month"
    ss["t3i_ready"] = True
    recompute()


def mark_dirty() -> None:
    st.session_state["t3i_dirty"] = True


def recompute() -> None:
    """Re-apply harmonisation and exclusion rules to the whole dataset."""
    ss = st.session_state
    df = ss.get("t3i_dataset")
    if df is None or df.empty:
        ss["t3i_view"] = pd.DataFrame()
        return
    d = harmonise.apply_rules(df, ss["t3i_rules_harm"])
    d = exclusions.apply_rules(d, ss["t3i_rules_excl"])
    ss["t3i_view"] = d


def view() -> pd.DataFrame:
    """The full dataset with rules applied (includes excluded rows)."""
    return st.session_state.get("t3i_view", pd.DataFrame())


def active(honour: list[str] | None = None) -> pd.DataFrame:
    """Rows kept after honouring the selected exclusion categories (spec §6.3)."""
    d = view()
    if d.empty:
        return d
    rules = st.session_state["t3i_rules_excl"]
    h = honour if honour is not None else st.session_state.get("t3i_honour")
    return d[exclusions.active_mask(d, rules, h)]


def has_data() -> bool:
    return not view().empty


# ------------------------------------------------------------------ sidebar --

def sidebar_controls(show_filters: bool = True) -> dict:
    """Global sidebar controls only (R1.5). Returns the active filter set."""
    ss = st.session_state
    sb = st.sidebar

    if ss.get("t3i_demo"):
        sb.warning("🧪 DEMO MODE — synthetic data")
    if ss.get("t3i_dirty"):
        sb.error("⚠️ Unsaved changes")

    filters: dict = {}
    if show_filters and has_data():
        d = view()
        sb.markdown("### Filters")

        years = sorted(int(y) for y in d["year"].dropna().unique())
        if years:
            filters["years"] = sb.multiselect("Year", years, default=years,
                                              key="t3i_f_years")
        minerals = sorted(m for m in d["mineral"].dropna().unique() if m)
        filters["minerals"] = sb.multiselect("Mineral", minerals, default=minerals,
                                             key="t3i_f_minerals")

        cats = ss["t3i_rules_excl"].get("categories", [])
        if cats:
            with sb.expander("Exclusion categories honoured", expanded=False):
                st.caption(
                    "Untick a category to bring those rows back into the "
                    "analyses on this page."
                )
                honoured = [c for c in cats
                            if st.checkbox(c, value=True, key=f"t3i_h_{c}")]
                ss["t3i_honour"] = honoured
    return filters


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    if df.empty or not filters:
        return df
    d = df
    if filters.get("years"):
        d = d[d["year"].isin(filters["years"])]
    if filters.get("minerals"):
        d = d[d["mineral"].isin(filters["minerals"])]
    return d


def page_setup(title: str, show_filters: bool = True) -> dict:
    """Standard page opening: CSS, title, sidebar. Returns active filters."""
    from app.style import inject_css
    inject_css()
    st.title(title)
    return sidebar_controls(show_filters)


def require_data() -> bool:
    """Guard for analysis pages. Returns True if there is data to work with."""
    if has_data():
        return True
    from app.style import info_banner
    info_banner(
        "No data loaded yet. Go to <b>1 · Data Management</b> to upload an MCIS "
        "extract, or load the demo dataset from the Home page."
    )
    return False
