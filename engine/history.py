"""Historisation — classify incoming records, diff conflicts, append.

Spec §4.3, §4.4. No Streamlit imports.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Fields compared when deciding whether a re-uploaded record has changed.
COMPARE_FIELDS = [
    "mineral", "product", "issuance_date", "exporter_raw", "grade_pct",
    "quantity_kg", "buyer_raw", "destination_raw", "export_tax_usd",
    "shipment_value_usd", "traceability_fees_usd",
]


def _norm(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float, np.floating, np.integer)):
        return round(float(value), 4)
    if isinstance(value, pd.Timestamp):
        return value.normalize().isoformat()
    return str(value).strip()


def classify(existing: pd.DataFrame, incoming: pd.DataFrame):
    """Split incoming into (new, exact_duplicates, conflicts).

    conflicts carries a per-record field diff for the review table (spec §4.3).
    """
    if existing is None or existing.empty:
        return incoming.copy(), incoming.iloc[0:0].copy(), []

    known = existing.set_index("record_key")
    in_keys = incoming["record_key"]

    is_known = in_keys.isin(known.index)
    new = incoming[~is_known].copy()

    exact_idx, conflicts = [], []
    for idx, row in incoming[is_known].iterrows():
        old = known.loc[row["record_key"]]
        if isinstance(old, pd.DataFrame):
            old = old.iloc[0]
        diffs = []
        for f in COMPARE_FIELDS:
            if f not in incoming.columns or f not in known.columns:
                continue
            a, b = _norm(old.get(f)), _norm(row.get(f))
            if a != b:
                diffs.append({"field": f, "existing": a, "incoming": b})
        if diffs:
            conflicts.append({
                "record_key": row["record_key"],
                "shipment_no": row.get("shipment_no"),
                "certificate_no": row.get("certificate_no"),
                "exporter": row.get("exporter_raw"),
                "source_file": row.get("source_file"),
                "diffs": diffs,
                "incoming_row": row,
            })
        else:
            exact_idx.append(idx)

    return new, incoming.loc[exact_idx].copy(), conflicts


def resolve(existing: pd.DataFrame, conflicts: list[dict],
            decisions: dict[str, str]) -> pd.DataFrame:
    """Apply per-record decisions: keep_existing | replace | keep_both."""
    out = existing.copy()
    extra = []

    for c in conflicts:
        key = c["record_key"]
        choice = decisions.get(key, "keep_existing")
        if choice == "replace":
            out = out[out["record_key"] != key]
            extra.append(c["incoming_row"])
        elif choice == "keep_both":
            row = c["incoming_row"].copy()
            row["record_key"] = f"{key}#dup"
            note = str(row.get("exclusion_note") or "")
            flag = "Conflicting duplicate retained for review"
            row["exclusion_note"] = flag if not note else f"{note}; {flag}"
            extra.append(row)

    if extra:
        out = pd.concat([out, pd.DataFrame(extra)], ignore_index=True)
    return out


def append(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if existing is None or existing.empty:
        return new.copy().reset_index(drop=True)
    if new is None or new.empty:
        return existing.copy()
    return pd.concat([existing, new], ignore_index=True)


def batch_record(batch_id: str, files: list[dict], counts: dict) -> dict:
    return {
        "batch_id": batch_id,
        "timestamp": pd.Timestamp.now().isoformat(timespec="seconds"),
        "files_accepted": ", ".join(f["name"] for f in files if f["status"] == "accepted"),
        "files_rejected": ", ".join(
            f"{f['name']} ({f['reason']})" for f in files if f["status"] == "rejected"
        ),
        "rows_read": counts.get("read", 0),
        "new": counts.get("new", 0),
        "exact_duplicates": counts.get("exact", 0),
        "conflicts": counts.get("conflicts", 0),
        "conflicts_replaced": counts.get("replaced", 0),
        "conflicts_kept_both": counts.get("kept_both", 0),
    }
