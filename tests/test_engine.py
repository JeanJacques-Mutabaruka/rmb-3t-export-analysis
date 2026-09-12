"""Regression tests for the calculation engine.

Expected values come from analysis already validated against the real
2019-2026 MCIS extract (spec §10). Run with:  pytest -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import (  # noqa: E402
    benchmarks_intl as bi, benchmarks_peer as bp, exclusions, harmonise,
    history, ingest, losses,
)
from engine.schema import FileRejected  # noqa: E402


# ------------------------------------------------------------------ fixtures --

def _row(**kw):
    base = {
        "Mineral": "Cassiterite", "Product": "Tin concentrate",
        "Shipment Number": "SN/RW/0000001", "Issuance Date": "1/15/2025 10:00:00 AM",
        "Exporter": "Alpha Mining Ltd", "Certificate Number": "RW000001",
        "Grade": 60.0, "Quantity(Kg)": 10_000.0, "Buyer": "Buyer One",
        "Destination": "China", "Export Tax($)": 1_000.0,
        "Shipment Value($)": 100_000.0, "Traceability Fees": 100.0,
    }
    base.update(kw)
    return base


@pytest.fixture
def simple_raw():
    return pd.DataFrame([
        _row(),
        _row(**{"Shipment Number": "SN/RW/0000002", "Certificate Number": "RW000002",
                "Exporter": "Beta Mining Ltd", "Shipment Value($)": 80_000.0}),
        _row(**{"Shipment Number": "SN/RW/0000003", "Certificate Number": "RW000003",
                "Exporter": "Gamma Mining Ltd", "Shipment Value($)": 120_000.0}),
        {**_row(), "Mineral": "Total", "Shipment Number": "", "Certificate Number": ""},
    ])


# ------------------------------------------------------------------ schema ----

def test_rejects_wrong_extension():
    with pytest.raises(FileRejected, match="Unsupported file type"):
        ingest.read_workbook(b"x", "notes.txt")


def test_rejects_missing_columns():
    bad = pd.DataFrame({"Mineral": ["Coltan"], "Product": ["x"]})
    with pytest.raises(FileRejected, match="missing columns"):
        ingest.normalise(bad, "bad.xlsx", "B1")


def test_rejects_empty_file():
    cols = list(_row().keys())
    with pytest.raises(FileRejected, match="no data rows"):
        ingest.normalise(pd.DataFrame(columns=cols), "empty.xlsx", "B1")


# ------------------------------------------------------------------ ingest ----

def test_subtotals_separated(simple_raw):
    recs, subs = ingest.normalise(simple_raw, "f.xlsx", "B1")
    assert len(recs) == 3
    assert len(subs) == 1


def test_derived_columns(simple_raw):
    recs, _ = ingest.normalise(simple_raw, "f.xlsx", "B1")
    r = recs.iloc[0]
    assert r["pure_quantity_kg"] == pytest.approx(6_000.0)       # 10000 * 60 / 100
    assert r["unit_value_usd_kg"] == pytest.approx(100_000 / 6_000)
    assert r["year"] == 2025
    assert r["year_month"] == "2025-01"
    assert r["quarter"] == "2025Q1"
    assert r["record_key"] == "SN/RW/0000001·RW000001"


# ----------------------------------------------------------------- history ----

def test_record_key_unique_on_real_key_pair(simple_raw):
    recs, _ = ingest.normalise(simple_raw, "f.xlsx", "B1")
    assert recs["record_key"].is_unique


def test_classify_new_exact_and_conflict(simple_raw):
    recs, _ = ingest.normalise(simple_raw, "f.xlsx", "B1")
    incoming = recs.copy()
    incoming.loc[1, "shipment_value_usd"] = 999.0          # conflict
    new, exact, conflicts = history.classify(recs, incoming)
    assert len(new) == 0
    assert len(exact) == 2
    assert len(conflicts) == 1
    assert conflicts[0]["diffs"][0]["field"] == "shipment_value_usd"


def test_resolve_replace_and_keep_both(simple_raw):
    recs, _ = ingest.normalise(simple_raw, "f.xlsx", "B1")
    incoming = recs.copy()
    incoming.loc[1, "shipment_value_usd"] = 999.0
    _, _, conflicts = history.classify(recs, incoming)
    key = conflicts[0]["record_key"]

    replaced = history.resolve(recs, conflicts, {key: "replace"})
    assert replaced.loc[replaced["record_key"] == key,
                        "shipment_value_usd"].iloc[0] == 999.0

    both = history.resolve(recs, conflicts, {key: "keep_both"})
    assert len(both) == len(recs) + 1


# -------------------------------------------------------------- harmonise ----

def test_proposal_merges_spelling_variants():
    names = pd.Series(["Traxys Europe S.A"] * 5 +
                      ["TRAXYS EUROPE S.A."] * 2 +
                      ["Wholly Different Corp"])
    props = harmonise.propose(names, harmonise.empty_rules(), "buyer")
    assert len(props) == 1
    assert props[0]["canonical"] == "Traxys Europe S.A"
    assert "TRAXYS EUROPE S.A." in props[0]["variants"]


def test_never_merge_keeps_distinct_companies_apart():
    rules = harmonise.add_never_merge(harmonise.empty_rules(), ["KALON", "HAIPU"])
    names = pd.Series(["Kalon Resources Limited"] * 4 +
                      ["Haipu Resources Limited"] * 3)
    props = harmonise.propose(names, rules, "buyer")
    for p in props:
        joined = " ".join([p["canonical"], *p["variants"]]).upper()
        assert not ("KALON" in joined and "HAIPU" in joined)


def test_apply_rules_rewrites_names(simple_raw):
    recs, _ = ingest.normalise(simple_raw, "f.xlsx", "B1")
    rules = harmonise.add_rule(harmonise.empty_rules(), "exporter",
                               "Alpha Mining Ltd", ["Beta Mining Ltd"])
    out = harmonise.apply_rules(recs, rules)
    assert (out["exporter"] == "Alpha Mining Ltd").sum() == 2
    assert (out["exporter_raw"] == "Beta Mining Ltd").sum() == 1   # raw preserved


# -------------------------------------------------------------- exclusions ----

def test_category_columns_and_master_flag(simple_raw):
    recs, _ = ingest.normalise(simple_raw, "f.xlsx", "B1")
    rules = exclusions.add_condition_rule(
        exclusions.empty_rules(), "Test record",
        [{"field": "exporter", "op": "==", "value": "Beta Mining Ltd"}], "test")
    out = exclusions.apply_rules(recs, rules)
    assert out["excl_test_record"].tolist().count("YES") == 1
    assert (out["excluded"] == "YES").sum() == 1


def test_two_conditions_are_anded(simple_raw):
    recs, _ = ingest.normalise(simple_raw, "f.xlsx", "B1")
    rules = exclusions.add_condition_rule(
        exclusions.empty_rules(), "Valuation error",
        [{"field": "shipment_no", "op": "==", "value": "SN/RW/0000001"},
         {"field": "shipment_value_usd", "op": ">", "value": 1e9}], "twin")
    out = exclusions.apply_rules(recs, rules)
    assert (out["excluded"] == "YES").sum() == 0      # value condition not met


def test_honouring_subset_of_categories(simple_raw):
    recs, _ = ingest.normalise(simple_raw, "f.xlsx", "B1")
    rules = exclusions.add_condition_rule(
        exclusions.empty_rules(), "Specialty exporter",
        [{"field": "exporter", "op": "==", "value": "Beta Mining Ltd"}], "")
    out = exclusions.apply_rules(recs, rules)
    assert exclusions.active_mask(out, rules).sum() == 2
    assert exclusions.active_mask(out, rules, honour=[]).sum() == 3


# ------------------------------------------------------------ peer benchmark --

def test_peer_stats_avg_max_min():
    raw = pd.DataFrame([
        _row(**{"Shipment Number": "A", "Certificate Number": "C1",
                "Exporter": "A Ltd", "Shipment Value($)": 60_000.0}),
        _row(**{"Shipment Number": "B", "Certificate Number": "C2",
                "Exporter": "B Ltd", "Shipment Value($)": 120_000.0}),
    ])
    recs, _ = ingest.normalise(raw, "f.xlsx", "B1")
    ep = bp.exporter_periods(recs, "month")
    stats = bp.peer_stats(ep, "month", 1)
    row = stats.iloc[0]
    # both 6,000 kg contained: prices are 10 and 20 -> vwa 15, max 20, min 10
    assert row["peer_avg"] == pytest.approx(15.0)
    assert row["peer_max"] == pytest.approx(20.0)
    assert row["peer_min"] == pytest.approx(10.0)
    assert row["peer_range"] == pytest.approx(10.0)


def test_forgone_uses_contained_quantity():
    raw = pd.DataFrame([
        _row(**{"Shipment Number": "A", "Certificate Number": "C1",
                "Exporter": "A Ltd", "Shipment Value($)": 60_000.0}),
        _row(**{"Shipment Number": "B", "Certificate Number": "C2",
                "Exporter": "B Ltd", "Shipment Value($)": 120_000.0}),
    ])
    recs, _ = ingest.normalise(raw, "f.xlsx", "B1")
    ep = bp.exporter_periods(recs, "month")
    disc = bp.discounts(ep, bp.peer_stats(ep, "month", 1))
    a = disc[disc["exporter"] == "A Ltd"].iloc[0]
    assert a["forgone_vs_avg"] == pytest.approx((15.0 - 10.0) * 6_000)
    assert a["disc_vs_avg_pct"] == pytest.approx((15.0 - 10.0) / 15.0)
    b = disc[disc["exporter"] == "B Ltd"].iloc[0]
    assert b["forgone_vs_avg"] == pytest.approx(0.0)     # floored at zero


def test_thin_market_flagged():
    raw = pd.DataFrame([_row()])
    recs, _ = ingest.normalise(raw, "f.xlsx", "B1")
    ep = bp.exporter_periods(recs, "month")
    stats = bp.peer_stats(ep, "month", 1)
    assert bool(stats.iloc[0]["thin_market"]) is True


def test_dominant_mineral_mapping_survives_a_mislabelled_row():
    rows = [
        _row(**{"Shipment Number": f"W{i}", "Certificate Number": f"CW{i}",
                "Mineral": "Wolframite", "Product": "Tungsten concentrate",
                "Exporter": f"E{i} Ltd"})
        for i in range(5)
    ]
    rows.append(_row(**{"Shipment Number": "BAD", "Certificate Number": "CBAD",
                        "Mineral": "Cassiterite", "Product": "Tungsten concentrate",
                        "Exporter": "Odd Ltd"}))
    recs, _ = ingest.normalise(pd.DataFrame(rows), "f.xlsx", "B1")
    ep = bp.exporter_periods(recs, "month")
    assert set(ep["mineral"].unique()) == {"Wolframite"}


def test_product_mineral_mismatch_is_suggested():
    rows = [
        _row(**{"Shipment Number": f"W{i}", "Certificate Number": f"CW{i}",
                "Mineral": "Wolframite", "Product": "Tungsten concentrate"})
        for i in range(5)
    ]
    rows.append(_row(**{"Shipment Number": "BAD", "Certificate Number": "CBAD",
                        "Mineral": "Cassiterite", "Product": "Tungsten concentrate"}))
    recs, _ = ingest.normalise(pd.DataFrame(rows), "f.xlsx", "B1")
    sug = exclusions.suggest(recs)
    assert any("mismatch" in r for r in sug["reason"])


# --------------------------------------------------- international benchmark --

def test_tin_series_is_real_and_continuous():
    prices = bi.default_price_file()
    price, basis, _ = bi.lookup(prices, "Cassiterite", 2024, 6)
    assert basis == bi.REAL
    assert price == pytest.approx(32.22875, rel=1e-3)


def test_tantalum_2026_tail_is_flagged_as_assumption():
    prices = bi.default_price_file()
    _, basis, note = bi.lookup(prices, "Coltan", 2026, 7)
    assert basis == bi.ASSUMPTION
    assert "UNDERESTIMATE" in note


def test_override_is_tagged():
    prices = bi.set_override(bi.default_price_file(), "Coltan", 2026, 7, 450.0)
    price, basis, _ = bi.lookup(prices, "Coltan", 2026, 7)
    assert price == 450.0
    assert basis == bi.OVERRIDE


def test_loss_is_floored_but_signed_view_keeps_sign():
    raw = pd.DataFrame([_row(**{"Shipment Value($)": 10_000_000.0})])
    recs, _ = ingest.normalise(raw, "f.xlsx", "B1")
    gap = losses.attach(losses.rwanda_monthly(recs), bi.default_price_file())
    assert gap.iloc[0]["loss_signed"] < 0
    assert gap.iloc[0]["loss_floored"] == 0


# ------------------------------------------------------- github sync (V1-0b) --

def test_repo_target_configuration_check():
    from engine import github_sync
    assert not github_sync.RepoTarget("", "", "main", "").is_configured()
    assert not github_sync.RepoTarget("me", "repo", "main", "").is_configured()
    assert github_sync.RepoTarget("me", "repo", "main", "tok").is_configured()
    assert github_sync.RepoTarget("me", "repo").slug == "me/repo"


def test_unconfigured_target_refuses_to_push():
    from engine import github_sync
    t = github_sync.RepoTarget("", "", "main", "")
    with pytest.raises(github_sync.GitHubError, match="not configured"):
        github_sync.put_file(t, "data/x.json", b"{}", "msg")
    with pytest.raises(github_sync.GitHubError, match="not configured"):
        github_sync.check_access(t)


# ---------------------------------------------------------- reporting (V1-0b) --

def _report_ctx():
    from engine import reporting
    return {
        "subtitle": "Test report", "period": "2019-2026", "filters": "none",
        "metrics": {"Shipments": "3,721", "Export value": "$1,874.0M"},
        "caveats": reporting.standard_caveats(),
    }


def _report_tables():
    return {"Value by year": pd.DataFrame(
        {"year": [2024, 2025, 2026],
         "Cassiterite": [9.6e7, 1.4e8, 1.6e8],
         "Coltan": [9.7e7, 1.4e8, 2.9e8]})}


def test_docx_report_builds():
    from engine import reporting
    if not reporting.DOCX_AVAILABLE:
        pytest.skip("python-docx not installed")
    data = reporting.build_docx(_report_ctx(), _report_tables())
    assert data[:2] == b"PK"          # docx is a zip
    assert len(data) > 5_000


def test_pdf_report_builds():
    from engine import reporting
    if not reporting.PDF_AVAILABLE:
        pytest.skip("reportlab not installed")
    data = reporting.build_pdf(_report_ctx(), _report_tables())
    assert data[:4] == b"%PDF"
    assert len(data) > 1_000


def test_years_are_not_comma_grouped():
    from engine.reporting import _fmt_cell
    assert _fmt_cell(2024, "year") == "2024"
    assert _fmt_cell(2024.0, "Year") == "2024"
    assert _fmt_cell(1_250_000.0, "value") == "1,250,000"
    assert _fmt_cell(12.5, "price") == "12.50"


def test_pdf_text_is_latin1_safe():
    from engine.reporting import _ascii
    assert _ascii("Ta\u2082O\u2085 \u2014 gap") == "Ta2O5 - gap"
    assert all(ord(c) < 256 for c in _ascii("\u4e2d\u6587 \u2192 x"))


def test_standard_caveats_cover_the_key_warnings():
    from engine import reporting
    joined = " ".join(reporting.standard_caveats()).lower()
    for phrase in ("contained metal", "assumption", "not by itself evidence",
                   "floored at zero", "same product"):
        assert phrase in joined


# ------------------------------------------------ scorecard columns (V1-0c) --

def _two_exporter_year():
    """A Ltd ships a large cheap lot in Jan and a small dear lot in Feb."""
    rows = [
        # January: A cheap on big volume, B sets a high bar
        _row(**{"Shipment Number": "A1", "Certificate Number": "CA1",
                "Exporter": "A Ltd", "Issuance Date": "1/10/2025 10:00:00 AM",
                "Quantity(Kg)": 20_000.0, "Grade": 50.0,
                "Shipment Value($)": 100_000.0}),          # 10,000 kg @ $10
        _row(**{"Shipment Number": "B1", "Certificate Number": "CB1",
                "Exporter": "B Ltd", "Issuance Date": "1/10/2025 10:00:00 AM",
                "Quantity(Kg)": 20_000.0, "Grade": 50.0,
                "Shipment Value($)": 200_000.0}),          # 10,000 kg @ $20
        # February: A dear on small volume, B cheap
        _row(**{"Shipment Number": "A2", "Certificate Number": "CA2",
                "Exporter": "A Ltd", "Issuance Date": "2/10/2025 10:00:00 AM",
                "Quantity(Kg)": 2_000.0, "Grade": 50.0,
                "Shipment Value($)": 30_000.0}),           # 1,000 kg @ $30
        _row(**{"Shipment Number": "B2", "Certificate Number": "CB2",
                "Exporter": "B Ltd", "Issuance Date": "2/10/2025 10:00:00 AM",
                "Quantity(Kg)": 2_000.0, "Grade": 50.0,
                "Shipment Value($)": 20_000.0}),           # 1,000 kg @ $20
    ]
    recs, _ = ingest.normalise(pd.DataFrame(rows), "f.xlsx", "B1")
    ep = bp.exporter_periods(recs, "month")
    return bp.scorecard(bp.discounts(ep, bp.peer_stats(ep, "month", 1)))


def test_scorecard_reports_price_and_discount_ranges():
    sc = _two_exporter_year()
    a = sc[sc["exporter"] == "A Ltd"].iloc[0]
    assert a["price_min"] == pytest.approx(10.0)
    assert a["price_max"] == pytest.approx(30.0)
    # Jan: (15-10)/15 = +33.3% discount; Feb: (25-30)/25 = -20% (beat the market)
    assert a["disc_max"] == pytest.approx(1 / 3, rel=1e-3)
    assert a["disc_min"] == pytest.approx(-0.20, rel=1e-3)


def test_pct_qty_below_avg_is_volume_weighted_not_period_counted():
    sc = _two_exporter_year()
    a = sc[sc["exporter"] == "A Ltd"].iloc[0]
    # below average in 1 of 2 periods...
    assert a["consistency"] == pytest.approx(0.5)
    # ...but that period carried 10,000 of 11,000 kg
    assert a["pct_qty_below_avg"] == pytest.approx(10_000 / 11_000, rel=1e-3)
    assert a["pct_qty_below_avg"] > a["consistency"]


def test_negative_discount_can_still_carry_value_forgone():
    """The case the UI has to explain: beat the market overall, yet forgone > 0."""
    sc = _two_exporter_year()
    b = sc[sc["exporter"] == "B Ltd"].iloc[0]
    # B's weighted price ($200k+$20k)/(11,000kg) = $20.00 vs peer avg $19.55
    assert b["disc_vs_avg_pct"] < 0          # beat the average across the year
    assert b["forgone_vs_avg"] > 0           # but lost ground in February
    # February only: (25-20) * 1,000 = 5,000
    assert b["forgone_vs_avg"] == pytest.approx(5_000.0, rel=1e-6)


def test_qty_below_avg_never_exceeds_total_quantity():
    sc = _two_exporter_year()
    assert (sc["qty_below_avg"] <= sc["pure_qty"] + 1e-9).all()
    assert (sc["pct_qty_below_avg"].between(0, 1)).all()
