"""1 · Data Management — upload, validate, resolve conflicts, commit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import state  # noqa: E402
from app.downloads import build_workbook, download_button, stamp  # noqa: E402
from app.formatting import fmt, fmt_date, fmt_money, table_formats  # noqa: E402
from app.style import info_banner, red_alert, section, warn_banner  # noqa: E402
from engine import github_sync, history, ingest  # noqa: E402
from engine.schema import FileRejected  # noqa: E402



def _github_target():
    """Read the optional [github] secrets block. Absent secrets is normal."""
    try:
        cfg = st.secrets.get("github", {})
    except Exception:  # noqa: BLE001 — no secrets file at all
        return None
    if not cfg:
        return None
    return github_sync.RepoTarget(
        owner=str(cfg.get("owner", "")).strip(),
        repo=str(cfg.get("repo", "")).strip(),
        branch=str(cfg.get("branch", "main")).strip() or "main",
        token=str(cfg.get("token", "")).strip(),
    )


state.init_state()
filters = state.page_setup("📥 Data Management", show_filters=False)

tabs = st.tabs(["📤 Upload & Validate", "🔍 Resolve Conflicts", "📚 Dataset",
                "🕓 Ingestion History", "💾 Save & Commit"])

# ============================================================ upload/validate --
with tabs[0]:
    section("Upload MCIS extracts")
    st.caption(
        "Several files can be uploaded at once. Each is validated on its own — "
        "an invalid file is rejected without blocking the valid ones. Files are "
        "processed oldest-first by their earliest issuance date."
    )

    files = st.file_uploader(
        "MCIS export extracts (.xls / .xlsx)",
        type=["xls", "xlsx"], accept_multiple_files=True, key="t3i_uploader",
    )

    if files and st.button("▶️ VALIDATE AND STAGE", type="primary"):
        batch_id = pd.Timestamp.now().strftime("B%Y%m%d%H%M%S")
        report, accepted = [], []

        for f in files:
            try:
                raw = ingest.read_workbook(f.getvalue(), f.name)
                records, subs = ingest.normalise(raw, f.name, batch_id)
                lo, hi = ingest.file_date_range(records)
                report.append({
                    "File": f.name, "Status": "✅ accepted", "Rows": len(records),
                    "From": fmt_date(lo), "To": fmt_date(hi), "Reason": "",
                })
                accepted.append({"records": records, "subs": subs,
                                 "name": f.name, "sort": lo})
            except FileRejected as exc:
                report.append({"File": f.name, "Status": "❌ rejected", "Rows": 0,
                               "From": "—", "To": "—", "Reason": str(exc)})
            except Exception as exc:  # noqa: BLE001
                report.append({"File": f.name, "Status": "❌ rejected", "Rows": 0,
                               "From": "—", "To": "—",
                               "Reason": f"Unreadable ({type(exc).__name__})"})

        st.session_state["t3i_file_report"] = pd.DataFrame(report)

        if accepted:
            accepted.sort(key=lambda a: (a["sort"] is None, a["sort"]))
            incoming = pd.concat([a["records"] for a in accepted], ignore_index=True)
            incoming = incoming.drop_duplicates("record_key", keep="first")
            subs = pd.concat([a["subs"] for a in accepted], ignore_index=True) \
                if any(len(a["subs"]) for a in accepted) else pd.DataFrame()

            new, exact, conflicts = history.classify(
                st.session_state["t3i_dataset"], incoming)
            st.session_state["t3i_pending"] = {
                "batch_id": batch_id, "new": new, "exact": exact,
                "conflicts": conflicts, "subs": subs,
                "files": [{"name": r["File"],
                           "status": "accepted" if "accepted" in r["Status"] else "rejected",
                           "reason": r["Reason"]} for r in report],
                "rows_read": int(len(incoming)),
            }
        else:
            st.session_state["t3i_pending"] = None
        st.rerun()

    rep = st.session_state.get("t3i_file_report")
    if rep is not None and not rep.empty:
        section("Validation result")
        st.dataframe(rep, width="stretch", hide_index=True)
        rejected = rep[rep["Status"].str.contains("rejected")]
        if len(rejected):
            red_alert(f"{len(rejected)} file(s) rejected — see the Reason column. "
                      "Rejected files are never partially imported.")

    pending = st.session_state.get("t3i_pending")
    if pending:
        section("Staged for import")
        c1, c2, c3 = st.columns(3)
        c1.metric("New records", fmt(len(pending["new"])))
        c2.metric("Exact duplicates (ignored)", fmt(len(pending["exact"])))
        c3.metric("Conflicting duplicates", fmt(len(pending["conflicts"])))

        if pending["conflicts"]:
            warn_banner(
                f"{len(pending['conflicts'])} conflicting duplicate(s) must be "
                "resolved on the <b>Resolve Conflicts</b> tab before this batch "
                "can be committed. Nothing is imported until then."
            )
        else:
            if st.button("✅ COMMIT BATCH TO SESSION", type="primary"):
                ss = st.session_state
                ss["t3i_dataset"] = history.append(ss["t3i_dataset"], pending["new"])
                if len(pending["subs"]):
                    ss["t3i_subtotals"] = pd.concat(
                        [ss["t3i_subtotals"], pending["subs"]], ignore_index=True)
                ss["t3i_batches"].append(history.batch_record(
                    pending["batch_id"], pending["files"],
                    {"read": pending["rows_read"], "new": len(pending["new"]),
                     "exact": len(pending["exact"]), "conflicts": 0}))
                ss["t3i_pending"] = None
                ss["t3i_dirty"] = True
                state.recompute()
                st.rerun()

# ========================================================== resolve conflicts --
with tabs[1]:
    section("Conflicting duplicates")
    pending = st.session_state.get("t3i_pending")
    conflicts = pending["conflicts"] if pending else []

    if not conflicts:
        info_banner("No conflicting duplicates to resolve.")
    else:
        st.caption(
            "The same Shipment Number + Certificate Number already exists with "
            "different values. Nothing is ever auto-overwritten — choose per "
            "record. Fields that differ are listed for each one."
        )

        decisions = st.session_state.setdefault("t3i_decisions", {})

        b1, b2, b3 = st.columns(3)
        if b1.button("Keep existing — all", width="stretch"):
            for c in conflicts:
                decisions[c["record_key"]] = "keep_existing"
        if b2.button("Replace with incoming — all", width="stretch"):
            for c in conflicts:
                decisions[c["record_key"]] = "replace"
        if b3.button("Keep both — all", width="stretch"):
            for c in conflicts:
                decisions[c["record_key"]] = "keep_both"

        for c in conflicts:
            key = c["record_key"]
            with st.expander(
                f"{c['shipment_no']} · cert {c['certificate_no']} — "
                f"{c['exporter']} ({len(c['diffs'])} field(s) differ)"
            ):
                st.dataframe(
                    pd.DataFrame(c["diffs"]).rename(columns={
                        "field": "Field", "existing": "Existing", "incoming": "Incoming"}),
                    width="stretch", hide_index=True,
                )
                decisions[key] = st.radio(
                    "Decision", ["keep_existing", "replace", "keep_both"],
                    format_func={
                        "keep_existing": "Keep existing — discard incoming",
                        "replace": "Replace with incoming — treat as a correction",
                        "keep_both": "Keep both, flagged for follow-up",
                    }.get,
                    key=f"t3i_dec_{key}",
                    index=["keep_existing", "replace", "keep_both"].index(
                        decisions.get(key, "keep_existing")),
                    horizontal=True,
                )

        if st.button("✅ APPLY DECISIONS AND COMMIT BATCH", type="primary"):
            ss = st.session_state
            base = history.resolve(ss["t3i_dataset"], conflicts, decisions)
            ss["t3i_dataset"] = history.append(base, pending["new"])
            if len(pending["subs"]):
                ss["t3i_subtotals"] = pd.concat(
                    [ss["t3i_subtotals"], pending["subs"]], ignore_index=True)
            ss["t3i_batches"].append(history.batch_record(
                pending["batch_id"], pending["files"],
                {"read": pending["rows_read"], "new": len(pending["new"]),
                 "exact": len(pending["exact"]), "conflicts": len(conflicts),
                 "replaced": sum(1 for v in decisions.values() if v == "replace"),
                 "kept_both": sum(1 for v in decisions.values() if v == "keep_both")}))
            ss["t3i_pending"] = None
            ss["t3i_decisions"] = {}
            ss["t3i_dirty"] = True
            state.recompute()
            st.rerun()

# ================================================================== dataset --
with tabs[2]:
    section("Current dataset")
    d = state.view()
    if d.empty:
        info_banner("No data loaded yet.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Records", fmt(len(d)))
        c2.metric("Excluded", fmt(int((d["excluded"] == "YES").sum())))
        c3.metric("Subtotal rows held aside",
                  fmt(len(st.session_state.get("t3i_subtotals", []))))

        show_cols = ["mineral", "product", "shipment_no", "certificate_no",
                     "issuance_date", "year_month", "exporter", "buyer",
                     "destination", "grade_pct", "quantity_kg",
                     "pure_quantity_kg", "shipment_value_usd",
                     "unit_value_usd_kg", "excluded"]
        show_cols = [c for c in show_cols if c in d.columns]
        st.dataframe(d[show_cols].head(1000), width="stretch", hide_index=True)
        st.caption("Showing the first 1,000 rows. Download for the full dataset.")
        download_button("Full Dataset", {"Dataset": d}, "RMB-3T_Dataset",
                        source="Data Management", key="dl_dataset")

# ======================================================== ingestion history --
with tabs[3]:
    section("Ingestion history")
    batches = st.session_state.get("t3i_batches", [])
    if not batches:
        info_banner("No uploads recorded in this session.")
    else:
        bdf = pd.DataFrame(batches)
        st.dataframe(bdf, width="stretch", hide_index=True)
        download_button("Ingestion History", {"Batches": bdf},
                        "RMB-3T_IngestionHistory", key="dl_batches")

# ============================================================ save & commit --
with tabs[4]:
    section("Save & commit")
    d = st.session_state["t3i_dataset"]

    if st.session_state.get("t3i_dirty"):
        warn_banner(
            "<b>UNSAVED CHANGES</b> — nothing is stored on the server. Download "
            "the files below and commit them to the repository, or this work is "
            "lost when the session ends or the app redeploys."
        )
    else:
        info_banner("No changes to save — the session matches the committed baseline.")

    st.markdown(
        "The app runs from files committed to the repository. To make this "
        "session's work permanent:\n\n"
        "1. Download the dataset (both formats) and any rules files you changed.\n"
        "2. Replace the matching files in the repository's `data/` folder.\n"
        "3. Commit and push. The app reloads from them on next start."
    )

    if not d.empty:
        c1, c2 = st.columns(2)
        with c1:
            xlsx = build_workbook({"Dataset": d}, source="Save & Commit")
            st.download_button("📥 DOWNLOAD — dataset.xlsx", xlsx,
                               file_name="dataset.xlsx",
                               mime="application/vnd.openxmlformats-officedocument"
                                    ".spreadsheetml.sheet",
                               width="stretch", key="dl_ds_x")
        with c2:
            out = d.copy()
            if "issuance_date" in out.columns:
                out["issuance_date"] = pd.to_datetime(
                    out["issuance_date"], errors="coerce"
                ).dt.strftime("%Y-%m-%dT%H:%M:%S")
            st.download_button(
                "📥 DOWNLOAD — dataset.json",
                out.to_json(orient="records", indent=2, date_format="iso"),
                file_name="dataset.json", mime="application/json",
                width="stretch", key="dl_ds_j")

    section("Rules files")
    r1, r2, r3 = st.columns(3)
    r1.download_button(
        "📥 rules_harmonisation.json",
        json.dumps(st.session_state["t3i_rules_harm"], indent=2, ensure_ascii=False),
        file_name="rules_harmonisation.json", mime="application/json",
        width="stretch", key="dl_rh")
    r2.download_button(
        "📥 rules_exclusions.json",
        json.dumps(st.session_state["t3i_rules_excl"], indent=2, ensure_ascii=False),
        file_name="rules_exclusions.json", mime="application/json",
        width="stretch", key="dl_re")
    r3.download_button(
        "📥 intl_prices.json",
        json.dumps(st.session_state["t3i_prices"], indent=2, ensure_ascii=False),
        file_name="intl_prices.json", mime="application/json",
        width="stretch", key="dl_ip")

    if st.session_state.get("t3i_dirty") and st.button(
            "Mark as saved (after committing)", key="t3i_mark_saved"):
        st.session_state["t3i_dirty"] = False
        st.session_state["t3i_baseline_rows"] = len(d)
        st.rerun()

    # ------------------------------------------------ commit straight to git --
    section("Commit directly to GitHub (optional)")

    target = _github_target()
    if target is None or not target.is_configured():
        st.caption(
            "Not configured — the manual download-and-commit cycle above is the "
            "only route. To enable one-click commits, add a `[github]` block to "
            "`.streamlit/secrets.toml` locally, or to the app's secrets on "
            "Streamlit Cloud. See DEPLOYMENT.md Part 3."
        )
        with st.expander("What the secrets block looks like"):
            st.code(
                '[github]\n'
                'owner = "YOUR-GITHUB-USERNAME"\n'
                'repo = "rmb-3t-intel"\n'
                'branch = "main"\n'
                'token = "github_pat_..."   # fine-grained, Contents: read and write\n',
                language="toml")
            st.caption(
                "The token is a write credential. Never commit it — "
                "`.streamlit/secrets.toml` is git-ignored in this project."
            )
    else:
        st.caption(f"Target: `{target.slug}` on branch `{target.branch}`.")

        cc1, cc2 = st.columns([1, 2])
        if cc1.button("Test connection", width="stretch", key="t3i_gh_test"):
            try:
                info = github_sync.check_access(target)
                perms = info.get("permissions", {})
                if perms.get("push"):
                    st.success(
                        f"Connected to {info['full_name']} "
                        f"({'private' if info['private'] else 'public'}). "
                        "Write access confirmed.")
                else:
                    red_alert(
                        f"Connected to {info['full_name']}, but this token has "
                        "no write access. Commits will fail.")
            except github_sync.GitHubError as exc:
                red_alert(str(exc))

        which = st.multiselect(
            "Files to commit",
            ["data/dataset.json", "data/dataset.xlsx",
             "data/rules_harmonisation.json", "data/rules_exclusions.json",
             "data/intl_prices.json"],
            default=["data/dataset.json", "data/rules_harmonisation.json",
                     "data/rules_exclusions.json", "data/intl_prices.json"],
            key="t3i_gh_files")
        msg = st.text_input(
            "Commit message",
            f"Update dataset and rules from the app "
            f"({pd.Timestamp.now().strftime('%d-%b-%Y %H:%M')})",
            key="t3i_gh_msg")

        st.caption(
            "One commit per file — the GitHub Contents API cannot batch them. "
            "If a commit fails partway, the earlier files are already pushed; "
            "the result table below shows exactly which."
        )

        if st.button("🚀 COMMIT TO GITHUB", type="primary", key="t3i_gh_push"):
            payload: dict[str, bytes] = {}
            out = d.copy()
            if "issuance_date" in out.columns:
                out["issuance_date"] = pd.to_datetime(
                    out["issuance_date"], errors="coerce"
                ).dt.strftime("%Y-%m-%dT%H:%M:%S")

            for path in which:
                if path.endswith("dataset.json"):
                    payload[path] = out.to_json(
                        orient="records", indent=2).encode("utf-8")
                elif path.endswith("dataset.xlsx"):
                    payload[path] = build_workbook({"Dataset": d},
                                                   source="GitHub sync")
                elif path.endswith("rules_harmonisation.json"):
                    payload[path] = json.dumps(
                        st.session_state["t3i_rules_harm"], indent=2,
                        ensure_ascii=False).encode("utf-8")
                elif path.endswith("rules_exclusions.json"):
                    payload[path] = json.dumps(
                        st.session_state["t3i_rules_excl"], indent=2,
                        ensure_ascii=False).encode("utf-8")
                elif path.endswith("intl_prices.json"):
                    payload[path] = json.dumps(
                        st.session_state["t3i_prices"], indent=2,
                        ensure_ascii=False).encode("utf-8")

            done: list[dict] = []
            try:
                with st.spinner("Committing…"):
                    done = github_sync.put_many(target, payload, msg)
                st.success(f"Committed {len(done)} file(s).")
                st.session_state["t3i_dirty"] = False
                st.session_state["t3i_baseline_rows"] = len(d)
            except github_sync.GitHubError as exc:
                red_alert(
                    f"Commit failed after {len(done)} of {len(payload)} file(s): "
                    f"{exc}")
            if done:
                st.dataframe(pd.DataFrame(done), width="stretch", hide_index=True)
