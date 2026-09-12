"""Exclusions — one column per category, rule evaluation, anomaly suggestions.

Spec §6. No Streamlit imports.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

STARTER_CATEGORIES = [
    "Test record",
    "Valuation error",
    "Grade error",
    "Duplicate declaration",
    "Non-concentrate product",
    "Specialty exporter",
    "Under review",
]

OPERATORS = {
    "==": lambda s, v: s.astype(str).str.strip() == str(v),
    "!=": lambda s, v: s.astype(str).str.strip() != str(v),
    ">": lambda s, v: pd.to_numeric(s, errors="coerce") > float(v),
    ">=": lambda s, v: pd.to_numeric(s, errors="coerce") >= float(v),
    "<": lambda s, v: pd.to_numeric(s, errors="coerce") < float(v),
    "<=": lambda s, v: pd.to_numeric(s, errors="coerce") <= float(v),
    "contains": lambda s, v: s.astype(str).str.contains(str(v), case=False, na=False),
    "in": lambda s, v: s.astype(str).str.strip().isin(
        [x.strip() for x in str(v).split("|")]
    ),
}


def slug(category: str) -> str:
    return "excl_" + re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_")


def empty_rules() -> dict:
    return {"categories": list(STARTER_CATEGORIES), "rules": []}


def add_condition_rule(rules: dict, category: str, conditions: list[dict],
                       note: str = "") -> dict:
    """conditions: [{field, op, value}, ...] — ANDed together."""
    rules.setdefault("rules", []).append({
        "type": "condition",
        "category": category,
        "conditions": conditions,
        "note": note,
        "created_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    })
    return rules


def add_record_rule(rules: dict, category: str, record_keys: list[str],
                    note: str = "") -> dict:
    rules.setdefault("rules", []).append({
        "type": "record",
        "category": category,
        "record_keys": list(record_keys),
        "note": note,
        "created_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    })
    return rules


def category_columns(rules: dict) -> list[str]:
    return [slug(c) for c in rules.get("categories", [])]


def apply_rules(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """Create one YES/blank column per category, plus the master `excluded` flag."""
    d = df.copy()
    cats = rules.get("categories", [])

    for cat in cats:
        d[slug(cat)] = ""

    notes: dict[int, list[str]] = {}

    for rule in rules.get("rules", []):
        cat = rule.get("category")
        if cat not in cats:
            continue
        col = slug(cat)

        if rule["type"] == "record":
            hit = d["record_key"].isin(rule.get("record_keys", []))
        else:
            hit = pd.Series(True, index=d.index)
            for cond in rule.get("conditions", []):
                field, op, val = cond.get("field"), cond.get("op"), cond.get("value")
                if field not in d.columns or op not in OPERATORS:
                    hit = pd.Series(False, index=d.index)
                    break
                hit &= OPERATORS[op](d[field], val).fillna(False)

        d.loc[hit, col] = "YES"
        if rule.get("note"):
            for idx in d.index[hit]:
                notes.setdefault(idx, []).append(rule["note"])

    cols = [slug(c) for c in cats]
    d["excluded"] = np.where((d[cols] == "YES").any(axis=1), "YES", "") if cols else ""

    if notes:
        existing = d["exclusion_note"].fillna("").astype(str)
        for idx, texts in notes.items():
            merged = "; ".join(dict.fromkeys(texts))
            prior = existing.at[idx]
            d.at[idx, "exclusion_note"] = merged if not prior else f"{prior}; {merged}"
    return d


def active_mask(df: pd.DataFrame, rules: dict,
                honour: list[str] | None = None) -> pd.Series:
    """Rows to KEEP. `honour` lists the categories to apply (spec §6.3).

    honour=None means honour every category.
    """
    cats = rules.get("categories", [])
    honour = cats if honour is None else honour
    cols = [slug(c) for c in honour if slug(c) in df.columns]
    if not cols:
        return pd.Series(True, index=df.index)
    return ~(df[cols] == "YES").any(axis=1)


# ---------------------------------------------------------------- anomalies --

def suggest(df: pd.DataFrame, iqr_factor: float = 3.0) -> pd.DataFrame:
    """Propose exclusion candidates — never applied automatically (spec §6.5)."""
    flags: list[dict] = []
    d = df

    for mineral, sub in d.groupby("mineral"):
        uv = sub["unit_value_usd_kg"].dropna()
        if len(uv) < 20:
            continue
        fence = uv.quantile(0.99) * iqr_factor
        for _, r in sub[sub["unit_value_usd_kg"] > fence].iterrows():
            flags.append({
                "record_key": r["record_key"], "shipment_no": r["shipment_no"],
                "exporter": r["exporter_raw"], "mineral": mineral,
                "detail": f"${r['unit_value_usd_kg']:,.0f}/kg vs 99th pct ${uv.quantile(0.99):,.0f}",
                "suggested_category": "Valuation error",
                "reason": f"Unit value exceeds {iqr_factor:g}x the 99th percentile for {mineral}",
            })

    dup = d[d.duplicated("shipment_no", keep=False)]
    for sn, sub in dup.groupby("shipment_no"):
        if not sn:
            continue
        if sub["exporter_raw"].nunique() > 1:
            for _, r in sub.iterrows():
                flags.append({
                    "record_key": r["record_key"], "shipment_no": sn,
                    "exporter": r["exporter_raw"], "mineral": r["mineral"],
                    "detail": ", ".join(sorted(sub["exporter_raw"].unique())),
                    "suggested_category": "Duplicate declaration",
                    "reason": "Same shipment number used by different exporters",
                })
        g = sub["grade_pct"].dropna()
        if len(g) > 1 and g.min() > 0 and 50 <= (g.max() / g.min()) <= 200:
            for _, r in sub.iterrows():
                flags.append({
                    "record_key": r["record_key"], "shipment_no": sn,
                    "exporter": r["exporter_raw"], "mineral": r["mineral"],
                    "detail": f"{g.min():g}% vs {g.max():g}%",
                    "suggested_category": "Grade error",
                    "reason": "Grade differs ~100x within one shipment — misplaced decimal",
                })
        if (sub["exporter_raw"].nunique() == 1 and sub["grade_pct"].nunique() == 1
                and sub["quantity_kg"].nunique() == 1
                and sub["shipment_value_usd"].nunique() > 1):
            vmin, vmax = sub["shipment_value_usd"].min(), sub["shipment_value_usd"].max()
            for _, r in sub.iterrows():
                flags.append({
                    "record_key": r["record_key"], "shipment_no": sn,
                    "exporter": r["exporter_raw"], "mineral": r["mineral"],
                    "detail": f"${vmin:,.0f} vs ${vmax:,.0f}",
                    "suggested_category": "Valuation error",
                    "reason": "Identical grade and quantity declared at different values",
                })

    pat = re.compile(r"qqq|zzz|xxx|test|0000000|2222222|1111111", re.I)
    for _, r in d[d["shipment_no"].astype(str).str.contains(pat, na=False)].iterrows():
        flags.append({
            "record_key": r["record_key"], "shipment_no": r["shipment_no"],
            "exporter": r["exporter_raw"], "mineral": r["mineral"],
            "detail": r["shipment_no"],
            "suggested_category": "Test record",
            "reason": "Placeholder-looking shipment number",
        })

    # product declared under a mineral it does not belong to
    dominant = (
        d.groupby(["product", "mineral"], observed=True)["shipment_value_usd"]
        .sum().reset_index()
        .sort_values("shipment_value_usd", ascending=False)
        .drop_duplicates("product").set_index("product")["mineral"]
    )
    expected = d["product"].map(dominant)
    mismatch = d[(expected.notna()) & (d["mineral"] != expected)]
    for idx, r in mismatch.iterrows():
        flags.append({
            "record_key": r["record_key"], "shipment_no": r["shipment_no"],
            "exporter": r["exporter_raw"], "mineral": r["mineral"],
            "detail": f"{r['product']} declared as {r['mineral']}, "
                      f"normally {expected.at[idx]}",
            "suggested_category": "Under review",
            "reason": "Product/mineral mismatch — product is usually declared "
                      "under a different mineral",
        })

    cols = ["record_key", "shipment_no", "exporter", "mineral", "detail",
            "suggested_category", "reason"]
    if not flags:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(flags).drop_duplicates(subset=["record_key", "reason"])[cols]
