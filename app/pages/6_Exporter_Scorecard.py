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
    CONSISTENCY, DISCOUNT_RANGE, PCT_QTY_BELOW, PEER_AVERAGE, PEER_MAX,
    PRICE_RANGE, PURE_QUANTITY, THIN_MARKET, VALUE_FORGONE,
    WORST_TRADER_CAUTION, WORST_TRADER_METHOD,
)
from app.style import info_banner, section, warn_banner  # noqa: E402
from engine import benchmarks_peer as bp  # noqa: E402
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
stats = bp.peer_stats(ep, grain, window)
disc = bp.discounts(ep, stats)
sc = bp.scorecard(disc)

st.caption(f"Peer basis: **{label}** — change it on 5 · Peer Benchmark → Basis Settings.")
fdesc = f"{label}; years={filters.get('years')}; minerals={filters.get('minerals')}"

tabs = st.tabs(["🏆 Ranking", "🔻 Worst Traders", "👤 Exporter Detail",
                "🔀 Compare Exporters"])

# ================================================================= ranking ====
with tabs[0]:
    section("Exporter ranking by export value")
    rank = (
        d.groupby("exporter")
        .agg(Value=("shipment_value_usd", "sum"),
             Quantity=("quantity_kg", "sum"),
             Contained=("pure_quantity_kg", "sum"),
             Shipments=("shipment_value_usd", "size"))
        .sort_values("Value", ascending=False)
    )
    rank["Share %"] = rank["Value"] / rank["Value"].sum() * 100
    rank["Cumulative %"] = rank["Share %"].cumsum()
    rank.insert(0, "Rank", range(1, len(rank) + 1))

    c1, c2 = st.columns(2)
    c1.metric("Exporters", fmt(len(rank)))
    c2.metric("Top-10 share", f"{rank.head(10)['Share %'].sum():.1f}%")

    st.dataframe(
        rank.style.format({
            "Value": "${:,.0f}", "Quantity": "{:,.0f}", "Contained": "{:,.0f}",
            "Shipments": "{:,.0f}", "Share %": "{:.1f}%",
            "Cumulative %": "{:.1f}%"}),
        width="stretch", height=420,
        column_config={
            "Contained": st.column_config.NumberColumn(
                "Contained (pure qty)", help=PURE_QUANTITY),
        })
    download_button("Exporter Ranking", {"Ranking": rank.reset_index()},
                    "RMB-3T_ExporterRanking", source="Exporter Scorecard",
                    filters=fdesc, key="dl_rank")

# =========================================================== worst traders ====
with tabs[1]:
    section("Worst traders by commodity and year")

    with st.expander("📖 What this means, and exactly how it is calculated", expanded=False):
        st.markdown(WORST_TRADER_METHOD)
        warn_banner(WORST_TRADER_CAUTION)

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

# ========================================================= exporter detail ====
with tabs[2]:
    section("Exporter detail")
    ed_years = sorted(int(y) for y in d["year"].dropna().unique())
    f1, f2 = st.columns([2, 1])
    exporters = sorted(d["exporter"].dropna().unique())
    e = f1.selectbox("Exporter", exporters, key="t3i_ed_exp")
    pick_years = f2.multiselect("Year", ed_years, default=ed_years,
                                key="t3i_ed_years",
                                help="Narrows this tab only.")

    sub = d[d["exporter"] == e]
    if pick_years:
        sub = sub[sub["year"].isin(pick_years)]
    if sub.empty:
        info_banner("No shipments for this exporter in the selected years.")
        st.stop()

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
                 "disc_vs_avg_pct", "pct_qty_below_avg", "consistency",
                 "pure_qty", "forgone_vs_avg"]]
            .style.format({"exporter_price": "${:,.2f}", "peer_avg": "${:,.2f}",
                           "disc_vs_avg_pct": "{:.1%}",
                           "pct_qty_below_avg": "{:.0%}", "consistency": "{:.0%}",
                           "pure_qty": "{:,.0f}", "forgone_vs_avg": "${:,.0f}"}),
            width="stretch", hide_index=True,
            column_config={
                "peer_avg": st.column_config.NumberColumn(
                    "peer_avg", help=PEER_AVERAGE),
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
with tabs[3]:
    section("Compare exporters")
    if sc.empty:
        info_banner("No scorecard available.")
    else:
        prods = sorted(disc["product"].dropna().unique())
        prod = st.selectbox("Product", prods, key="t3i_cmp_prod")
        s = disc[disc["product"] == prod].copy()
        s["period"] = s["period"].astype(str)

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
                    "Contained kg": x["pure_qty"].sum(),
                    "Periods": x["period"].nunique(),
                    "% below avg": x["below_avg"].mean(),
                    "Forgone": x["forgone_vs_avg"].sum(),
                }), include_groups=False)
            )
            comp["Discount"] = (comp["Peer avg"] - comp["Price"]) / comp["Peer avg"]
            st.dataframe(comp.style.format({
                "Price": "${:,.2f}", "Peer avg": "${:,.2f}",
                "Contained kg": "{:,.0f}", "% below avg": "{:.0%}",
                "Forgone": "${:,.0f}", "Discount": "{:.1%}"}), width="stretch")
            download_button("Exporter Comparison", {"Comparison": comp.reset_index()},
                            "RMB-3T_ExporterComparison",
                            source="Exporter Scorecard", filters=fdesc, key="dl_cmp")
