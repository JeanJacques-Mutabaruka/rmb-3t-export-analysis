# CHANGES — V1-0a

**Date:** 12 September 2026
**Spec:** `RMB-3T_Functional_Spec__V2026-09-12_1600.md` (V0-2)

First delivery. Builds the specification in full.

---

## Decisions taken on the seven open spec items

You asked me to apply my proposed choice where you had not answered. For the
record, these are the choices made — all are reversible:

| # | Item | Decision |
|---|---|---|
| 1 | Regulation N°2 scope | **Out of scope.** No pricing mechanism or Annex I invoicing. |
| 2 | Multi-file processing order | **Chronological** — ascending by each file's earliest issuance date, ties broken by filename. |
| 3 | Exclusion column granularity | **One column per category**, not per rule. Seven starter categories give seven columns. |
| 4 | Per-category analysis toggles | **Implemented.** Sidebar checkboxes let you untick a category so those rows return to the analyses on that page. |
| 5 | Window definitions | Current month, current quarter, moving N months (default 3), moving N quarters (default 2) — as specified. |
| 6 | Minimum as a loss basis | **Statistic only.** Min appears in peer statistics and range views and feeds anomaly detection; it is not offered as a loss benchmark. |
| 7 | Page structure | **Seven pages.** Harmonisation and Exclusions merged into *2 · Rules & Data Quality* with two-level tabs. |

---

## Delivered

### Features
- Multi-file upload with independent per-file validation; a rejected file never blocks a valid one
- Five rejection checks with specific messages (extension, readability, missing columns, no rows, no certificate numbers)
- Duplicate detection on `shipment_no` + `certificate_no`, classified New / Exact duplicate / Conflicting duplicate
- Conflicting duplicates resolved per record with a field-by-field diff — keep existing, replace, or keep both; bulk actions available; nothing auto-overwrites
- Ingestion audit trail per batch
- Name harmonisation for exporter, buyer and destination: threshold-driven proposals, approve / edit / reject, never-merge list, rules saved to JSON
- Rule-change preview showing rows affected and the concentration figures that move, before applying
- User-defined exclusion categories, each becoming its own YES/blank column, plus a master `excluded` flag
- Condition rules (one or two ANDed conditions) and record rules
- Anomaly suggester with six detectors; proposes, never excludes
- Excluded-rows tab with eight filter dimensions, free-text search, value and quantity range sliders, and inline note editing
- International benchmark with provenance tags and a per-month override editor
- Peer benchmark with average, maximum, minimum and range across four window bases
- Discounts vs peer average and maximum, value forgone weighted by contained quantity, consistency measure
- Exporter ranking, worst traders per commodity and year, exporter detail, exporter comparison
- Summary report, export centre, download button on every table section
- Demo data generator seeded with the same kinds of data problems the real extracts contain

### Design
- `style.py` built from the reference `style_template.py`, with the confirmed overrides: RMB green `#1A5C38` → gold `#C8960A` gradient, Cambria headings, comma thousands separators
- Both Streamlit tab-markup implementations covered in the CSS
- `.streamlit/config.toml` matched to the theme
- Session keys prefixed `t3i_`
- Excel exports: frozen header, bold headers, auto-width, `_INFO` provenance sheet, `__V{date}_{time}` filename stamps

### Engineering
- Calculation engine (`engine/`) contains no Streamlit imports and is directly testable
- 23 pytest regression tests, all passing
- `run.sh` / `run.bat` single-command launchers

---

## Two issues found and fixed during the build

**Phantom $3.3 billion loss.** The earlier prototype keyed exclusions on shipment
number alone. Two corrupted records are *twins* — the same shipment number
carries one good row and one corrupted row — so excluding by shipment number
either kept both or dropped both. Exclusions are now evaluated at row level with
optional field conditions, so a rule can isolate exactly the corrupted twin.
Regression tests cover both twins.

**Wolframite disappearing from the peer benchmark.** The product → mineral
mapping used the first occurrence of each product. The source data contains
single-row mineral/product mismatches — one `Tungsten concentrate` row is
labelled `Cassiterite` — and first-occurrence mapping silently mislabelled the
entire Wolframite peer group. Mapping now uses the value-dominant label, and a
new detector surfaces the mismatched rows for review. Regression tests cover both.

---

## Known deviation from the design rules

**R15 (DataTables Responsive for tables over 4 columns)** is not implemented.
The rule was written for the static HTML site. Embedding DataTables in Streamlit
requires `components.html`, which loses native sorting, column configuration and
theme integration. `st.dataframe` provides equivalent responsive behaviour
natively and is what `RMB_UI_Design_System.md` §3 prescribes. Flagged rather
than silently skipped — say if you want the HTML-embedded version anyway.

---

## Operational note

The dataset ships **empty**. No real export data is committed. This is
deliberate: the repository may end up public, and the data is commercially
sensitive. Upload your extract on first use, or press **LOAD DEMO DATA**.

Persistence is download-and-commit, as agreed. Nothing is stored server-side.
`DEPLOYMENT.md` Part 3 covers the cycle and the alternatives if it becomes
tedious.

---

## Not yet built

- GitHub API write-back (would remove the manual commit step)
- Word/PDF report export — only Excel at present
- Authentication or read-only roles

---

## Files

```
app/            Home.py, style.py, state.py, formatting.py, downloads.py,
                demo_data.py, pages/1-7
engine/         schema, ingest, harmonise, exclusions, history,
                benchmarks_intl, benchmarks_peer, losses
data/           dataset (empty), rules_harmonisation, rules_exclusions,
                intl_prices
tests/          test_engine.py — 23 tests
                README.md, DEPLOYMENT.md, run.sh, run.bat,
                requirements.txt, .streamlit/config.toml
```
