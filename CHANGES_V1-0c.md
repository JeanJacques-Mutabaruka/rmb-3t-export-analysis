# CHANGES — V1-0c

**Date:** 12 September 2026
**Supersedes:** V1-0b

Bug fixes and explanatory work from your review of V1-0b.

---

## 1. Name harmonisation — two bugs fixed

### Variants can now be chosen from the full name list

The matcher only ever proposed names above the similarity threshold, so any
spelling it missed was unreachable. Each proposal now carries:

- **Every name in the field**, not just the proposed ones
- The matcher's suggestions **pre-selected** by default
- A **keyword filter** above the picker — type `halcyon` and the list narrows to
  matching names; clear it and anything already selected stays selected
- A live line showing the result: *"**HALCYON INC.** covering 393 rows from 4 spellings"*

### APPROVE now merges and recomputes immediately

**This reverses a decision you confirmed earlier**, so I want it visible rather
than buried. In the V0-2 spec you asked for a change preview *before* applying.
You have now asked for APPROVE to merge and recompute directly, so the button is
one step: it applies the rule, recomputes every analysis, and shows an
**"Applied — what changed"** panel afterwards with rows re-labelled, distinct
buyer count before and after, and the shift in top-5 concentration.

Nothing is lost — you still see the impact, just after rather than before. Say
the word if you would rather have the two-step flow back for approvals.

### Remove (un-merge) actually removes

It was writing to a preview slot rendered on a *different* sub-tab, so pressing
it appeared to do nothing. It now:

1. Asks for confirmation, naming how many spellings will revert
2. Removes the rule, recomputes, and reports what changed
3. The grouping reappears on **Proposals** automatically, since it is no longer
   covered by a rule

---

## 2. Market Overview

- **Buyers & Destinations** — year filter added, on the same row as the dimension selector.
- **Grades** — new range chart plotting weighted average with **minimum and maximum** grade per year, so the spread is visible rather than implied. Product selector sits on the same row as the products filter.
- **Std dev** — tooltip on the column plus a full expander explaining it in practical terms: what a standard deviation of 3 versus 12 means for the same average grade, and why a rising figure invites impurity penalties and weakens negotiating ground.

---

## 3. "Quantity" now says which quantity

A shared glossary (`app/glossary.py`) defines each term once, so the wording is
identical everywhere and a fix lands in every page at once.

- **Pure quantity (contained metal)** — formula, a worked example (20,000 kg at 62% grade contains 12,400 kg of tin; the other 7,600 kg is waste rock nobody pays for), and why every price in the tool is expressed per kg of it.
- **Gross quantity** — flagged as reference only.
- Tooltips attached on Market Overview, Peer Benchmark, Exporter Scorecard and Reports. The Market Overview metric is now labelled "Pure quantity (contained metal)" rather than "Contained metal".

---

## 4. Exporter Scorecard

### Exporter detail
Year filter added, on the same row as the exporter selector. It filters the
shipments, the metrics and the peer-performance table together.

### Worst Traders — new explainer
An expander directly under the title covering: what the term means, the
four calculation steps with formulas, a **full worked example** with a
three-month table, and a reading guide for the column combinations.

It answers the negative-discount question explicitly. The short version: the
**discount** is one annual volume-weighted figure, while **value forgone** is
built period by period and floored at zero in each. So an exporter can finish
above the peer average overall — negative discount — while still having sat
below it in particular periods, each of which contributed forgone value that the
good periods do not cancel out. A negative discount with large forgone value
usually points at **volume, not conduct**.

Your data has real examples. Hillside Mining (Coltan 2025) shows a discount of
−0.22% — it beat the average across the year — yet **88.7% of its contained
tonnage moved in periods when it was below average**, carrying $235,532 of
forgone value.

### New and changed columns

| Column | Change |
|---|---|
| **Price range** | New — lowest to highest realised price across the year's periods, beside the weighted average |
| **Disc range** | New — period-by-period discount range. A range spanning zero means above average in some periods, below in others |
| **% qty below avg** | New — share of contained tonnage sold in below-average periods. **Highlighted red above 75%, amber above 40%** |
| **% periods below avg** | Kept, with a tooltip distinguishing it from the tonnage measure |

**Why the tonnage column matters more.** From your data: Minerals Fusion
(Coltan 2025) was below average in **50% of periods** but only **9.1% of
tonnage** — a weak signal. Gisande Trading was below average in **67% of
periods** and **93.3% of tonnage** — a strong one. The period count alone cannot
tell these apart.

---

## 5. Filter layout

Where a tab has two or more filters they now sit in columns on one row:
Buyers & Destinations, Grades, Exporter Detail, Discounts. Worst Traders and
Basis Settings already did.

---

## Testing

**34 tests, all passing** (was 30). Four added:

- Price and discount ranges are computed across periods, not from the annual aggregate
- `% qty below avg` is volume-weighted and genuinely diverges from the period count (fixture: below average in 1 of 2 periods, but 91% of tonnage)
- The negative-discount case reproduces exactly: an exporter with a negative annual discount and a non-zero, correctly-valued forgone figure
- Tonnage below average can never exceed total tonnage, and the percentage stays within 0–100%

---

## Files changed

```
engine/benchmarks_peer.py   scorecard(): price_min/max, disc_min/max,
                            qty_below_avg, pct_qty_below_avg
app/glossary.py             NEW - all tooltip and explainer text
app/pages/2_Rules_and_Data_Quality.py   full name picker, keyword filter,
                                        immediate apply, working un-merge
app/pages/3_Market_Overview.py          year filter, grade range chart, tooltips
app/pages/5_Peer_Benchmark.py           peer stat tooltips, filter row
app/pages/6_Exporter_Scorecard.py       explainer, new columns, year filter
app/pages/7_Reports_and_Exports.py      tooltips
tests/test_engine.py                    4 new tests
```
