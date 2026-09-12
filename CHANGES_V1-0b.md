# CHANGES — V1-0b

**Date:** 12 September 2026
**Supersedes:** V1-0a
**Spec:** `RMB-3T_Functional_Spec__V2026-09-12_1600.md` (V0-2)

Three additions requested after the V1-0a delivery: pre-loaded rules, GitHub
write-back, and Word/PDF report export.

---

## 1. Rules now ship pre-loaded

Every decision taken during our analysis sessions is committed in `data/`, so
nothing has to be retyped on first use.

### `rules_exclusions.json` — 6 rules across 4 categories

| Category | Rule | Effect on your 2019–2026 extract |
|---|---|---|
| Valuation error | `PMI/RW/0000082` **AND** value > $1bn | drops the corrupted $5.75bn twin, keeps the $230,158 row |
| Grade error | `AMX/RW/0000015` **AND** grade < 1% | drops the 0.2778% twin, keeps the 27.78% row |
| Test record | shipment in `222/qqqqq/2222222`, `qqqqq/2222222` | 2 rows |
| Valuation error | shipment in `RW-ETI-B003-0149`, `RW-NYA-B003-0293` | 2 rows |
| Specialty exporter | exporter in `Luna Smelter Ltd`, `POWERX Ltd` | 361 rows |
| Non-concentrate product | 12 refined/byproduct product types | 365 rows |

Total: **373 of 3,721 records excluded**, leaving 3,348 for analysis.

The two twin rules use a second ANDed condition precisely so the good twin
survives — this is the bug that produced the phantom $3.3bn loss in the
prototype.

### `rules_harmonisation.json` — 3 approved merges, 7 never-merge pairs

Approved: Ganzhou Qingxing (+2 variants), Guangdong Xinshan (+1), Ximei
Resources HK (+1). Never-merge: Kalon/Haipu/Rayson, DAER/Zeran,
Zhongma/Shengcheng, Jiaxin/Qingxing, Qiangmin/Qingxing.

Only the merges you confirmed explicitly are shipped. The remaining ~40 buyer
groupings still surface as proposals on **2 · Rules & Data Quality** for you to
approve — deliberately, since they were never individually confirmed.

---

## 2. GitHub write-back — `engine/github_sync.py`

Commits changed files straight to the repository through the GitHub Contents
API, removing the manual download-and-commit cycle.

- **New page section:** *1 · Data Management → Save & Commit → Commit directly to GitHub*
- **Test connection** button verifies the token and reports whether it actually has write permission
- Choose which files to commit; edit the commit message
- Result table shows each file's commit SHA and link
- Stdlib only (`urllib`) — **no new dependency**
- Configured through a `[github]` block in Streamlit secrets; absent secrets is normal and the section simply explains how to enable it

**Security.** The token is a write credential. It goes in
`.streamlit/secrets.toml` (now git-ignored) or the Streamlit Cloud secrets UI —
never in code. A fine-grained token scoped to the one repository with
*Contents: read and write* is sufficient; a broad classic `repo` token is not
needed.

**Limitation, stated rather than hidden:** the Contents API commits one file per
call, so committing four files makes four commits. If the third fails, the first
two are already pushed — the result table shows exactly which succeeded.

---

## 3. Word and PDF reports — `engine/reporting.py`

A narrative report for circulation, distinct from the Excel workbook for
analysis.

- **New page section:** *7 · Reports & Exports → Export Centre → Word / PDF report*
- Headline figures, value by year and mineral, estimated international losses, the 15 largest peer gaps
- **The nine standing caveats travel with every report** — contained-metal basis, benchmark provenance, floored losses, peer-comparison limits, thin periods. A figure should never leave this tool without them.
- Word: python-docx, Cambria headings in brand green
- PDF: reportlab, landscape A4, brand-green table headers
- Both libraries are optional — if either is missing the button is replaced by a note instead of crashing

New dependencies: `python-docx>=1.1`, `reportlab>=4.0`.

---

## Defects found and fixed while building this

**Years rendered as "2,024".** The report cell formatter comma-grouped every
integer. Now column-aware, and any integer in 1900–2200 is left ungrouped.

**PDF table headers were invisible.** Dark grey text on the dark green header
band — reportlab `Paragraph` objects carry their own colour and ignore a
`TableStyle` `TEXTCOLOR`. Header cells now use a dedicated white style. Caught
by rendering the PDF and looking at it, not by the tests.

**Word headings were Word's default blue**, not brand green. `add_heading()`
applies the built-in style; the colour now overrides it explicitly.

Tests: **30 passing** (was 23). Seven added covering the sync guard clauses,
both report formats, year formatting, Latin-1 safety and caveat coverage.

---

## Findings from your 2019–2026 extract

Run with the shipped rules. These are the tool's own output, not hand analysis.

**International price gap: $213.9M cumulative.** By share, the story has
inverted — Coltan dominated the early years (67% of the 2019 gap), Wolframite
now dominates (**77% of the 2026 gap**, $60.3M of $78.3M).

**Peer benchmark, contained-metal basis, four bases:**

| Basis | Cassiterite | Coltan | Wolframite | Total |
|---|---|---|---|---|
| Current month | $9.39M | $26.23M | $24.17M | **$59.79M** |
| Moving 3-month | $10.70M | $22.30M | $17.91M | $50.91M |
| Current quarter | $8.85M | $26.12M | $24.29M | $59.26M |
| Moving 2-quarter | $10.19M | $18.60M | $14.06M | $42.85M |

The spread between bases (**$42.9M to $59.8M**) is itself a finding: roughly a
third of the measured gap is timing rather than persistent under-pricing.
Longer windows absorb month-to-month volatility, so a figure quoted from this
tool should always name its basis.

**Worst traders 2026, ranked by value forgone vs the monthly peer average:**

- *Wolframite* — Boss Mining Solution ($115.37 vs $156.00, 26% below, **below average in 100% of months**, $4.60M); African Panther Resources (37.9% below, 100% of months, $3.23M); Kanzamin ($2.99M)
- *Coltan* — Raph Mining Supply (12.9% below, 100% of months, $3.14M); JCSpring (25.4% below, 100% of months, $2.90M)
- *Cassiterite* — Raph Mining Supply (12.6% below, 100% of months, $0.51M)

The consistency column earns its place here. Space Mining shows a 2.1% Coltan
discount yet $2.30M forgone — large volume, marginal pricing. Philbert Trading
appears on the list with a *negative* discount: it beat the average overall and
is there on volume alone. Neither is the same phenomenon as Boss Mining or
African Panther, which sat below the average in every single month.

**What Min is for, demonstrated.** Tungsten concentrate 2026, peer range by
month: January $58.74–$70.95 (spread $12), September **$58.50–$231.79 (spread
$173)**. The floor barely moved while the ceiling quadrupled. Either some
exporters are locked into pre-surge contracts, or the low-end records need
checking. That is exactly the question the minimum statistic exists to raise.

**Still flagged, not excluded — 28 records worth reviewing:**

- 16 rows: identical grade *and* quantity declared at different values (largest: JCSpring, $6,818 vs $416,119)
- 8 rows: one shipment number used by two different exporters
- 3 rows: product declared under the wrong mineral
- 1 row: ~100× grade divergence within one shipment

These are proposals on **2 · Rules & Data Quality → Anomaly Suggestions**. I
have not excluded them — they are judgement calls for you, and several may be
legitimate multi-lot consignments.

---

## Still not built

- Scheduled or automatic ingestion
- Authentication or read-only roles
- Charts embedded in the Word/PDF reports (tables and figures only)
