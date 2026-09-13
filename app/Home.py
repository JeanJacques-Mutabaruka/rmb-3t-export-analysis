"""RMB 3T Export Intelligence — entry point."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="RMB 3T Export Intelligence", page_icon="⛏️",
                   layout="wide")

from app import demo_data, state  # noqa: E402
from app.formatting import fmt, fmt_money_m  # noqa: E402
from app.style import info_banner, inject_css, section, warn_banner  # noqa: E402
from engine import ingest  # noqa: E402

inject_css()
state.init_state()

st.title("⛏️ RMB 3T Export Intelligence")
state.sidebar_controls(show_filters=False)

if st.session_state.get("t3i_dirty"):
    d = state.view()
    added = len(d) - st.session_state.get("t3i_baseline_rows", 0)
    warn_banner(
        f"<b>UNSAVED CHANGES</b> — {fmt(max(added, 0))} record(s) added this "
        "session, or rules changed. Nothing is stored on the server. Go to "
        "<b>1 · Data Management → Save &amp; Commit</b>, download the updated "
        "dataset and commit it to the repository, or these changes will be lost."
    )

if st.session_state.get("t3i_demo"):
    info_banner(
        "<b>DEMO MODE</b> — this is synthetic data for demonstration only. "
        "Every exporter, buyer and figure is invented."
    )

st.markdown(
    "Maintains a growing history of Rwanda's 3T export declarations and "
    "benchmarks them two ways: against **international market prices**, and "
    "against **the Rwandan market itself**."
)

# ------------------------------------------------------------- dataset state --
section("Dataset")

d = state.view()
if d.empty:
    info_banner(
        "No dataset loaded. Upload an MCIS extract on "
        "<b>1 · Data Management</b>, or load the demo dataset below."
    )
else:
    a = state.active()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Records", fmt(len(d)))
    c2.metric("Export value", fmt_money_m(a["shipment_value_usd"].sum()))
    c3.metric("Exporters", fmt(a["exporter"].nunique()))
    years = a["year"].dropna()
    c4.metric("Period", f"{int(years.min())}–{int(years.max())}" if len(years) else "—")

    excluded = int((d["excluded"] == "YES").sum()) if "excluded" in d.columns else 0
    st.caption(
        f"{fmt(excluded)} record(s) currently excluded by the active rules. "
        "Review them on **7 · Reports & Exports → Excluded Rows**."
    )

# ---------------------------------------------------------------- demo data --
section("Demo data")

col_a, col_b = st.columns([1, 3])
with col_a:
    if st.button("🧪 LOAD DEMO DATA", type="primary", width="stretch"):
        raw = demo_data.generate()
        records, subs = ingest.normalise(raw, "DEMO_DATA.xlsx", "DEMO")
        st.session_state["t3i_dataset"] = records
        st.session_state["t3i_subtotals"] = subs
        st.session_state["t3i_demo"] = True
        st.session_state["t3i_dirty"] = True
        state.recompute()
        st.rerun()
with col_b:
    st.caption(
        "Loads a synthetic six-year dataset with the same kinds of data problems "
        "the real extracts contain — a corrupted value twin, a misplaced grade "
        "decimal, a placeholder record, a valuation discrepancy and buyer-name "
        "spelling variants — so every workflow can be demonstrated without real data."
    )

if st.session_state.get("t3i_demo") and st.button("Clear demo data"):
    for k in ("t3i_dataset", "t3i_subtotals"):
        st.session_state[k] = st.session_state[k].iloc[0:0]
    st.session_state["t3i_demo"] = False
    st.session_state["t3i_dirty"] = False
    state.recompute()
    st.rerun()

# -------------------------------------------------------------------- pages --
section("Where to go")

left, right = st.columns(2)
with left:
    st.markdown(
        "**1 · Data Management** — upload extracts, resolve conflicting "
        "duplicates, browse the dataset, download and commit.\n\n"
        "**2 · Rules & Data Quality** — approve name harmonisation, manage "
        "exclusion categories and rules, review anomaly suggestions.\n\n"
        "**3 · Market Overview** — volumes, values, price trends, grades, "
        "buyers and destinations.\n\n"
        "**4 · International Benchmark** — Rwanda's prices vs LME, USGS and "
        "Fastmarkets references, and the value forgone."
    )
with right:
    st.markdown(
        "**5 · Peer Benchmark** — each exporter against the Rwandan market "
        "average, maximum and minimum.\n\n"
        "**6 · Exporter Scorecard** — rankings, the worst traders per commodity "
        "and year, and per-exporter detail.\n\n"
        "**7 · Reports & Exports** — summary report, excluded rows with "
        "multi-criteria filtering, and the export centre."
    )

st.divider()
st.caption(
    "Tool version V1-0f · Prices are always $/kg of contained metal, so grade "
    "differences never distort a comparison."
)
