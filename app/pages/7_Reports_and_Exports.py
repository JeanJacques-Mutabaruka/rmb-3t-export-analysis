"""7 · Reports & Exports — summary, excluded rows, export centre."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import state  # noqa: E402
from app.downloads import download_button, stamp  # noqa: E402
from app.formatting import fmt, fmt_money_m  # noqa: E402
from app.glossary import PURE_QUANTITY, VALUE_FORGONE  # noqa: E402
from app.style import info_banner, section, warn_banner  # noqa: E402
from engine import benchmarks_peer as bp, coverage, exclusions, losses, reporting  # noqa: E402

state.init_state()
filters = state.page_setup("📄 Reports & Exports")

if not state.require_data():
    st.stop()

full = state.view()
d = state.apply_filters(state.active(), filters)
fdesc = f"years={filters.get('years')}, minerals={filters.get('minerals')}"

tabs = st.tabs(["📄 Summary Report", "🚫 Excluded Rows", "📥 Export Centre"])

# ========================================================== summary report ====
with tabs[0]:
    if d.empty:
        info_banner("No rows match the current filters.")
    else:
        section("Headline figures")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Shipments", fmt(len(d)))
        c2.metric("Export value", fmt_money_m(d["shipment_value_usd"].sum()))
        c3.metric("Exporters", fmt(d["exporter"].nunique()))
        c4.metric("Buyers", fmt(d["buyer"].nunique()))

        years = d["year"].dropna()
        period = f"{int(years.min())}–{int(years.max())}" if len(years) else "—"

        _warn = coverage.coverage_warning(d, filters.get("years"))
        if _warn:
            warn_banner(_warn)

        section("Value by year and mineral")
        piv = d.pivot_table(index="year", columns="mineral",
                            values="shipment_value_usd", aggfunc="sum").fillna(0)
        piv["Total"] = piv.sum(axis=1)
        st.dataframe(piv.style.format("${:,.0f}"), width="stretch")

        section("International price gap")
        gap = losses.attach(losses.rwanda_monthly(d), st.session_state["t3i_prices"])
        ann = losses.annual(gap)
        if ann.empty:
            info_banner("No benchmark data for this selection.")
        else:
            st.metric("Estimated cumulative gap", fmt_money_m(ann["Total"].sum()))
            st.dataframe(ann.style.format("${:,.0f}"), width="stretch")
            assumed = int((gap["basis"] == "ASSUMPTION").sum())
            if assumed:
                warn_banner(
                    f"{assumed} month(s) in this figure rest on an ASSUMPTION "
                    "benchmark with no published source. See 4 · International "
                    "Benchmark before quoting."
                )

        section("Peer benchmark")
        grain = st.session_state.get("t3i_grain", "month")
        window = int(st.session_state.get("t3i_window", 3))
        ep = bp.exporter_periods(d, grain)
        peer_year = pd.DataFrame()
        if not ep.empty:
            stats, _ = bp.peer_stats(ep, grain, window)
            disc = bp.discounts(ep, stats)
            st.metric("Total value forgone vs market average",
                      fmt_money_m(disc["forgone_vs_avg"].sum()),
                      help=VALUE_FORGONE)
            peer_year = disc.pivot_table(index="year", columns="mineral",
                                         values="forgone_vs_avg",
                                         aggfunc="sum").fillna(0)
            peer_year["Total"] = peer_year.sum(axis=1)
            st.dataframe(peer_year.style.format("${:,.0f}"), width="stretch")

        section("Data quality")
        excluded_n = int((full["excluded"] == "YES").sum())
        st.caption(
            f"{fmt(excluded_n)} record(s) excluded by the active rules across the "
            f"whole dataset. Period covered: {period}."
        )

        download_button("Summary Report",
                        {"Value by year": piv.reset_index(),
                         "Intl losses": ann.reset_index() if not ann.empty else pd.DataFrame(),
                         "Peer forgone": peer_year.reset_index() if not peer_year.empty else pd.DataFrame()},
                        "RMB-3T_SummaryReport", source="Reports",
                        filters=fdesc, key="dl_sum")

# =========================================================== excluded rows ====
with tabs[1]:
    section("Excluded rows")
    st.caption(
        "Every row currently flagged by an exclusion rule. Filter, review, and "
        "amend the category flags or notes directly in the grid."
    )

    ex = full[full["excluded"] == "YES"].copy() if "excluded" in full.columns \
        else pd.DataFrame()
    if ex.empty:
        info_banner("No rows are currently excluded.")
    else:
        cats = st.session_state["t3i_rules_excl"].get("categories", [])
        cat_cols = [exclusions.slug(c) for c in cats if exclusions.slug(c) in ex.columns]

        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            f_min = c1.multiselect("Mineral", sorted(ex["mineral"].dropna().unique()),
                                   key="t3i_ex_min")
            f_prod = c2.multiselect("Product", sorted(ex["product"].dropna().unique()),
                                    key="t3i_ex_prod")
            f_exp = c3.multiselect("Exporter", sorted(ex["exporter"].dropna().unique()),
                                   key="t3i_ex_exp")
            c4, c5, c6 = st.columns(3)
            f_buy = c4.multiselect("Buyer", sorted(ex["buyer"].dropna().unique()),
                                   key="t3i_ex_buy")
            f_dest = c5.multiselect("Destination",
                                    sorted(ex["destination"].dropna().unique()),
                                    key="t3i_ex_dest")
            f_yr = c6.multiselect("Year",
                                  sorted(int(y) for y in ex["year"].dropna().unique()),
                                  key="t3i_ex_yr")
            c7, c8 = st.columns(2)
            f_cat = c7.multiselect("Exclusion category", cats, key="t3i_ex_cat")
            search = c8.text_input("Search (shipment, certificate, note)",
                                   key="t3i_ex_search")

            c9, c10 = st.columns(2)
            vmin = float(ex["shipment_value_usd"].min() or 0)
            vmax = float(ex["shipment_value_usd"].max() or 0)
            if vmax > vmin:
                v_range = c9.slider("Shipment value ($)", vmin, vmax, (vmin, vmax),
                                    key="t3i_ex_vr")
            else:
                v_range = (vmin, vmax)
            qmin = float(ex["quantity_kg"].min() or 0)
            qmax = float(ex["quantity_kg"].max() or 0)
            if qmax > qmin:
                q_range = c10.slider("Quantity (kg)", qmin, qmax, (qmin, qmax),
                                     key="t3i_ex_qr")
            else:
                q_range = (qmin, qmax)

        f = ex
        if f_min:
            f = f[f["mineral"].isin(f_min)]
        if f_prod:
            f = f[f["product"].isin(f_prod)]
        if f_exp:
            f = f[f["exporter"].isin(f_exp)]
        if f_buy:
            f = f[f["buyer"].isin(f_buy)]
        if f_dest:
            f = f[f["destination"].isin(f_dest)]
        if f_yr:
            f = f[f["year"].isin(f_yr)]
        if f_cat:
            hit = pd.Series(False, index=f.index)
            for c in f_cat:
                col = exclusions.slug(c)
                if col in f.columns:
                    hit |= (f[col] == "YES")
            f = f[hit]
        if search.strip():
            s = search.strip().lower()
            hay = (f["shipment_no"].astype(str) + " " +
                   f["certificate_no"].astype(str) + " " +
                   f["exclusion_note"].astype(str)).str.lower()
            f = f[hay.str.contains(s, na=False)]
        f = f[(f["shipment_value_usd"].between(*v_range)) &
              (f["quantity_kg"].between(*q_range))]

        st.caption(f"{fmt(len(f))} of {fmt(len(ex))} excluded row(s) shown.")

        edit_cols = ["record_key", "shipment_no", "certificate_no", "mineral",
                     "product", "exporter", "buyer", "year_month",
                     "quantity_kg", "shipment_value_usd", "unit_value_usd_kg",
                     *cat_cols, "exclusion_note"]
        edit_cols = [c for c in edit_cols if c in f.columns]

        st.caption(
            "Category columns are editable — set to YES or clear. Note: "
            "st.data_editor cannot colour rows, so status is carried in the "
            "category columns themselves."
        )
        edited = st.data_editor(
            f[edit_cols], width="stretch", height=420, hide_index=True,
            disabled=[c for c in edit_cols if c not in cat_cols + ["exclusion_note"]],
            key="t3i_ex_editor",
        )

        if st.button("💾 APPLY EDITS TO DATASET", type="primary"):
            ds = st.session_state["t3i_dataset"].set_index("record_key")
            for _, row in edited.iterrows():
                key = row["record_key"]
                if key not in ds.index:
                    continue
                if "exclusion_note" in edited.columns:
                    ds.at[key, "exclusion_note"] = row["exclusion_note"]
            st.session_state["t3i_dataset"] = ds.reset_index()
            state.mark_dirty()
            state.recompute()
            warn_banner(
                "Notes updated. Category flags are produced by the exclusion "
                "rules — to change which rows a category covers, edit the rule "
                "on <b>2 · Rules &amp; Data Quality → Exclusions</b>."
            )
            st.rerun()

        download_button("Excluded Rows", {"Excluded": f},
                        "RMB-3T_ExcludedRows", source="Reports",
                        filters=fdesc, key="dl_ex")

# ============================================================ export centre ====
with tabs[2]:
    section("Export centre")
    st.caption("Build one workbook containing every table in the tool.")

    if st.button("📦 BUILD FULL EXPORT", type="primary"):
        with st.spinner("Building…"):
            sheets: dict[str, pd.DataFrame] = {"Dataset": full}
            if not d.empty:
                sheets["By year"] = d.groupby(["year", "mineral"]).agg(
                    value=("shipment_value_usd", "sum"),
                    quantity=("quantity_kg", "sum"),
                    shipments=("shipment_value_usd", "size")).reset_index()
                sheets["Exporters"] = d.groupby(["year", "mineral", "exporter"])[
                    "shipment_value_usd"].sum().reset_index()
                sheets["Buyers"] = d.groupby(["year", "buyer"])[
                    "shipment_value_usd"].sum().reset_index()
                sheets["Destinations"] = d.groupby(["year", "destination"])[
                    "shipment_value_usd"].sum().reset_index()

                gap = losses.attach(losses.rwanda_monthly(d),
                                    st.session_state["t3i_prices"])
                if not gap.empty:
                    g = gap.copy()
                    g["period"] = g["period"].astype(str)
                    sheets["Intl gap monthly"] = g
                    sheets["Intl losses annual"] = losses.annual(gap).reset_index()

                ep = bp.exporter_periods(d, st.session_state.get("t3i_grain", "month"))
                if not ep.empty:
                    stats, outliers = bp.peer_stats(
                        ep, st.session_state.get("t3i_grain", "month"),
                        int(st.session_state.get("t3i_window", 3)))
                    disc = bp.discounts(ep, stats)
                    if not outliers.empty:
                        sheets["Peer outliers excluded"] = outliers
                    dd = disc.copy()
                    dd["period"] = dd["period"].astype(str)
                    sheets["Peer monthly"] = dd
                    sheets["Peer scorecard"] = bp.scorecard(disc)

            ex = full[full["excluded"] == "YES"]
            if not ex.empty:
                sheets["Excluded rows"] = ex
            subs = st.session_state.get("t3i_subtotals")
            if subs is not None and not subs.empty:
                sheets["Source subtotals"] = subs
            batches = st.session_state.get("t3i_batches", [])
            if batches:
                sheets["Ingestion history"] = pd.DataFrame(batches)

            st.session_state["t3i_full_export"] = sheets
        st.success(f"Built {len(st.session_state['t3i_full_export'])} sheet(s).")

    if st.session_state.get("t3i_full_export"):
        download_button("Full Analysis Workbook",
                        st.session_state["t3i_full_export"],
                        "RMB-3T_FullAnalysis", source="Export Centre",
                        filters=fdesc, key="dl_full", width="stretch")

    section("Word / PDF report")
    st.caption(
        "A narrative report carrying the headline figures, the main tables and "
        "the standing caveats — for circulation rather than further analysis. "
        "Tables are truncated; use the Excel workbook for complete data."
    )

    if d.empty:
        info_banner("No rows match the current filters.")
    else:
        years = d["year"].dropna()
        period = f"{int(years.min())}-{int(years.max())}" if len(years) else "-"

        gap_r = losses.attach(losses.rwanda_monthly(d), st.session_state["t3i_prices"])
        ann_r = losses.annual(gap_r)
        ep_r = bp.exporter_periods(d, st.session_state.get("t3i_grain", "month"))
        peer_tbl = pd.DataFrame()
        forgone_total = 0.0
        if not ep_r.empty:
            stats_r, _ = bp.peer_stats(ep_r, st.session_state.get("t3i_grain", "month"),
                                       int(st.session_state.get("t3i_window", 3)))
            disc_r = bp.discounts(ep_r, stats_r)
            forgone_total = float(disc_r["forgone_vs_avg"].sum())
            sc_r = bp.scorecard(disc_r)
            if not sc_r.empty:
                peer_tbl = (
                    sc_r.nlargest(15, "forgone_vs_avg")[
                        ["mineral", "year", "exporter", "exporter_price",
                         "peer_avg", "disc_vs_avg_pct", "forgone_vs_avg"]]
                    .rename(columns={
                        "mineral": "Mineral", "year": "Year", "exporter": "Exporter",
                        "exporter_price": "Their price", "peer_avg": "Peer avg",
                        "disc_vs_avg_pct": "Discount", "forgone_vs_avg": "Forgone"})
                )

        ctx = {
            "subtitle": "Export analysis report",
            "period": period,
            "filters": fdesc,
            "metrics": {
                "Shipments": fmt(len(d)),
                "Export value": fmt_money_m(d["shipment_value_usd"].sum()),
                "Exporters": fmt(d["exporter"].nunique()),
                "Buyers": fmt(d["buyer"].nunique()),
                "Estimated international price gap":
                    fmt_money_m(ann_r["Total"].sum()) if not ann_r.empty else "-",
                "Value forgone vs peer average": fmt_money_m(forgone_total),
                "Records excluded by active rules":
                    fmt(int((full["excluded"] == "YES").sum())),
            },
            "caveats": reporting.standard_caveats(),
        }
        rep_tables = {
            "Value by year and mineral": d.pivot_table(
                index="year", columns="mineral", values="shipment_value_usd",
                aggfunc="sum").fillna(0).reset_index(),
            "Estimated international losses":
                ann_r.reset_index() if not ann_r.empty else pd.DataFrame(),
            "Largest peer-benchmark gaps": peer_tbl,
        }

        c1, c2 = st.columns(2)
        with c1:
            if reporting.DOCX_AVAILABLE:
                try:
                    st.download_button(
                        "📥 DOWNLOAD — Report (.docx)",
                        reporting.build_docx(ctx, rep_tables),
                        file_name=f"RMB-3T_Report{stamp()}.docx",
                        mime="application/vnd.openxmlformats-officedocument"
                             ".wordprocessingml.document",
                        width="stretch", key="dl_docx")
                except Exception as exc:  # noqa: BLE001
                    st.caption(f"Word export unavailable: {exc}")
            else:
                st.caption("Word export needs `python-docx` in requirements.txt.")
        with c2:
            if reporting.PDF_AVAILABLE:
                try:
                    st.download_button(
                        "📥 DOWNLOAD — Report (.pdf)",
                        reporting.build_pdf(ctx, rep_tables),
                        file_name=f"RMB-3T_Report{stamp()}.pdf",
                        mime="application/pdf",
                        width="stretch", key="dl_pdf")
                except Exception as exc:  # noqa: BLE001
                    st.caption(f"PDF export unavailable: {exc}")
            else:
                st.caption("PDF export needs `reportlab` in requirements.txt.")
