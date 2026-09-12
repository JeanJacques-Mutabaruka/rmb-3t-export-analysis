"""3 · Market Overview — volumes, values, prices, grades, buyers, destinations."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import state  # noqa: E402
from app.downloads import download_button  # noqa: E402
from app.formatting import fmt, fmt_money_m, table_formats  # noqa: E402
from app.glossary import GRADE_STD_DEV, GROSS_QUANTITY, PURE_QUANTITY, UNIT_PRICE  # noqa: E402
from app.style import info_banner, section  # noqa: E402

state.init_state()
filters = state.page_setup("📊 Market Overview")

if not state.require_data():
    st.stop()

d = state.apply_filters(state.active(), filters)
if d.empty:
    info_banner("No rows match the current filters.")
    st.stop()

fdesc = f"years={filters.get('years')}, minerals={filters.get('minerals')}"
tabs = st.tabs(["📊 Volumes & Values", "💵 Price Trends", "🧪 Grades",
                "🌍 Buyers & Destinations"])

# ======================================================== volumes & values ====
with tabs[0]:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Shipments", fmt(len(d)))
    c2.metric("Export value", fmt_money_m(d["shipment_value_usd"].sum()))
    c3.metric("Gross quantity", fmt(d["quantity_kg"].sum()) + " kg",
              help=GROSS_QUANTITY)
    c4.metric("Pure quantity (contained metal)",
              fmt(d["pure_quantity_kg"].sum()) + " kg", help=PURE_QUANTITY)

    section("Export value by year")
    st.caption("The most recent year is usually partial — read it as year-to-date.")
    yearly = d.groupby("year").agg(
        Value=("shipment_value_usd", "sum"),
        Quantity=("quantity_kg", "sum"),
        Shipments=("shipment_value_usd", "size"),
    )
    st.bar_chart(yearly["Value"])

    section("Mineral mix")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Share of value, %")
        mix = d.pivot_table(index="year", columns="mineral",
                            values="shipment_value_usd", aggfunc="sum").fillna(0)
        vshare = (mix.div(mix.sum(axis=1), axis=0) * 100).round(1)
        st.dataframe(vshare, width="stretch")
    with c2:
        st.caption("Share of quantity, %")
        qmix = d.pivot_table(index="year", columns="mineral",
                             values="quantity_kg", aggfunc="sum").fillna(0)
        qshare = (qmix.div(qmix.sum(axis=1), axis=0) * 100).round(1)
        st.dataframe(qshare, width="stretch")

    st.dataframe(yearly.style.format({"Value": "${:,.0f}", "Quantity": "{:,.0f}",
                                      "Shipments": "{:,.0f}"}), width="stretch")
    download_button("Volumes & Values",
                    {"By year": yearly.reset_index(),
                     "Value share": vshare.reset_index(),
                     "Quantity share": qshare.reset_index()},
                    "RMB-3T_VolumesValues", source="Market Overview",
                    filters=fdesc, key="dl_vv")

# ============================================================ price trends ====
with tabs[1]:
    section("Realised price ($/kg contained metal)")
    st.caption("Volume-weighted across all exporters.")
    with st.expander("How this price is calculated"):
        st.markdown(UNIT_PRICE)
        st.markdown(PURE_QUANTITY)
    p = d[d["pure_quantity_kg"] > 0].copy()
    monthly = (
        p.groupby(["year_month", "mineral"])
        .apply(lambda x: x["shipment_value_usd"].sum() / x["pure_quantity_kg"].sum(),
               include_groups=False)
        .unstack()
        .sort_index()
    )
    st.line_chart(monthly)

    annual = (
        p.groupby(["year", "mineral"])
        .apply(lambda x: x["shipment_value_usd"].sum() / x["pure_quantity_kg"].sum(),
               include_groups=False)
        .unstack()
    )
    st.caption("Annual volume-weighted average, $/kg")
    st.dataframe(annual.style.format("${:,.2f}"), width="stretch")
    download_button("Price Trends",
                    {"Monthly": monthly.reset_index(), "Annual": annual.reset_index()},
                    "RMB-3T_PriceTrends", source="Market Overview",
                    filters=fdesc, key="dl_pt")

# ================================================================== grades ====
with tabs[2]:
    section("Grade statistics")
    st.caption(
        "Weighted average is weighted by shipment quantity, so it reflects the "
        "grade of the material actually exported."
    )
    products = d.groupby("product")["shipment_value_usd"].sum() \
        .sort_values(ascending=False).index.tolist()
    gf1, gf2 = st.columns([2, 1])
    chosen = gf1.multiselect("Products", products, default=products[:3],
                             key="t3i_grade_products")
    g = d[d["product"].isin(chosen)]

    if g.empty:
        info_banner("Select at least one product.")
    else:
        rows = []
        for (prod, year), sub in g.groupby(["product", "year"]):
            w = sub["quantity_kg"]
            rows.append({
                "Product": prod, "Year": int(year), "Shipments": len(sub),
                "Weighted avg %": float(np.average(sub["grade_pct"], weights=w))
                if w.sum() > 0 else np.nan,
                "Min %": sub["grade_pct"].min(),
                "Max %": sub["grade_pct"].max(),
                "Std dev": sub["grade_pct"].std(),
                "Quantity kg": w.sum(),
            })
        stats = pd.DataFrame(rows).sort_values(["Product", "Year"])
        st.dataframe(
            stats.style.format({
                "Weighted avg %": "{:.2f}", "Min %": "{:.2f}", "Max %": "{:.2f}",
                "Std dev": "{:.2f}", "Quantity kg": "{:,.0f}"}),
            width="stretch", hide_index=True,
            column_config={
                "Std dev": st.column_config.NumberColumn(
                    "Std dev", help=GRADE_STD_DEV),
                "Quantity kg": st.column_config.NumberColumn(
                    "Quantity kg", help=GROSS_QUANTITY),
            })
        with st.expander("What does the standard deviation mean in practice?"):
            st.markdown(GRADE_STD_DEV)

        section("Grade range over time")
        st.caption(
            "Weighted average with the minimum and maximum grade recorded in "
            "each year. A widening band means less consistent material."
        )
        band_prod = gf2.selectbox(
            "Product for the range chart", chosen, key="t3i_grade_band")
        band = stats[stats["Product"] == band_prod].set_index("Year")
        st.line_chart(band[["Weighted avg %", "Min %", "Max %"]])

        c1, c2 = st.columns(2)
        with c1:
            st.caption("Weighted average grade over time")
            st.line_chart(stats.pivot(index="Year", columns="Product",
                                      values="Weighted avg %"))
        with c2:
            st.caption("Dispersion (std dev) — rising means less consistent material")
            st.line_chart(stats.pivot(index="Year", columns="Product",
                                      values="Std dev"))
        download_button("Grade Statistics", {"Grades": stats},
                        "RMB-3T_GradeStats", source="Market Overview",
                        filters=fdesc, key="dl_gr")

# ================================================ buyers and destinations ====
with tabs[3]:
    f1, f2 = st.columns([1, 2])
    dim = f1.radio("Dimension", ["buyer", "destination"], horizontal=True,
                   format_func=str.title, key="t3i_dim")
    bd_years = sorted(int(y) for y in d["year"].dropna().unique())
    pick_years = f2.multiselect("Year", bd_years, default=bd_years,
                                key="t3i_bd_years",
                                help="Narrows this tab only. The sidebar year "
                                     "filter applies to every page.")

    bd = d[d["year"].isin(pick_years)] if pick_years else d
    if bd.empty:
        info_banner("No rows for the selected years.")
        st.stop()

    tot = bd.groupby(dim)["shipment_value_usd"].sum().sort_values(ascending=False)
    share = tot / tot.sum() * 100
    hhi = float((share ** 2).sum())

    c1, c2, c3 = st.columns(3)
    c1.metric(f"Distinct {dim}s", fmt(len(tot)))
    c2.metric("Top-5 share", f"{share.head(5).sum():.1f}%")
    c3.metric("HHI", fmt(hhi),
              help="Herfindahl-Hirschman Index. Below 1,500 unconcentrated; "
                   "1,500–2,500 moderate; above 2,500 highly concentrated.")

    table = pd.DataFrame({"Value": tot, "Share %": share})
    table["Cumulative %"] = table["Share %"].cumsum()
    st.dataframe(table.style.format({"Value": "${:,.0f}", "Share %": "{:.1f}%",
                                     "Cumulative %": "{:.1f}%"}),
                 width="stretch", height=380)

    section("Share over time — top 6")
    top = tot.head(6).index.tolist()
    piv = bd[bd[dim].isin(top)].pivot_table(index="year", columns=dim,
                                          values="shipment_value_usd",
                                          aggfunc="sum").fillna(0)
    yr_tot = bd.groupby("year")["shipment_value_usd"].sum()
    st.line_chart(piv.div(yr_tot, axis=0) * 100)
    st.caption("Share of each year's total export value, %.")

    download_button(f"{dim.title()} Concentration",
                    {"Concentration": table.reset_index(),
                     "Share over time": (piv.div(yr_tot, axis=0) * 100).reset_index()},
                    f"RMB-3T_{dim.title()}Concentration",
                    source="Market Overview", filters=fdesc, key="dl_conc")
