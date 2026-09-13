# CHANGES — V1-0f

**Date:** 13 September 2026
**Supersedes:** V1-0e

The `benchmarks_peer.py` split, plus the partial-year handling, drill-down
filters and Ranking rework.

---

## 1. The split (Option A + scorecard helpers)

Done first, as agreed, so the new features landed on the clean structure rather
than being retrofitted afterwards.

```
engine/peer/
├── __init__.py      re-exports the full public API
├── panel.py    (69)  who traded what, when, at what realised price
├── benchmark.py(125) what the market did in each product-period
└── evaluate.py (184) how each exporter compares to that benchmark
```

`engine/benchmarks_peer.py` is now a 19-line compatibility shim, so every
existing call site (`from engine import benchmarks_peer as bp`) works
unchanged. **No page or test file needed editing for the split** — the 46
tests passed untouched immediately after the move, which is the evidence that
it was behaviour-preserving rather than a rewrite.

`scorecard()`'s single 20-field lambda is now four named functions:
`_aggregate_exporter_year()` (grouped by concern — volume, own price,
benchmark, under-performance, out-performance), then
`_underperformance_metrics()`, `_outperformance_metrics()` and
`_relative_metrics()`. The below/above symmetry is now visible in the code
instead of implied.

---

## 2. Partial years — made structural, not a note

Your data, which is exactly why you were right to raise this:

| Year | Coverage |
|---|---|
| **2019** | **2 / 12 months** (Nov–Dec) |
| 2020–2025 | full |
| **2026** | **9 / 12 months** (Jan–Sep) |

**A correction to my own earlier reporting.** In previous summaries I wrote
that exports "grew from $10M (2019) to $631M (2026) — a >60x increase". That
was misleading: 2019 is five weeks of data. The growth is real and large, but
the multiple was inflated by comparing two months against nine. I mentioned
"thin early reporting" once in passing and then kept quoting the figure anyway.

New `engine/coverage.py` provides `year_coverage()`, `partial_years()`,
`coverage_warning()` and `annotate_years()`. The warning names the consequence,
not just the fact — "totals, growth rates and rankings for these years are
**not comparable** with the full years alongside them" — because a bare "2019
is partial" invites a nod and a carry-on.

Wired into every page that aggregates by year: **Market Overview**,
**International Benchmark** (including the cumulative loss figure, which you
didn't ask about but has the same flaw), **Peer Benchmark**, **Exporter
Scorecard** and **Reports**. It appears only when the current selection
actually contains a partial year, so it does not become wallpaper.

---

## 3. Ranking tab, rebuilt

- **Year filter.** Rankings show the **latest selected year**; select 2024–2025 and you rank 2025 against 2024.
- **Quantity columns removed from the all-products view.** Adding kilograms of tin to kilograms of tantalum produces a figure with no meaning. Replaced by rank movement. A caption says so explicitly rather than leaving the reader to wonder where the column went.
- **Product sub-tabs** restore Quantity and Pure quantity, where they are valid.
- **New columns:** `Rank`, `Rank {prev}`, `Move` (▲/▼/new, colour-coded), `Value {prev}`, `Value change %`, `Share % {prev}`, plus a **New entrants** metric.
- **Previous-year figures always come from the full dataset**, per your decision — filtering to 2026 alone still shows the 2025 comparison. Documented in `ranking.py` and in the filter's tooltip.

From your data, 2026 vs 2025: Trinity Nyakabingo **▲3** to #1, Rani Mining
**▲10** to #2, Raph Mining Supply a **new entrant** at #5. Read alongside the
partial-year banner — 2026 is nine months against twelve.

---

## 4. Months column, and the drill-down filters

- **Worst Traders** gains **Months below avg**; **Best Traders** gains **Months above avg** — the specific periods, e.g. `2026-01, 2026-03, 2026-04`.
- **Exporter Detail** gains a **Year-Month** filter.
- **Compare Exporters** gains **Year** and **Year-Month** filters.

The workflow you described now closes: spot an exporter on Worst Traders, read
the months, paste one into Exporter Detail or Compare Exporters. The month
options follow the year selection so the list stays manageable.

Per your decision, the peer-performance table stays **annual** when a month
filter is applied — the shipment figures narrow, the benchmark table does not.
A note says so on screen, since the mixed granularity would otherwise be easy
to misread.

---

## Testing

**55 tests, all passing** (was 46). Nine added:

- Coverage counts distinct months; returns `None` when every year in scope is full; names both the years and the consequence; respects a year selection
- Ranking's previous year survives a filter that excludes it — the specific trap in this design
- New entrants flagged with `NaN` previous rank, not zero
- Rank movement direction is correct (positive = moved up, since a smaller rank number is better)
- Per-product ranking isolates that product
- Scorecard month lists match the flagged periods exactly

---

## Files changed

```
engine/peer/            NEW package - panel.py, benchmark.py, evaluate.py, __init__.py
engine/benchmarks_peer.py   now a 19-line compatibility shim
engine/coverage.py      NEW - partial-year detection and warnings
engine/ranking.py       NEW - year-on-year rank movement
app/glossary.py         MONTHS_COLUMN_BELOW / _ABOVE added
app/pages/3,4,5,7       coverage warnings wired in
app/pages/6             Ranking rebuilt; months columns; Year-Month filters
tests/test_engine.py    9 new tests
```

---

## One note for next time

`app/pages/6_Exporter_Scorecard.py` is now ~580 lines across five tabs and is
the file this round grew most. It is the same pattern I flagged for
`benchmarks_peer.py` two rounds ago, one layer up. If the next request touches
this page substantially, it is worth splitting the tab bodies into
`app/scorecard/` modules before adding to it — same approach, same reasoning.
