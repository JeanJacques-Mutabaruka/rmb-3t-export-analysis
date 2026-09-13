# CHANGES — V1-0e

**Date:** 13 September 2026
**Supersedes:** V1-0d

One feature and one highlighted remark, both in Exporter Scorecard.

---

## 1. New tab: 🏅 Best Traders

The exact mirror of Worst Traders — exporters who repeatedly sold **above**
what their peers achieved for the same product in the same period, and moved
enough tonnage for the premium to represent real money.

Same structure as Worst Traders throughout, so the two read as a genuine pair:

- **Rank by** Value gained ($) or Premium (%), same logic as Worst Traders' Value forgone / Discount
- **Price range**, **Premium range**, **% qty above avg**, **% periods above avg** — every column has a mirror counterpart
- Per-mineral sub-tabs, year selector, min-quantity filter, download button
- **Green/teal highlighting** on % qty above avg (75% / 40% thresholds) — deliberately the positive-signal colour, opposite of Worst Traders' red/amber
- An explainer expander with the same worked-example structure as Worst Traders, adapted for gains

### New engine fields (mirroring the existing forgone/below-average ones)
`gained_vs_avg`, `above_avg`, `qty_above_avg`, `pct_qty_above_avg`,
`periods_above_avg`, `premium_consistency`. Computed alongside the existing
forgone-side fields in `discounts()` and `scorecard()` — same functions, same
per-period floor-at-zero logic, just the other direction.

**Verified mutually exclusive per row**: for any single exporter-period, at
most one of `forgone_vs_avg` / `gained_vs_avg` can be positive — an exporter is
either at, above, or below the average that period, never two of those at
once. Tested directly.

### A finding worth your attention
Your **Trinity Nyakabingo Mine** is #1 on Best Traders for Wolframite 2026 by
value gained ($18.2M, a 25.2% premium, 100% of its tonnage sold above the peer
average) — and earlier analysis flagged it as your largest exporter by volume
in the leave-one-out check. Large and well-priced together is the profile
worth studying for what it's doing right.

Also visible: **RANI MINING** appears on Best Traders for Wolframite despite a
**negative** annual premium (-4.8%) — the mirror image of the negative-discount
puzzle from Worst Traders. It underperformed the average across the year
overall, but a specific period was strong enough to register real value gained.
Same reasoning as before, opposite direction: a single annual figure can hide
what happened period by period.

---

## 2. The competitive-risk remark you asked for

**Added to the Worst Traders tab, directly under the explainer — not buried,
and in a colour used nowhere else in the tool:**

> A worst trader's problem can compound. If other exporters are consistently
> achieving higher selling prices, the buyers behind those prices can typically
> afford higher buying prices too — that is usually where the higher selling
> price comes from. A worst trader can therefore be squeezed from both
> directions: realising less per kilogram than its peers, and at risk of losing
> access to the miners' output altogether if a best trader simply outbids it
> upstream.

**New indigo/blue banner style** (`insight_banner()` in `style.py`), distinct
from the existing red data-quality alert, amber caution warning, and green
routine note — chosen specifically so this reads as a strategic observation,
not a data caveat, and doesn't get visually lumped in with either.

A shorter version of the same cross-reference sits on the **Best Traders** tab
too: compare the two tabs for the same commodity and year, and where the same
buyers or destinations show up on both sides, that's the clearest sign of a
real, addressable gap rather than a structural disadvantage.

---

## Testing

**46 tests, all passing** (was 41). Five added:

- Forgone and gained are mutually exclusive on every row, and symmetric in magnitude for a simple two-exporter case
- `best_traders()` ranked by value gained returns the exporter who actually gained
- `best_traders()` ranked by premium correctly uses the most *negative* discount (a negative discount is a positive premium)
- `pct_qty_above_avg` and `pct_qty_below_avg` sum to the whole for an exporter with no period exactly at the average
- `best_traders()` returns empty for a year with no data, rather than erroring

---

## A note on `benchmarks_peer.py`

I flagged after V1-0d that this module was accumulating several purposes. This
round added to it again — by design, since Best Traders is a genuine mirror of
existing logic, not a new concern. But the file is now doing five things:
outlier detection, discount calculation, leave-one-out, forgone tracking, and
now gained tracking. It's still fully tested and each addition is small and
symmetric, but if you have more changes planned for this area, it's worth
asking me to split it before a sixth layer goes on.

---

## Files changed

```
engine/benchmarks_peer.py   discounts(): above_avg, gained_vs_avg added;
                            scorecard(): periods_above_avg, qty_above_avg,
                            pct_qty_above_avg, premium_consistency,
                            gained_vs_avg added; best_traders() added
app/glossary.py             BEST_TRADER_METHOD, COMPETITIVE_RISK_NOTE,
                            COMPETITIVE_RISK_DETAIL added
app/style.py                insight_banner() + indigo THEME tokens added
app/pages/6_Exporter_Scorecard.py   new Best Traders tab; highlighted note
                                    added to Worst Traders; tab indices
                                    renumbered (5 tabs, was 4)
tests/test_engine.py        5 new tests
```
