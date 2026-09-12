"""Name harmonisation — proposals, rules and change preview.

Spec §5. No Streamlit imports.
"""
from __future__ import annotations

from difflib import SequenceMatcher

import pandas as pd

from .schema import NAME_FIELDS

DEFAULT_THRESHOLD = 0.80


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.upper().strip(), b.upper().strip()).ratio()


def empty_rules() -> dict:
    return {"exporter": {}, "buyer": {}, "destination": {}, "never_merge": []}


def _blocked(members: list[str], never_merge: list[list[str]]) -> list[list[str]] | None:
    """Split a cluster that mixes keyword groups the user has said never to merge."""
    for group in never_merge:
        present = [kw for kw in group if any(kw.upper() in m.upper() for m in members)]
        if len(present) > 1:
            buckets: dict[str, list[str]] = {kw: [] for kw in present}
            leftovers: list[str] = []
            for m in members:
                for kw in present:
                    if kw.upper() in m.upper():
                        buckets[kw].append(m)
                        break
                else:
                    leftovers.append(m)
            out = [v for v in buckets.values() if v]
            if leftovers:
                out.append(leftovers)
            return out
    return None


def propose(values: pd.Series, rules: dict, field: str,
            threshold: float = DEFAULT_THRESHOLD) -> list[dict]:
    """Suggest groupings for names not already covered by a locked rule.

    Returns a list of proposals: {canonical, variants, counts, score}.
    Proposals are suggestions only — nothing is applied until approved (§5.3).
    """
    counts = values.value_counts()
    field_rules = rules.get(field, {})
    never = rules.get("never_merge", [])

    covered: set[str] = set()
    for canon, rule in field_rules.items():
        covered.add(canon)
        covered.update(rule.get("variants", []))

    names = [n for n in counts.index if n not in covered and str(n).strip()]
    assigned: set[str] = set()
    clusters: list[list[str]] = []

    for name in names:
        if name in assigned:
            continue
        members = [name]
        assigned.add(name)
        for other in names:
            if other in assigned:
                continue
            if _similar(name, other) >= threshold:
                members.append(other)
                assigned.add(other)
        clusters.append(members)

    final: list[list[str]] = []
    for members in clusters:
        split = _blocked(members, never)
        final.extend(split if split else [members])

    proposals = []
    for members in final:
        if len(members) < 2:
            continue
        canon = max(members, key=lambda m: counts[m])
        others = [m for m in members if m != canon]
        proposals.append({
            "field": field,
            "canonical": canon,
            "variants": others,
            "counts": {m: int(counts[m]) for m in members},
            "rows": int(sum(counts[m] for m in members)),
            "score": min(_similar(canon, m) for m in others),
        })
    proposals.sort(key=lambda p: -p["rows"])
    return proposals


def add_rule(rules: dict, field: str, canonical: str, variants: list[str],
             approved_by: str = "user") -> dict:
    rules.setdefault(field, {})[canonical] = {
        "variants": list(variants),
        "approved_by": approved_by,
        "approved_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "locked": True,
    }
    return rules


def remove_rule(rules: dict, field: str, canonical: str) -> dict:
    rules.get(field, {}).pop(canonical, None)
    return rules


def add_never_merge(rules: dict, keywords: list[str]) -> dict:
    pair = [k.strip().upper() for k in keywords if k.strip()]
    if len(pair) >= 2 and pair not in rules.setdefault("never_merge", []):
        rules["never_merge"].append(pair)
    return rules


def mapping_for(rules: dict, field: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for canon, rule in rules.get(field, {}).items():
        out[canon] = canon
        for v in rule.get("variants", []):
            out[v] = canon
    return out


def apply_rules(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """Write harmonised names into `exporter` / `buyer` / `destination`."""
    d = df.copy()
    for field, raw_col in NAME_FIELDS.items():
        mapping = mapping_for(rules, field)
        d[field] = d[raw_col].map(lambda v: mapping.get(v, v))
    return d


def preview_change(df: pd.DataFrame, rules_before: dict, rules_after: dict,
                   field: str) -> dict:
    """What a rule change would do, before it is applied (spec §5.4)."""
    raw_col = NAME_FIELDS[field]
    before = apply_rules(df, rules_before)[field]
    after = apply_rules(df, rules_after)[field]
    changed = (before != after)

    def top5_share(series: pd.Series) -> float:
        tot = df.groupby(series)["shipment_value_usd"].sum()
        if tot.sum() == 0:
            return 0.0
        return float(tot.nlargest(5).sum() / tot.sum() * 100)

    return {
        "field": field,
        "rows_affected": int(changed.sum()),
        "distinct_before": int(before.nunique()),
        "distinct_after": int(after.nunique()),
        "top5_share_before": top5_share(before),
        "top5_share_after": top5_share(after),
        "examples": (
            pd.DataFrame({"From": before[changed], "To": after[changed]})
            .drop_duplicates().head(20)
        ),
    }
