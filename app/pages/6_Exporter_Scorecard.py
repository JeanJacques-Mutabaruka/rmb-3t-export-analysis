"""6 · Exporter Scorecard — rankings, worst traders, detail, comparison."""
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
from app.formatting import fmt, fmt_money, fmt_money_m, fmt_pct  # noqa: E402
from app.glossary import (  # noqa: E402
    BEST_TRADER_METHOD, CONSISTENCY, COMPETITIVE_RISK_DETAIL, MONTHS_COLUMN_ABOVE,
    MONTHS_COLUMN_BELOW,
    COMPETITIVE_RISK_NOTE, DISCOUNT_RANGE, PCT_QTY_BELOW, PEER_AVERAGE,
    PEER_AVG_EXCL_SELF, PEER_MAX, PRICE_RANGE, PURE_QUANTITY, THIN_MARKET,
    VALUE_FORGONE, WORST_TRADER_CAUTION, WORST_TRADER_METHOD,
)
from app.style import info_banner, insight_banner, section, warn_banner  # noqa: E402
from engine import benchmarks_peer as bp  # noqa: E402
from engine import coverage, ranking  # noqa: E402
from engine.schema import MINERAL_LABEL  # noqa: E402

state.init_state()
filters = state.page_setup("🏆 Exporter Scorecard")

if not state.require_data():
    st.stop()

d = state.apply_filters(state.active(), filters)
if d.empty:
    info_banner("No rows match the current filters.")
    st.stop()

grain = st.session_state.get("t3i_grain", "month")
window = int(st.session_state.get("t3i_window", 3 if grain == "month" else 2))
label = st.session_state.get("t3i_basis_label", "Current month")

ep = bp.exporter_periods(d, grain)
if ep.empty:
    info_banner("Not enough priced data to build the scorecard.")
    st.stop()
stats, outliers = bp.peer_stats(ep, grain, window)
disc = bp.discounts(ep, stats)
sc = bp.scorecard(disc)

st.caption(f"Peer basis: **{label}** — change it on 5 · Peer Benchmark → Basis Settings.")
fdesc = f"{label}; years={filters.get('years')}; minerals={filters.get('minerals')}"

tabs = st.tabs(["🏆 Ranking", "🔻 Worst Traders", "🏅 Best Traders",
                "👤 Exporter Detail", "🔀 Compare Exporters"])

# ================================================================= ranking ====
with tabs[0]:
    section("Exporter ranking by export value")

    # The unfiltered active set — the previous year's rank must survive the
    # user's year filter, otherwise the comparison column blanks out exactly
    # when it is most useful.
    d_all = state.active()

    all_years = sorted(int(y) for y in d["year"].dropna().unique())
    rk_years = st.multiselect(
        "Years", all_years, default=all_years, key="t3i_rk_years",
        help="Rankings are shown for the LATEST year selected. The previous "
             "year is always taken from the full dataset, even if it is not "
             "selected here.")
    if not rk_years:
        info_banner("Select at least one year.")
    else:
        current_year = max(int(y) for y in rk_years)
        prev_year = current_year - 1

        warn = coverage.coverage_warning(d_all, [current_year, prev_year])
        if warn:
            warn_banner(warn)

        st.caption(
            f"Ranking for **{current_year}**, compared against **{prev_year}**."
        )

        prods = (
            d[d["year"].isin(rk_years)]
            .groupby("product")["shipment_value_usd"].sum()
            .sort_values(ascending=False).index.tolist()
        )
        sub_labels = ["All products (value only)"] + prods
        sub = st.tabs(sub_labels)

        for stab, plabel in zip(sub, sub_labels):
            with stab:
                product = None if plabel.startswith("All products") else plabel
                rk = ranking.ranking_with_movement(d_all, current_year, product)
                if rk.empty:
                    info_banner(f"No data for {current_year}.")
                    continue

                if product is None:
                    st.caption(
                        "Quantity columns are omitted here on purpose: adding "
                        "kilograms of tin to kilograms of tantalum produces a "
                        "figure with no meaning. Use a product sub-tab for "
                        "quantities."
                    )

                show = pd.DataFrame({
                    "Rank": rk["rank"],
                    f"Rank {prev_year}": rk["rank_prev"],
                    "Move": [ranking.movement_label(r) for _, r in rk.iterrows()],
                    "Exporter": rk["exporter"],
                    f"Value {current_year}": rk["value"],
                    f"Value {prev_year}": rk["value_prev"],
                    "Value change": rk["value_change_pct"],
                    f"Share % {current_year}": rk["share_pct"],
                    f"Share % {prev_year}": rk["share_pct_prev"],
                    "Shipments": rk["shipments"],
                })
                if product is not None:
                    show["Quantity (kg)"] = rk["quantity"]
                    show["Pure qty (kg)"] = rk["pure_qty"]
                show["Cumulative %"] = rk["share_pct"].cumsum()

                c1, c2, c3 = st.columns(3)
                c1.metric("Exporters", fmt(len(rk)))
                c2.metric("Top-10 share", f"{rk.head(10)['share_pct'].sum():.1f}%")
                c3.metric("New entrants", fmt(int(rk["is_new_entrant"].sum())),
                          help=f"Exporters ranked in {current_year} with no "
                               f"{prev_year} activity.")

                def _move_colour(v):
                    if not isinstance(v, str):
                        return ""
                    if v.startswith("▲"):
                        return "color: #1A5C38; font-weight: 700"
                    if v.startswith("▼"):
                        return "color: #C00000; font-weight: 700"
                    if v == "new":
                        return "color: #2C3E9E; font-weight: 600"
                    return ""

                fmts = {
                    f"Value {current_year}": "${:,.0f}",
                    f"Value {prev_year}": "${:,.0f}",
                    "Value change": "{:+.1f}%",
                    f"Share % {current_year}": "{:.1f}%",
                    f"Share % {prev_year}": "{:.1f}%",
                    "Cumulative %": "{:.1f}%",
                    "Shipments": "{:,.0f}",
                    f"Rank {prev_year}": "{:.0f}",
                }
                if product is not None:
                    fmts["Quantity (kg)"] = "{:,.0f}"
                    fmts["Pure qty (kg)"] = "{:,.0f}"

                st.dataframe(
                    show.style.format(fmts, na_rep="—")
                        .map(_move_colour, subset=["Move"]),
                    width="stretch", height=420, hide_index=True,
                    column_config={
                        "Move": st.column_config.TextColumn(
                            "Move", help="Change in rank versus the previous "
                            "year. ▲ moved up, ▼ moved down, 'new' means no "
                            "activity in the previous year."),
                        "Value change": st.column_config.NumberColumn(
                            "Value change", help="Percentage change in export "
                            "value versus the previous year."),
                        "Pure qty (kg)": st.column_config.NumberColumn(
                            "Pure qty (kg)", help=PURE_QUANTITY),
                    })
                download_button(
                    f"Ranking {plabel} {current_year}", {"Ranking": show},
                    f"RMB-3T_Ranking_{current_year}",
                    source="Exporter Scorecard", filters=fdesc,
                    key=f"dl_rank_{plabel[:12]}")

# =========================================================== worst traders ====
with tabs[1]:
    section("Worst traders by commodity and year")

    with st.expander("📖 What this means, and exactly how it is calculated", expanded=False):
        st.markdown(WORST_TRADER_METHOD)
        warn_banner(WORST_TRADER_CAUTION)

    insight_banner(COMPETITIVE_RISK_NOTE)
    with st.expander("Why this matters in practice"):
        st.markdown(COMPETITIVE_RISK_DETAIL)

    if sc.empty:
        info_banner("No scorecard available.")
    else:
        c1, c2, c3 = st.columns(3)
        mode = c1.selectbox(
            "Rank by", ["Value forgone ($)", "Discount (%)"], key="t3i_wt_mode",
            help="Value forgone prioritises where the money is. Discount finds "
                 "the deepest under-pricing regardless of size.")
        topn = c2.number_input("Show top N", 3, 20, 5, key="t3i_wt_n")
        min_qty = c3.number_input(
            "Min pure quantity (kg)", 0.0, 1e6,
            5000.0 if mode == "Discount (%)" else 0.0, 1000.0, key="t3i_wt_q",
            help="Stops a single tiny shipment topping the table. "
                 + PURE_QUANTITY)

        rank_by = "forgone_vs_avg" if mode == "Value forgone ($)" else "disc_vs_avg_pct"
        years = sorted(int(y) for y in sc["year"].dropna().unique())
        minerals = [m for m in ["Cassiterite", "Coltan", "Wolframite"]
                    if m in sc["mineral"].unique()]

        if not minerals or not years:
            info_banner("No data for the current filters.")
        else:
            mtabs = st.tabs([MINERAL_LABEL.get(m, m) for m in minerals])
            for tab, mineral in zip(mtabs, minerals):
                with tab:
                    yr = st.selectbox("Year", years, index=len(years) - 1,
                                      key=f"t3i_wt_y_{mineral}")
                    worst = bp.worst_traders(sc, mineral, yr, int(topn),
                                             rank_by, min_qty)
                    if worst.empty:
                        info_banner("No exporters match for this year.")
                        continue

                    show = pd.DataFrame({
                        "Exporter": worst["exporter"],
                        "Price avg": worst["exporter_price"],
                        "Price range": [
                            f"${lo:,.2f} – ${hi:,.2f}"
                            for lo, hi in zip(worst["price_min"], worst["price_max"])],
                        "Peer avg": worst["peer_avg"],
                        "Disc vs avg": worst["disc_vs_avg_pct"],
                        "Disc range": [
                            f"{lo:.1%} – {hi:.1%}"
                            for lo, hi in zip(worst["disc_min"], worst["disc_max"])],
                        "Pure qty (kg)": worst["pure_qty"],
                        "Vol share": worst["volume_share"],
                        "% qty below avg": worst["pct_qty_below_avg"],
                        "% periods below avg": worst["consistency"],
                        "Forgone vs avg": worst["forgone_vs_avg"],
                        "Months below avg": worst["months_below_avg"],
                        "Thin periods": worst["thin_periods"],
                    })

                    def _flag_qty(v):
                        """Red above 75%, amber above 40% - volume at risk."""
                        if pd.isna(v):
                            return ""
                        if v >= 0.75:
                            return "background-color: #FDECEA; color: #C00000; font-weight: 700"
                        if v >= 0.40:
                            return "background-color: #FFF8E1; color: #8A6100; font-weight: 600"
                        return ""

                    styled = (
                        show.style
                        .format({"Price avg": "${:,.2f}", "Peer avg": "${:,.2f}",
                                 "Disc vs avg": "{:.1%}", "Pure qty (kg)": "{:,.0f}",
                                 "Vol share": "{:.1%}", "% qty below avg": "{:.0%}",
                                 "% periods below avg": "{:.0%}",
                                 "Forgone vs avg": "${:,.0f}"})
                        .map(_flag_qty, subset=["% qty below avg"])
                    )
                    st.dataframe(
                        styled, width="stretch", hide_index=True,
                        column_config={
                            "Price avg": st.column_config.NumberColumn(
                                "Price avg", help=PRICE_RANGE),
                            "Price range": st.column_config.TextColumn(
                                "Price range", help=PRICE_RANGE),
                            "Peer avg": st.column_config.NumberColumn(
                                "Peer avg", help=PEER_AVERAGE),
                            "Disc range": st.column_config.TextColumn(
                                "Disc range", help=DISCOUNT_RANGE),
                            "Pure qty (kg)": st.column_config.NumberColumn(
                                "Pure qty (kg)", help=PURE_QUANTITY),
                            "% qty below avg": st.column_config.NumberColumn(
                                "% qty below avg", help=PCT_QTY_BELOW),
                            "% periods below avg": st.column_config.NumberColumn(
                                "% periods below avg", help=CONSISTENCY),
                            "Forgone vs avg": st.column_config.NumberColumn(
                                "Forgone vs avg", help=VALUE_FORGONE),
                            "Months below avg": st.column_config.TextColumn(
                                "Months below avg", help=MONTHS_COLUMN_BELOW),
                            "Thin periods": st.column_config.NumberColumn(
                                "Thin periods", help=THIN_MARKET),
                        })

                    st.caption(
                        "🔴 above 75% / 🟡 above 40% of contained tonnage sold "
                        "below the peer average. This is the column that tracks "
                        "the money — an exporter can be below average in only a "
                        "couple of periods and still have most of its tonnage "
                        "affected, if those periods carried the big consignments."
                    )
                    download_button(
                        f"Worst Traders {mineral} {yr}", {"Worst": show},
                        f"RMB-3T_WorstTraders_{mineral}_{yr}",
                        source="Exporter Scorecard", filters=fdesc,
                        key=f"dl_wt_{mineral}")

# ============================================================ best traders ====
with tabs[2]:
    section("Best traders by commodity and year")

    with st.expander("📖 What this means, and exactly how it is calculated", expanded=False):
        st.markdown(BEST_TRADER_METHOD)

    insight_banner(
        "Compare this tab against <b>Worst Traders</b> for the same commodity "
        "and year. Where the same buyers or destinations appear on both sides, "
        "that is usually the clearest sign of a real, addressable pricing gap "
        "— not a structural disadvantage."
    )

    if sc.empty:
        info_banner("No scorecard available.")
    else:
        c1, c2, c3 = st.columns(3)
        mode = c1.selectbox(
            "Rank by", ["Value gained ($)", "Premium (%)"], key="t3i_bt_mode",
            help="Value gained prioritises where the extra money is. Premium "
                 "finds the largest percentage premium regardless of size.")
        topn = c2.number_input("Show top N", 3, 20, 5, key="t3i_bt_n")
        min_qty = c3.number_input(
            "Min pure quantity (kg)", 0.0, 1e6,
            5000.0 if mode == "Premium (%)" else 0.0, 1000.0, key="t3i_bt_q",
            help="Stops a single tiny shipment topping the table. "
                 + PURE_QUANTITY)

        rank_by = "gained_vs_avg" if mode == "Value gained ($)" else "disc_vs_avg_pct"
        years = sorted(int(y) for y in sc["year"].dropna().unique())
        minerals = [m for m in ["Cassiterite", "Coltan", "Wolframite"]
                    if m in sc["mineral"].unique()]

        if not minerals or not years:
            info_banner("No data for the current filters.")
        else:
            mtabs = st.tabs([MINERAL_LABEL.get(m, m) for m in minerals])
            for tab, mineral in zip(mtabs, minerals):
                with tab:
                    yr = st.selectbox("Year", years, index=len(years) - 1,
                                      key=f"t3i_bt_y_{mineral}")
                    best = bp.best_traders(sc, mineral, yr, int(topn),
                                           rank_by, min_qty)
                    if best.empty:
                        info_banner("No exporters match for this year.")
                        continue

                    show = pd.DataFrame({
                        "Exporter": best["exporter"],
                        "Price avg": best["exporter_price"],
                        "Price range": [
                            f"${lo:,.2f} – ${hi:,.2f}"
                            for lo, hi in zip(best["price_min"], best["price_max"])],
                        "Peer avg": best["peer_avg"],
                        "Premium vs avg": -best["disc_vs_avg_pct"],
                        "Premium range": [
                            f"{-hi:.1%} – {-lo:.1%}"
                            for lo, hi in zip(best["disc_min"], best["disc_max"])],
                        "Pure qty (kg)": best["pure_qty"],
                        "Vol share": best["volume_share"],
                        "% qty above avg": best["pct_qty_above_avg"],
                        "% periods above avg": best["premium_consistency"],
                        "Value gained": best["gained_vs_avg"],
                        "Months above avg": best["months_above_avg"],
                        "Thin periods": best["thin_periods"],
                    })

                    def _flag_qty_best(v):
                        """Green above 75%, teal above 40% - a positive signal,
                        the mirror of the red/amber used on Worst Traders."""
                        if pd.isna(v):
                            return ""
                        if v >= 0.75:
                            return "background-color: #E8F5EE; color: #1A5C38; font-weight: 700"
                        if v >= 0.40:
                            return "background-color: #F2FAF5; color: #2D6B4A; font-weight: 600"
                        return ""

                    styled = (
                        show.style
                        .format({"Price avg": "${:,.2f}", "Peer avg": "${:,.2f}",
                                 "Premium vs avg": "{:.1%}", "Pure qty (kg)": "{:,.0f}",
                                 "Vol share": "{:.1%}", "% qty above avg": "{:.0%}",
                                 "% periods above avg": "{:.0%}",
                                 "Value gained": "${:,.0f}"})
                        .map(_flag_qty_best, subset=["% qty above avg"])
                    )
                    st.dataframe(
                        styled, width="stretch", hide_index=True,
                        column_config={
                            "Price avg": st.column_config.NumberColumn(
                                "Price avg", help=PRICE_RANGE),
                            "Price range": st.column_config.TextColumn(
                                "Price range", help=PRICE_RANGE),
                            "Peer avg": st.column_config.NumberColumn(
                                "Peer avg", help=PEER_AVERAGE),
                            "Premium range": st.column_config.TextColumn(
                                "Premium range", help=DISCOUNT_RANGE),
                            "Pure qty (kg)": st.column_config.NumberColumn(
                                "Pure qty (kg)", help=PURE_QUANTITY),
                            "% qty above avg": st.column_config.NumberColumn(
                                "% qty above avg", help="The mirror of "
                                "'% qty below avg' on Worst Traders: the share "
                                "of this exporter's contained tonnage sold in "
                                "periods when its price beat the peer average."),
                            "% periods above avg": st.column_config.NumberColumn(
                                "% periods above avg", help=CONSISTENCY),
                            "Value gained": st.column_config.NumberColumn(
                                "Value gained", help=VALUE_FORGONE),
                            "Months above avg": st.column_config.TextColumn(
                                "Months above avg", help=MONTHS_COLUMN_ABOVE),
                            "Thin periods": st.column_config.NumberColumn(
                                "Thin periods", help=THIN_MARKET),
                        })

                    st.caption(
                        "🟢 above 75% / 🟢 above 40% of contained tonnage sold "
                        "above the peer average. The same read as Worst Traders, "
                        "mirrored: a strong result concentrated in a couple of "
                        "big periods is a different pattern from one earned "
                        "consistently all year."
                    )
                    download_button(
                        f"Best Traders {mineral} {yr}", {"Best": show},
                        f"RMB-3T_BestTraders_{mineral}_{yr}",
                        source="Exporter Scorecard", filters=fdesc,
                        key=f"dl_bt_{mineral}")

# ========================================================= exporter detail ====
with tabs[3]:
    section("Exporter detail")
    ed_years = sorted(int(y) for y in d["year"].dropna().unique())
    f1, f2, f3 = st.columns([2, 1, 1])
    exporters = sorted(d["exporter"].dropna().unique())
    e = f1.selectbox("Exporter", exporters, key="t3i_ed_exp")
    pick_years = f2.multiselect("Year", ed_years, default=ed_years,
                                key="t3i_ed_years",
                                help="Narrows this tab only.")

    # Month options follow the year selection, so the list stays manageable.
    _ym_scope = d[d["year"].isin(pick_years)] if pick_years else d
    ed_months = sorted(m for m in _ym_scope["year_month"].dropna().unique())
    pick_months = f3.multiselect(
        "Year-Month", ed_months, default=[], key="t3i_ed_months",
        help="Leave empty for all months. Paste a month from the "
             "'Months below/above avg' column on Worst or Best Traders to "
             "jump straight to it.")

    sub = d[d["exporter"] == e]
    if pick_years:
        sub = sub[sub["year"].isin(pick_years)]
    if pick_months:
        sub = sub[sub["year_month"].isin(pick_months)]
    if sub.empty:
        info_banner("No shipments for this exporter in the selected period.")
        st.stop()

    warn = coverage.coverage_warning(state.active(), pick_years or ed_years)
    if warn and not pick_months:
        warn_banner(warn)
    if pick_months:
        info_banner(
            f"Filtered to <b>{len(pick_months)}</b> month(s). The shipment "
            "figures below reflect only those months; the peer-performance "
            "table underneath stays on an annual basis."
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Export value", fmt_money_m(sub["shipment_value_usd"].sum()))
    c2.metric("Shipments", fmt(len(sub)))
    c3.metric("Pure quantity", fmt(sub["pure_quantity_kg"].sum()) + " kg",
              help=PURE_QUANTITY)
    c4.metric("Buyers", fmt(sub["buyer"].nunique()))

    esc = sc[sc["exporter"] == e] if not sc.empty else pd.DataFrame()
    if not esc.empty and pick_years:
        esc = esc[esc["year"].isin(pick_years)]
    if not esc.empty:
        st.caption("Peer performance by mineral and year")
        st.dataframe(
            esc[["mineral", "year", "exporter_price", "peer_avg",
                 "peer_avg_excl_self", "disc_vs_avg_pct", "pct_qty_below_avg",
                 "consistency", "pure_qty", "forgone_vs_avg"]]
            .style.format({"exporter_price": "${:,.2f}", "peer_avg": "${:,.2f}",
                           "peer_avg_excl_self": "${:,.2f}",
                           "disc_vs_avg_pct": "{:.1%}",
                           "pct_qty_below_avg": "{:.0%}", "consistency": "{:.0%}",
                           "pure_qty": "{:,.0f}", "forgone_vs_avg": "${:,.0f}"}),
            width="stretch", hide_index=True,
            column_config={
                "peer_avg": st.column_config.NumberColumn(
                    "peer_avg", help=PEER_AVERAGE),
                "peer_avg_excl_self": st.column_config.NumberColumn(
                    "peer_avg_excl_self", help=PEER_AVG_EXCL_SELF),
                "pct_qty_below_avg": st.column_config.NumberColumn(
                    "pct_qty_below_avg", help=PCT_QTY_BELOW),
                "consistency": st.column_config.NumberColumn(
                    "consistency", help=CONSISTENCY),
                "pure_qty": st.column_config.NumberColumn(
                    "pure_qty", help=PURE_QUANTITY),
                "forgone_vs_avg": st.column_config.NumberColumn(
                    "forgone_vs_avg", help=VALUE_FORGONE),
            })

    st.caption("Products and destinations")
    c1, c2 = st.columns(2)
    with c1:
        st.dataframe(sub.groupby("product")["shipment_value_usd"].sum()
                     .sort_values(ascending=False).to_frame("Value")
                     .style.format("${:,.0f}"), width="stretch")
    with c2:
        st.dataframe(sub.groupby("destination")["shipment_value_usd"].sum()
                     .sort_values(ascending=False).head(10).to_frame("Value")
                     .style.format("${:,.0f}"), width="stretch")

    download_button(f"Exporter Detail — {e}",
                    {"Shipments": sub, "Peer performance": esc},
                    f"RMB-3T_Exporter_{e[:20]}", source="Exporter Scorecard",
                    filters=fdesc, key="dl_ed")

# ======================================================== compare exporters ====
with tabs[4]:
    section("Compare exporters")
    if sc.empty:
        info_banner("No scorecard available.")
    else:
        f1, f2, f3 = st.columns([1, 1, 1])
        prods = sorted(disc["product"].dropna().unique())
        prod = f1.selectbox("Product", prods, key="t3i_cmp_prod")

        cmp_years = sorted(int(y) for y in disc["year"].dropna().unique())
        pick_years = f2.multiselect("Year", cmp_years, default=cmp_years,
                                    key="t3i_cmp_years",
                                    help="Narrows this tab only.")

        s = disc[disc["product"] == prod].copy()
        if pick_years:
            s = s[s["year"].isin(pick_years)]
        s["period"] = s["period"].astype(str)

        cmp_months = sorted(s["period"].unique())
        pick_months = f3.multiselect(
            "Year-Month", cmp_months, default=[], key="t3i_cmp_months",
            help="Leave empty for all months. Paste a month from the "
                 "'Months below/above avg' column on Worst or Best Traders.")
        if pick_months:
            s = s[s["period"].isin(pick_months)]

        if s.empty:
            info_banner("No data for the selected product and period.")
            st.stop()

        warn = coverage.coverage_warning(state.active(), pick_years or cmp_years)
        if warn and not pick_months:
            warn_banner(warn)

        available = sorted(s["exporter"].unique())
        chosen = st.multiselect("Exporters", available,
                                default=available[:3], key="t3i_cmp_exp")
        if not chosen:
            info_banner("Select at least one exporter.")
        else:
            chart = s.groupby("period")[["peer_avg"]].first().rename(
                columns={"peer_avg": "Market average"})
            for e in chosen:
                chart[e] = s[s["exporter"] == e].set_index("period")["price"]
            st.line_chart(chart)

            comp = (
                s[s["exporter"].isin(chosen)]
                .groupby("exporter")
                .apply(lambda x: pd.Series({
                    "Price": x["value"].sum() / x["pure_qty"].sum(),
                    "Peer avg": (x["peer_avg"] * x["pure_qty"]).sum() / x["pure_qty"].sum(),
                    "Peer avg (excl. self)": bp.weighted_mean_skip_na(
                        x["peer_avg_excl_self"], x["pure_qty"]),
                    "Contained kg": x["pure_qty"].sum(),
                    "Periods": x["period"].nunique(),
                    "% below avg": x["below_avg"].mean(),
                    "Forgone": x["forgone_vs_avg"].sum(),
                }), include_groups=False)
            )
            comp["Discount"] = (comp["Peer avg"] - comp["Price"]) / comp["Peer avg"]
            st.dataframe(
                comp.style.format({
                    "Price": "${:,.2f}", "Peer avg": "${:,.2f}",
                    "Peer avg (excl. self)": "${:,.2f}",
                    "Contained kg": "{:,.0f}", "% below avg": "{:.0%}",
                    "Forgone": "${:,.0f}", "Discount": "{:.1%}"}),
                width="stretch",
                column_config={
                    "Peer avg": st.column_config.NumberColumn(
                        "Peer avg", help=PEER_AVERAGE),
                    "Peer avg (excl. self)": st.column_config.NumberColumn(
                        "Peer avg (excl. self)", help=PEER_AVG_EXCL_SELF),
                })
            download_button("Exporter Comparison", {"Comparison": comp.reset_index()},
                            "RMB-3T_ExporterComparison",
                            source="Exporter Scorecard", filters=fdesc, key="dl_cmp")
