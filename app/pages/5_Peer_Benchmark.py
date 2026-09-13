"""5 · Peer Benchmark — exporters against the Rwandan market itself."""
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
from app.formatting import fmt, fmt_money_m  # noqa: E402
from app.glossary import (  # noqa: E402
    PEER_AVERAGE, PEER_AVG_EXCL_SELF, PEER_MAX, PEER_MIN, PURE_QUANTITY,
    THIN_MARKET, VALUE_FORGONE,
)
from app.style import info_banner, section, warn_banner  # noqa: E402
from engine import benchmarks_peer as bp  # noqa: E402
from engine import coverage  # noqa: E402

state.init_state()
filters = state.page_setup("⚖️ Peer Benchmark")

if not state.require_data():
    st.stop()

warn_banner(
    "Trading below the peer average is <b>not by itself evidence of wrongdoing</b>. "
    "Contract timing, impurity penalties, lot size, payment terms and long-term "
    "offtake agreements all produce legitimate discounts. This page identifies "
    "where to look, not what was found."
)

d = state.apply_filters(state.active(), filters)
if d.empty:
    info_banner("No rows match the current filters.")
    st.stop()

tabs = st.tabs(["⚙️ Basis Settings", "📊 Peer Statistics", "🚫 Outliers Excluded",
                "📉 Discounts", "💸 Value Forgone"])

# =========================================================== basis settings ====
with tabs[0]:
    section("Benchmark basis")
    st.caption(
        "Peers are exporters shipping the **same product** in the same period — "
        "not the same mineral. Mineral-level grouping would put 99.9%-grade tin "
        "ingots in the same pool as 4%-grade tin slag."
    )

    c1, c2 = st.columns(2)
    grain = c1.radio("Period grain", ["month", "quarter"], horizontal=True,
                     key="t3i_grain",
                     format_func=lambda g: "Month" if g == "month" else "Quarter")

    # Switching grain resets the window to that grain's own default, otherwise
    # "Moving 3-quarter" silently carries over from the month setting.
    default_n = 3 if grain == "month" else 2
    if st.session_state.get("t3i_prev_grain") != grain:
        st.session_state["t3i_prev_grain"] = grain
        st.session_state["t3i_window"] = default_n

    window = c2.number_input(
        f"Window size (number of {grain}s)", 1, 12, key="t3i_window",
        help="1 = the current period only. Above 1 = a moving window ending at "
             "that period.")

    label = ("Current " if window == 1 else f"Moving {window}-") + grain
    st.session_state["t3i_basis_label"] = label
    st.info(f"Active basis: **{label}**")

    st.markdown(
        f"""
| Statistic | How it is computed |
|---|---|
| **Average** | Volume-weighted across the whole {window}-{grain} window |
| **Maximum** | Highest exporter-level price in the window |
| **Minimum** | Lowest exporter-level price in the window |
| **Range** | Maximum − Minimum |

**Minimum is a statistic, not a loss basis.** An exporter is not "losing"
relative to the floor. It is shown for range and error detection — an
implausibly low floor usually points at a record that should be excluded.

Periods with fewer than **{bp.THIN_MARKET_THRESHOLD}** active exporters are
flagged as thin: with one or two exporters the "market" is largely the exporter
itself.
        """
    )

grain = st.session_state.get("t3i_grain", "month")
window = int(st.session_state.get("t3i_window", 3 if grain == "month" else 2))
label = st.session_state.get("t3i_basis_label", "Current month")

ep = bp.exporter_periods(d, grain)
if ep.empty:
    info_banner("Not enough priced data to build peer benchmarks.")
    st.stop()
stats, outliers = bp.peer_stats(ep, grain, window)
disc = bp.discounts(ep, stats)
fdesc = f"{label}; years={filters.get('years')}; minerals={filters.get('minerals')}"

# ========================================================== peer statistics ====
with tabs[1]:
    section(f"Peer statistics — {label}")
    st.caption(
        "Shown here with extreme values removed (see the Outliers Excluded "
        "tab) — this affects the DISPLAY only. Discount %, Value Forgone and "
        "Worst Traders are computed on the full peer set, unchanged."
    )
    if stats.empty:
        info_banner("No statistics available.")
    else:
        prods = sorted(stats["product"].unique())
        prod = st.selectbox("Product", prods, key="t3i_ps_prod")
        s = stats[stats["product"] == prod].copy()
        s["period"] = s["period"].astype(str)

        st.line_chart(s.set_index("period")[
            ["peer_avg_clean", "peer_max_clean", "peer_min_clean"]]
            .rename(columns={"peer_avg_clean": "peer_avg", "peer_max_clean": "peer_max",
                             "peer_min_clean": "peer_min"}))
        st.caption("Average, maximum and minimum realised price, $/kg contained metal "
                   "— outliers excluded.")

        thin = int(s["thin_market"].sum())
        if thin:
            warn_banner(
                f"{thin} period(s) had fewer than {bp.THIN_MARKET_THRESHOLD} "
                "active exporters — the benchmark is weak there.")
        n_out = int(s["n_outliers_excluded"].sum())
        if n_out:
            st.caption(
                f"🚫 {n_out} extreme value(s) excluded from this product's "
                "statistics across all periods shown — see Outliers Excluded.")

        show = s[["period", "n_exporters", "n_shipments",
                  "n_outliers_excluded", "thin_market"]].copy()
        show["peer_avg"] = s["peer_avg_clean"]
        show["peer_max"] = s["peer_max_clean"]
        show["peer_min"] = s["peer_min_clean"]
        show["peer_range"] = s["peer_range_clean"]
        show = show[["period", "peer_avg", "peer_max", "peer_min", "peer_range",
                    "n_exporters", "n_shipments", "n_outliers_excluded",
                    "thin_market"]]
        st.dataframe(
            show[["period", "peer_avg", "peer_max", "peer_min", "peer_range",
                  "n_exporters", "n_shipments", "n_outliers_excluded",
                  "thin_market"]]
            .style.format({"peer_avg": "${:,.2f}", "peer_max": "${:,.2f}",
                           "peer_min": "${:,.2f}", "peer_range": "${:,.2f}"}),
            width="stretch", height=380, hide_index=True,
            column_config={
                "peer_avg": st.column_config.NumberColumn("peer_avg", help=PEER_AVERAGE),
                "peer_max": st.column_config.NumberColumn("peer_max", help=PEER_MAX),
                "peer_min": st.column_config.NumberColumn("peer_min", help=PEER_MIN),
                "peer_range": st.column_config.NumberColumn(
                    "peer_range", help="Maximum minus minimum. A widening range "
                    "means exporters are getting increasingly different outcomes "
                    "for the same material."),
                "n_exporters": st.column_config.NumberColumn(
                    "n_exporters", help="Number of DISTINCT exporters active "
                    "in this period/window."),
                "n_shipments": st.column_config.NumberColumn(
                    "n_shipments", help="Total number of shipment records "
                    "behind this period/window — several shipments from the "
                    "same exporter all count."),
                "n_outliers_excluded": st.column_config.NumberColumn(
                    "n_outliers_excluded", help="Exporter-period prices "
                    "removed from Average/Max/Min/Range above as extreme "
                    "values. Detail on the Outliers Excluded tab."),
                "thin_market": st.column_config.CheckboxColumn(
                    "thin_market", help=THIN_MARKET),
            })
        download_button("Peer Statistics", {"Stats": show},
                        f"RMB-3T_PeerStats_{prod}", source="Peer Benchmark",
                        filters=fdesc, key="dl_ps")

# ======================================================= outliers excluded ====
with tabs[2]:
    section(f"Outliers excluded from Peer Statistics — {label}")
    st.markdown(
        f"""
An exporter-period price is treated as extreme, and left out of the Average /
Maximum / Minimum / Range shown on the Peer Statistics tab, when it falls
outside **{bp.OUTLIER_IQR_FACTOR:g}× the interquartile range** of that
product-period's prices — a standard, robust threshold that is not itself
distorted by the outlier it is trying to catch.

Skipped when a period has fewer than **{bp.OUTLIER_MIN_EXPORTERS}** exporters,
since quartiles are not meaningful on that few points — those periods are
already flagged separately as thin markets.

**This exclusion affects the Peer Statistics display only.** Discount %, Value
Forgone and Worst Traders on the other tabs use the full peer set, exactly as
before — nothing here has changed those figures.
        """
    )

    if outliers.empty:
        info_banner("No extreme values detected in the current selection.")
    else:
        st.warning(
            f"🚫 {len(outliers)} exporter-period price(s) excluded across "
            f"{outliers['product'].nunique()} product(s)."
        )
        oc1, oc2 = st.columns(2)
        o_prods = sorted(outliers["product"].unique())
        o_prod = oc1.selectbox("Product", ["All"] + o_prods, key="t3i_out_prod")
        o_show = outliers if o_prod == "All" else outliers[outliers["product"] == o_prod]

        table = o_show.copy()
        table["period"] = table["period"].astype(str)
        table = table.sort_values("period", ascending=False)
        st.dataframe(
            table[["product", "period", "exporter", "price", "pure_qty",
                  "peer_median", "fence_low", "fence_high"]]
            .style.format({"price": "${:,.2f}", "pure_qty": "{:,.0f}",
                           "peer_median": "${:,.2f}", "fence_low": "${:,.2f}",
                           "fence_high": "${:,.2f}"}),
            width="stretch", height=380, hide_index=True,
            column_config={
                "peer_median": st.column_config.NumberColumn(
                    "peer_median", help="The median price for that "
                    "product-period, for reference — medians are not "
                    "affected by outliers the way an average is."),
                "fence_low": st.column_config.NumberColumn(
                    "fence_low", help="Any price below this was excluded."),
                "fence_high": st.column_config.NumberColumn(
                    "fence_high", help="Any price above this was excluded."),
            })
        st.caption(
            "If a price here is genuine (not a data error), consider it "
            "separately — it will not appear on Peer Statistics, but it "
            "still counts fully in Discount %, Value Forgone and Worst Traders."
        )
        download_button("Outliers Excluded", {"Outliers": table},
                        "RMB-3T_PeerOutliers", source="Peer Benchmark",
                        filters=fdesc, key="dl_out")

# ================================================================ discounts ====
with tabs[3]:
    section(f"Discounts vs peers — {label}")
    f1, f2 = st.columns([1, 2])
    prods = sorted(disc["product"].dropna().unique())
    prod = f1.selectbox("Product", prods, key="t3i_dc_prod")
    s = disc[disc["product"] == prod].copy()
    s["period"] = s["period"].astype(str)

    exporters = sorted(s["exporter"].unique())
    default = (
        s.groupby("exporter")["forgone_vs_avg"].sum()
        .sort_values(ascending=False).head(3).index.tolist()
    )
    chosen = f2.multiselect("Exporters to plot", exporters, default=default,
                            key="t3i_dc_exp")

    chart = s.groupby("period")[["peer_avg", "peer_max"]].first().rename(
        columns={"peer_avg": "Market average", "peer_max": "Market maximum"})
    for e in chosen:
        chart[e] = s[s["exporter"] == e].set_index("period")["price"]
    st.line_chart(chart)

    st.dataframe(
        s[["period", "exporter", "price", "peer_avg", "peer_avg_excl_self",
           "peer_max", "disc_vs_avg_pct", "disc_vs_max_pct", "pure_qty",
           "thin_market"]]
        .sort_values(["period", "disc_vs_avg_pct"], ascending=[False, False])
        .style.format({"price": "${:,.2f}", "peer_avg": "${:,.2f}",
                       "peer_avg_excl_self": "${:,.2f}", "peer_max": "${:,.2f}",
                       "disc_vs_avg_pct": "{:.1%}",
                       "disc_vs_max_pct": "{:.1%}", "pure_qty": "{:,.0f}"}),
        width="stretch", height=400, hide_index=True,
        column_config={
            "peer_avg": st.column_config.NumberColumn("peer_avg", help=PEER_AVERAGE),
            "peer_avg_excl_self": st.column_config.NumberColumn(
                "peer_avg_excl_self", help=PEER_AVG_EXCL_SELF),
            "peer_max": st.column_config.NumberColumn("peer_max", help=PEER_MAX),
            "pure_qty": st.column_config.NumberColumn("pure_qty", help=PURE_QUANTITY),
            "thin_market": st.column_config.CheckboxColumn(
                "thin_market", help=THIN_MARKET),
        })
    download_button("Discounts", {"Discounts": s},
                    f"RMB-3T_Discounts_{prod}", source="Peer Benchmark",
                    filters=fdesc, key="dl_dc")

# =========================================================== value forgone ====
with tabs[4]:
    section(f"Value forgone — {label}")
    st.caption(
        "Value forgone = (benchmark − exporter price) × that exporter's contained "
        "quantity, floored at zero. Against the average it measures trading below "
        "the national norm; against the maximum it measures the full theoretical "
        "opportunity, which is a stretch target rather than a realistic expectation."
    )

    by_min = disc.groupby("mineral")[["forgone_vs_avg", "forgone_vs_max"]].sum()
    c1, c2 = st.columns(2)
    c1.metric("Total vs market average", fmt_money_m(by_min["forgone_vs_avg"].sum()),
              help=VALUE_FORGONE)
    c2.metric("Total vs market maximum", fmt_money_m(by_min["forgone_vs_max"].sum()),
              help=PEER_MAX)

    st.dataframe(by_min.style.format("${:,.0f}"), width="stretch")

    _warn = coverage.coverage_warning(d, filters.get("years"))
    if _warn:
        warn_banner(_warn)

    section("By year and mineral")
    piv = disc.pivot_table(index="year", columns="mineral",
                           values="forgone_vs_avg", aggfunc="sum").fillna(0)
    piv["Total"] = piv.sum(axis=1)
    st.dataframe(piv.style.format("${:,.0f}"), width="stretch")
    st.bar_chart(piv[[c for c in piv.columns if c != "Total"]])

    section("Share of value forgone by mineral")
    base = piv[[c for c in piv.columns if c != "Total"]]
    tot = base.sum(axis=1).replace(0, pd.NA)
    share = (base.div(tot, axis=0) * 100).fillna(0)
    st.dataframe(share.style.format("{:.1f}%"), width="stretch")
    st.caption("Which commodity is leaking the most value, year by year.")

    download_button("Value Forgone",
                    {"By mineral": by_min.reset_index(),
                     "By year": piv.reset_index(),
                     "Share": share.reset_index()},
                    "RMB-3T_ValueForgone", source="Peer Benchmark",
                    filters=fdesc, key="dl_vf")
