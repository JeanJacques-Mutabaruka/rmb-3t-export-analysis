"""4 · International Benchmark — Rwanda prices vs world references."""
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
from app.formatting import fmt_money_m  # noqa: E402
from app.style import info_banner, section, warn_banner  # noqa: E402
from engine import benchmarks_intl as bi, losses  # noqa: E402

state.init_state()
filters = state.page_setup("🌍 International Benchmark")

if not state.require_data():
    st.stop()

d = state.apply_filters(state.active(), filters)
if d.empty:
    info_banner("No rows match the current filters.")
    st.stop()

with st.expander("⚠️ Read this before quoting any number from this page", expanded=False):
    st.markdown(
        """
**Tin is solid. Tantalum and tungsten are not equally solid.**

* **Cassiterite → LME tin**, monthly cash-settlement averages. Exchange-traded,
  continuous, reliable for every month.
* **Coltan → tantalite concentrate.** No exchange exists. Real USGS/CRU annual
  averages 2019–2024, a single Nov-2025 anchor, and an Argus spot point for
  Feb-2026. **March-2026 onward is held flat and is almost certainly too low** —
  Rwanda's own realised price rose above it, which shows up as an implausible
  negative loss. Override those months if you can source better data.
* **Wolframite → tungsten concentrate.** Real USGS annual averages 2019–2025
  (in-warehouse Rotterdam) plus two Fastmarkets 2026 anchor points. The monthly
  path between anchors is not known.

Annual benchmarks applied to monthly data understate within-year swings. The
floored view treats months where Rwanda beat the benchmark as zero loss rather
than a gain — the conservative, defensible choice for reporting.
        """
    )

prices = st.session_state["t3i_prices"]
rw = losses.rwanda_monthly(d)
gap = losses.attach(rw, prices)

tabs = st.tabs(["📈 Price Gap", "💸 Losses", "⚖️ Loss Share by Mineral",
                "🛠️ Benchmark Editor"])
fdesc = f"years={filters.get('years')}, minerals={filters.get('minerals')}"

# =============================================================== price gap ====
with tabs[0]:
    section("Rwanda realised price vs international benchmark")
    minerals = sorted(gap["mineral"].dropna().unique())
    if not minerals:
        info_banner("No priced rows available.")
        st.stop()
    m = st.selectbox("Mineral", minerals, key="t3i_gap_min")
    st.caption(f"Basis: {bi.BASIS_LABEL.get(m, '')}")

    sub = gap[gap["mineral"] == m].copy()
    sub["period"] = sub["period"].astype(str)
    st.line_chart(sub.set_index("period")[["rwanda_price", "benchmark"]])

    assumed = sub[sub["basis"] == bi.ASSUMPTION]
    if len(assumed):
        warn_banner(
            f"{len(assumed)} month(s) on this chart use an <b>ASSUMPTION</b> "
            "benchmark with no underlying published figure. Check the Basis "
            "column below before quoting."
        )

    st.dataframe(
        sub[["period", "rwanda_price", "benchmark", "basis", "gap", "gap_pct",
             "pure_qty", "loss_floored", "note"]]
        .style.format({"rwanda_price": "${:,.2f}", "benchmark": "${:,.2f}",
                       "gap": "${:,.2f}", "gap_pct": "{:.1%}",
                       "pure_qty": "{:,.0f}", "loss_floored": "${:,.0f}"}),
        width="stretch", height=420, hide_index=True)
    download_button("Price Gap Detail", {"Gap": sub},
                    f"RMB-3T_PriceGap_{m}", source="International Benchmark",
                    filters=fdesc, key="dl_gapdet")

# ================================================================== losses ====
with tabs[1]:
    floored = st.toggle(
        "Floor negative gaps at zero", value=True, key="t3i_floor",
        help="Off shows the signed view, which exposes stale benchmarks.")
    ann = losses.annual(gap, floored=floored)

    if ann.empty:
        info_banner("No losses to report.")
    else:
        c1, c2 = st.columns(2)
        c1.metric("Estimated cumulative gap", fmt_money_m(ann["Total"].sum()))
        c2.metric("Period", f"{int(ann.index.min())}–{int(ann.index.max())}")

        section("Estimated loss by year and mineral")
        st.dataframe(ann.style.format("${:,.0f}"), width="stretch")
        st.bar_chart(ann[[c for c in ann.columns
                          if c not in ("Total", "Cumulative")]])

        if not floored:
            warn_banner(
                "Signed view. Large negative figures usually mean the benchmark "
                "for those months is stale or too low — not that Rwanda genuinely "
                "outsold the international market."
            )
        download_button("Annual Losses", {"Losses": ann.reset_index()},
                        "RMB-3T_IntlLosses", source="International Benchmark",
                        filters=fdesc, key="dl_loss")

# ============================================================== loss share ====
with tabs[2]:
    section("Share of total loss by mineral — where to focus")
    share = losses.loss_share(gap)
    if share.empty:
        info_banner("No losses to report.")
    else:
        st.dataframe(share.style.format("{:.1f}%"), width="stretch")
        st.bar_chart(share)
        st.caption(
            "Read this to prioritise control and regulation: the mineral with "
            "the largest share is where the most value is escaping."
        )
        download_button("Loss Share", {"Share": share.reset_index()},
                        "RMB-3T_LossShare", source="International Benchmark",
                        filters=fdesc, key="dl_share")

# ======================================================= benchmark editor ====
with tabs[3]:
    section("Override a benchmark price")
    st.caption(
        "Overrides are saved to the rules file and tagged USER OVERRIDE. "
        "Download intl_prices.json from Data Management → Save & Commit to keep them."
    )
    c1, c2, c3, c4 = st.columns(4)
    om = c1.selectbox("Mineral", ["Cassiterite", "Coltan", "Wolframite"],
                      key="t3i_ov_m")
    oy = c2.number_input("Year", 2019, 2035, 2026, key="t3i_ov_y")
    omo = c3.number_input("Month", 1, 12, 6, key="t3i_ov_mo")
    cur, basis, _ = bi.lookup(prices, om, int(oy), int(omo))
    ov = c4.number_input("Benchmark $/kg", 0.0, 1_000_000.0,
                         float(cur) if pd.notna(cur) else 0.0, key="t3i_ov_v")
    st.caption(f"Current: ${cur:,.2f} ({basis})" if pd.notna(cur) else "No current value")

    a, b = st.columns(2)
    if a.button("Apply override", type="primary", width="stretch"):
        st.session_state["t3i_prices"] = bi.set_override(
            prices, om, int(oy), int(omo), float(ov))
        state.mark_dirty()
        st.rerun()
    if b.button("Reset all to published defaults", width="stretch"):
        st.session_state["t3i_prices"] = bi.default_price_file()
        state.mark_dirty()
        st.rerun()

    section("Current benchmark series")
    view_m = st.selectbox("Show series for", ["Cassiterite", "Coltan", "Wolframite"],
                          key="t3i_ov_view")
    series = pd.DataFrame([
        {"Month": k, "Price ($/kg)": v.get("price"), "Basis": v.get("basis"),
         "Note": v.get("note", "")}
        for k, v in sorted(prices.get(view_m, {}).items())
    ])
    if not series.empty:
        st.dataframe(series.style.format({"Price ($/kg)": "${:,.2f}"}),
                     width="stretch", height=360, hide_index=True)
        download_button("Benchmark Series", {"Series": series},
                        f"RMB-3T_Benchmarks_{view_m}",
                        source="Benchmark Editor", key="dl_bench")
