"""2 · Rules & Data Quality — harmonisation approval and exclusion management."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import state  # noqa: E402
from app.downloads import download_button  # noqa: E402
from app.formatting import fmt, fmt_pct  # noqa: E402
from app.style import info_banner, red_alert, section, warn_banner  # noqa: E402
from engine import exclusions, harmonise  # noqa: E402



def _clone(rules: dict) -> dict:
    """Deep-enough copy so a preview can diff before against after."""
    import copy
    return copy.deepcopy(rules)


state.init_state()
state.page_setup("🧹 Rules & Data Quality", show_filters=False)

if not state.require_data():
    st.stop()

top = st.tabs(["🔤 Name Harmonisation", "🚫 Exclusions"])

# ========================================================== harmonisation ====
with top[0]:
    sub = st.tabs(["💡 Proposals", "✅ Approved Rules", "🚫 Never-Merge List"])
    rules = st.session_state["t3i_rules_harm"]
    df = st.session_state["t3i_dataset"]

    # ---------------------------------------------------------- proposals --
    with sub[0]:
        section("Suggested groupings")
        st.caption(
            "Proposals only — nothing is applied until you approve it. The "
            "suggested variants are pre-selected; you can remove any of them, "
            "or add names the matcher missed from the full list below each "
            "proposal."
        )
        c1, c2 = st.columns(2)
        field = c1.selectbox("Field", ["buyer", "exporter", "destination"],
                            key="t3i_h_field")
        threshold = c2.slider("Similarity threshold", 0.60, 1.00, 0.80, 0.01,
                              key="t3i_h_thr")

        raw_col = {"buyer": "buyer_raw", "exporter": "exporter_raw",
                   "destination": "destination_raw"}[field]
        counts = df[raw_col].value_counts()
        all_names = [n for n in counts.index if str(n).strip()]
        proposals = harmonise.propose(df[raw_col], rules, field, threshold)

        if not proposals:
            info_banner("No new groupings proposed at this threshold.")
        else:
            st.caption(f"{len(proposals)} proposal(s). Highest row-impact first.")

        for i, p in enumerate(proposals[:40]):
            with st.expander(
                f"**{p['canonical']}** ← {len(p['variants'])} variant(s) · "
                f"{fmt(p['rows'])} rows · match {p['score']:.2f}"
            ):
                st.dataframe(
                    pd.DataFrame([
                        {"Name": n, "Rows": c,
                         "Role": "canonical" if n == p["canonical"] else "variant"}
                        for n, c in p["counts"].items()
                    ]), width="stretch", hide_index=True)

                canonical = st.text_input("Canonical name", p["canonical"],
                                          key=f"t3i_can_{field}_{i}")

                # Keyword filter over the FULL name list, so the user can pull
                # in names the similarity matcher never proposed.
                kw = st.text_input(
                    "Filter all names by keyword",
                    key=f"t3i_kw_{field}_{i}",
                    placeholder="e.g. halcyon — leave blank to see every name",
                    help="Narrows the picker below. The matcher only proposes "
                         "names above the similarity threshold; use this to add "
                         "spellings it missed.")

                pool = all_names
                if kw.strip():
                    pool = [n for n in all_names if kw.strip().lower() in str(n).lower()]
                # always keep the proposal's own members selectable
                options = list(dict.fromkeys(
                    [*p["variants"], *[n for n in pool if n != canonical]]))

                chosen = st.multiselect(
                    "Variants to merge into it",
                    options,
                    default=[v for v in p["variants"] if v in options],
                    key=f"t3i_var_{field}_{i}",
                    help="Pre-filled with the matcher's suggestions. Add or "
                         "remove freely.")
                if kw.strip():
                    st.caption(
                        f"{len(pool)} name(s) match “{kw.strip()}”. "
                        "Clearing the filter keeps anything already selected.")

                total_rows = int(counts.get(canonical, 0)
                                 + sum(counts.get(v, 0) for v in chosen))
                st.caption(
                    f"Result: **{canonical}** covering {fmt(total_rows)} row(s) "
                    f"from {len(chosen) + 1} spelling(s).")

                a, b = st.columns(2)
                if a.button("✅ APPROVE AND RECOMPUTE", key=f"t3i_ap_{field}_{i}",
                            width="stretch", type="primary"):
                    if not canonical.strip():
                        red_alert("Canonical name cannot be blank.")
                    else:
                        before = _clone(rules)
                        harmonise.add_rule(rules, field, canonical.strip(), chosen)
                        prev = harmonise.preview_change(df, before, rules, field)
                        st.session_state["t3i_last_change"] = prev
                        state.mark_dirty()
                        state.recompute()
                        st.rerun()
                if b.button("❌ REJECT (never merge)", key=f"t3i_rj_{field}_{i}",
                            width="stretch"):
                    words = []
                    for name in [p["canonical"], *p["variants"]]:
                        tokens = [t for t in str(name).upper().split()
                                  if len(t) > 3 and t not in
                                  {"LIMITED", "TRADING", "MINING", "RESOURCES",
                                   "COMPANY", "GROUP", "INTERNATIONAL"}]
                        if tokens:
                            words.append(tokens[0])
                    if len(set(words)) > 1:
                        harmonise.add_never_merge(rules, sorted(set(words)))
                        state.mark_dirty()
                    st.rerun()

        # --------------------------------------------- what just changed --
        last = st.session_state.get("t3i_last_change")
        if last:
            section("Applied — what changed")
            p_ = last
            warn_banner(
                f"{fmt(p_['rows_affected'])} row(s) re-labelled. Distinct "
                f"{p_['field']}s: {fmt(p_['distinct_before'])} \u2192 "
                f"{fmt(p_['distinct_after'])}. Top-5 concentration: "
                f"{fmt_pct(p_['top5_share_before'], already_pct=True)} \u2192 "
                f"{fmt_pct(p_['top5_share_after'], already_pct=True)}. "
                "Every analysis has been recomputed."
            )
            if not p_["examples"].empty:
                st.dataframe(p_["examples"], width="stretch", hide_index=True)
            if st.button("Dismiss", key="t3i_dismiss_change"):
                st.session_state["t3i_last_change"] = None
                st.rerun()

    # ----------------------------------------------------- approved rules --
    with sub[1]:
        section("Approved harmonisation rules")
        rows = [
            {"Field": f, "Canonical": canon, "Variants": len(r.get("variants", [])),
             "Merged names": ", ".join(r.get("variants", []))[:120],
             "Approved": r.get("approved_at", "")}
            for f in ("buyer", "exporter", "destination")
            for canon, r in rules.get(f, {}).items()
        ]
        if not rows:
            info_banner("No rules approved yet.")
        else:
            rdf = pd.DataFrame(rows)
            st.dataframe(rdf, width="stretch", hide_index=True)
            download_button("Harmonisation Rules", {"Rules": rdf},
                            "RMB-3T_HarmonisationRules", key="dl_hr")

            section("Remove a rule")
            labels = [f"{r['Field']} \u00b7 {r['Canonical']}" for r in rows]
            c1, c2 = st.columns([2, 1])
            choice = c1.selectbox("Rule", labels, key="t3i_rm_rule")

            pending = st.session_state.get("t3i_rm_pending")
            if pending != choice:
                if c2.button("Remove (un-merge)", width="stretch",
                             key="t3i_rm_ask"):
                    st.session_state["t3i_rm_pending"] = choice
                    st.rerun()
            else:
                f_, canon_ = choice.split(" \u00b7 ", 1)
                variants = rules.get(f_, {}).get(canon_, {}).get("variants", [])
                warn_banner(
                    f"Remove the rule for <b>{canon_}</b>? "
                    f"{len(variants)} spelling(s) will go back to their original "
                    "text, every analysis will be recomputed, and the grouping "
                    "will reappear on the Proposals tab."
                )
                y_, n_ = st.columns(2)
                if y_.button("Yes, remove and recompute", type="primary",
                             width="stretch", key="t3i_rm_yes"):
                    before = _clone(rules)
                    harmonise.remove_rule(rules, f_, canon_)
                    st.session_state["t3i_last_change"] = harmonise.preview_change(
                        df, before, rules, f_)
                    st.session_state["t3i_rm_pending"] = None
                    state.mark_dirty()
                    state.recompute()
                    st.rerun()
                if n_.button("Cancel", width="stretch", key="t3i_rm_no"):
                    st.session_state["t3i_rm_pending"] = None
                    st.rerun()

    # -------------------------------------------------------- never merge --
    with sub[2]:
        section("Never-merge list")
        st.caption(
            "Keyword groups you have said are different companies. The matcher "
            "will never propose merging names containing these together."
        )
        nm = rules.get("never_merge", [])
        if nm:
            st.dataframe(pd.DataFrame({"Keywords kept apart": [" ↔ ".join(g) for g in nm]}),
                         width="stretch", hide_index=True)
        else:
            info_banner("Empty.")

        c1, c2, c3 = st.columns([2, 2, 1])
        k1 = c1.text_input("Keyword A", key="t3i_nm_a")
        k2 = c2.text_input("Keyword B", key="t3i_nm_b")
        if c3.button("Add", width="stretch") and k1.strip() and k2.strip():
            harmonise.add_never_merge(rules, [k1, k2])
            state.mark_dirty()
            st.rerun()

# ============================================================== exclusions ====
with top[1]:
    sub = st.tabs(["🏷️ Categories", "📋 Rules", "💡 Anomaly Suggestions"])
    er = st.session_state["t3i_rules_excl"]
    d = state.view()

    # ---------------------------------------------------------- categories --
    with sub[0]:
        section("Exclusion categories")
        st.caption(
            "Each category becomes its own YES/blank column in the dataset. "
            "A row is excluded if any category flags it."
        )
        cats = er.get("categories", [])
        counts = [{"Category": c,
                   "Column": exclusions.slug(c),
                   "Rows flagged": int((d.get(exclusions.slug(c), pd.Series(dtype=str))
                                        == "YES").sum())}
                  for c in cats]
        st.dataframe(pd.DataFrame(counts), width="stretch", hide_index=True)

        c1, c2 = st.columns([3, 1])
        new_cat = c1.text_input("New category name", key="t3i_newcat")
        if c2.button("Add category", width="stretch") and new_cat.strip():
            if new_cat.strip() not in cats:
                er.setdefault("categories", []).append(new_cat.strip())
                state.mark_dirty()
                state.recompute()
                st.rerun()

        c3, c4 = st.columns([3, 1])
        rm = c3.selectbox("Category to remove", cats or ["—"], key="t3i_rmcat")
        if c4.button("Remove category", width="stretch") and cats:
            er["categories"] = [c for c in cats if c != rm]
            er["rules"] = [r for r in er.get("rules", []) if r.get("category") != rm]
            state.mark_dirty()
            state.recompute()
            st.rerun()

    # --------------------------------------------------------------- rules --
    with sub[1]:
        section("Exclusion rules")
        rules_list = er.get("rules", [])
        if rules_list:
            rdf = pd.DataFrame([{
                "#": i,
                "Category": r.get("category"),
                "Type": r.get("type"),
                "Definition": (
                    " AND ".join(f"{c['field']} {c['op']} {c['value']}"
                                 for c in r.get("conditions", []))
                    if r.get("type") == "condition"
                    else f"{len(r.get('record_keys', []))} record(s)"),
                "Note": r.get("note", ""),
            } for i, r in enumerate(rules_list)])
            st.dataframe(rdf, width="stretch", hide_index=True)
            download_button("Exclusion Rules", {"Rules": rdf},
                            "RMB-3T_ExclusionRules", key="dl_er")

            c1, c2 = st.columns([3, 1])
            idx = c1.selectbox("Rule to remove", list(range(len(rules_list))),
                               format_func=lambda i: f"#{i} · {rules_list[i].get('category')}",
                               key="t3i_rm_excl")
            if c2.button("Remove rule", width="stretch"):
                er["rules"].pop(idx)
                state.mark_dirty()
                state.recompute()
                st.rerun()
        else:
            info_banner("No exclusion rules defined.")

        section("Add a condition rule")
        fields = ["mineral", "product", "exporter", "buyer", "destination",
                  "shipment_no", "certificate_no", "grade_pct", "quantity_kg",
                  "shipment_value_usd", "unit_value_usd_kg", "year"]
        c1, c2, c3 = st.columns(3)
        f1 = c1.selectbox("Field", fields, key="t3i_ec_f1")
        o1 = c2.selectbox("Operator", list(exclusions.OPERATORS), key="t3i_ec_o1")
        v1 = c3.text_input("Value", key="t3i_ec_v1",
                           help="For 'in', separate values with |")

        use2 = st.checkbox("Add a second condition (ANDed)", key="t3i_ec_use2")
        cond2 = None
        if use2:
            c4, c5, c6 = st.columns(3)
            f2 = c4.selectbox("Field ", fields, key="t3i_ec_f2")
            o2 = c5.selectbox("Operator ", list(exclusions.OPERATORS), key="t3i_ec_o2")
            v2 = c6.text_input("Value ", key="t3i_ec_v2")
            cond2 = {"field": f2, "op": o2, "value": v2}

        c7, c8 = st.columns([2, 2])
        cat = c7.selectbox("Category", er.get("categories", []), key="t3i_ec_cat")
        note = c8.text_input("Note", key="t3i_ec_note")

        if st.button("Add exclusion rule", type="primary") and v1.strip():
            conds = [{"field": f1, "op": o1, "value": v1}]
            if cond2 and str(cond2["value"]).strip():
                conds.append(cond2)
            exclusions.add_condition_rule(er, cat, conds, note)
            state.mark_dirty()
            state.recompute()
            st.rerun()

    # ------------------------------------------------------------ anomalies --
    with sub[2]:
        section("Anomaly suggestions")
        st.caption(
            "Candidates only — nothing is excluded automatically. Accept one to "
            "create a record-level exclusion rule in the chosen category."
        )
        sug = exclusions.suggest(st.session_state["t3i_dataset"])
        if sug.empty:
            info_banner("No anomalies detected.")
        else:
            st.caption(f"{len(sug)} flag(s) across {sug['record_key'].nunique()} record(s).")
            for reason, grp in sug.groupby("reason"):
                with st.expander(f"{reason} — {len(grp)} row(s)"):
                    st.dataframe(
                        grp[["shipment_no", "exporter", "mineral", "detail"]],
                        width="stretch", hide_index=True)
                    c1, c2 = st.columns([2, 1])
                    cat = c1.selectbox(
                        "Exclude these as", er.get("categories", []),
                        index=min(er.get("categories", []).index(
                            grp["suggested_category"].iloc[0])
                            if grp["suggested_category"].iloc[0] in er.get("categories", [])
                            else 0, len(er.get("categories", [])) - 1),
                        key=f"t3i_sg_cat_{abs(hash(reason))}")
                    if c2.button("Accept all", key=f"t3i_sg_acc_{abs(hash(reason))}",
                                 width="stretch"):
                        exclusions.add_record_rule(
                            er, cat, grp["record_key"].tolist(), reason)
                        state.mark_dirty()
                        state.recompute()
                        st.rerun()
            download_button("Anomaly Suggestions", {"Anomalies": sug},
                            "RMB-3T_Anomalies", key="dl_anom")
