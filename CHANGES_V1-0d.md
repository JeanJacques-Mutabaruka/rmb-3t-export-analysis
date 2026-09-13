# CHANGES — V1-0d

**Date:** 13 September 2026
**Supersedes:** V1-0c

Two features from your review of the deployed app.

---

## 1. Peer Statistics — extreme values, and richer counts

### What prompted this
Your screenshot showed Tantalum concentrate at **$4,299/kg** for January 2020 —
roughly 40× the level every other month sat at. I traced it in the demo data:
one exporter (Kivu Ridge Minerals) carries the deliberately-seeded corrupted
value anomaly (a 300× multiplier on one row), and it landed in that
month/product. A single bad record was dominating an average and a chart.

### How it's fixed
**IQR-based outlier detection**, applied per product-period to the exporter-level
prices behind the peer statistics: a price is treated as extreme if it falls
outside 3× the interquartile range of that period's prices. This threshold is
not itself distorted by the value it's trying to catch, unlike a mean or a
z-score. Periods with fewer than 5 active exporters are skipped — quartiles
aren't meaningful on that few points, and those periods are already flagged
separately as thin markets.

**Scoped to display only, as agreed.** Peer Statistics now shows the
outlier-cleaned Average/Max/Min/Range. Discount %, Value Forgone and Worst
Traders are untouched — they still compute from the full peer set, exactly as
before. Nothing you've already reviewed moved.

**New tab: 🚫 Outliers Excluded**, next to Peer Statistics. Lists every
excluded price with the exporter, the period, the peer median for reference,
and the exact fence it fell outside — so nothing disappears silently. A note
there: an excluded price still counts fully in Discount/Forgone/Worst Traders,
even though it's absent from the Peer Statistics chart.

### New counts
Peer Statistics now shows, per period:
- **n_exporters** — distinct exporters (existing)
- **n_shipments** — total shipment records behind that period, new. Several
  shipments from one exporter all count, so this can run well above
  n_exporters.
- **n_outliers_excluded** — how many prices were removed from that row's
  Average/Max/Min/Range

### A bug caught while testing this
My first cut of the outlier rule failed exactly the case it needed to catch:
when six exporters price identically and a seventh is wildly different, the
interquartile range of that set is **zero** (the middle 50% has no spread), and
my code read "zero IQR" as "can't compute a bound, skip." That's backwards — a
zero-width IQR means the mainstream cluster is *that* tight, so anything
outside a tiny tolerance around it is exactly the outlier the rule exists to
find. Fixed: a zero IQR now uses a near-zero relative tolerance instead of
skipping. Caught by a test before this shipped, not after.

---

## 2. Leave-one-out peer average

**New column, added everywhere the ordinary peer average appears: "Peer avg
(excl. self)"** — Peer Benchmark → Discounts, Exporter Scorecard → Exporter
Detail, and Compare Exporters.

It recomputes the volume-weighted peer average with the exporter's own
shipments removed from the total first. This matters most for a large
exporter: the ordinary peer average includes that exporter's own volume, so a
big player partly benchmarks against itself, understating how far it actually
sits from everyone else.

**Additive, as agreed.** Discount %, Value Forgone and Worst Traders keep using
the ordinary (inclusive) peer average, exactly as validated. This column is for
comparison, not a replacement.

On your data, your largest exporter (by contained tonnage) shows a
leave-one-out average that differs from the ordinary peer average in every
single period — expected, since removing a large player's own volume from its
own benchmark always moves the number, and confirms the column is behaving as
intended rather than degenerating to the same figure.

One edge case handled: if an exporter is the *only* one active in a period,
leave-one-out is undefined (nothing to average) and is correctly left blank
for that period — without blanking the exporter's whole-year figure, which
still weights across every period where a comparison was possible.

---

## Testing

**41 tests, all passing** (was 34). Seven added:

- An outlier is excluded from the display average but the raw average used by `discounts()` still includes it — proving the two paths stayed genuinely separate
- Uniform prices produce zero outliers
- Outlier detection is skipped below 5 exporters, even with an extreme price present
- Shipment count and exporter count diverge correctly when one exporter ships multiple times
- Leave-one-out average for a two-exporter market equals exactly the other exporter's own price
- Leave-one-out is `NaN`, not zero or an error, when an exporter is alone in a period
- A scorecard's annual leave-one-out figure correctly skips a `NaN` period rather than propagating it into the whole year

---

## Files changed

```
engine/benchmarks_peer.py   peer_stats() now returns (stats, outliers);
                            adds peer_avg_clean/peer_max_clean/peer_min_clean/
                            peer_range_clean, n_shipments, n_outliers_excluded;
                            discounts() adds peer_avg_excl_self;
                            scorecard() adds peer_avg_excl_self (NaN-safe
                            weighted average via new weighted_mean_skip_na())
app/glossary.py             PEER_AVG_EXCL_SELF added
app/pages/5_Peer_Benchmark.py    new Outliers Excluded tab; Peer Statistics
                                 shows cleaned figures + counts; Discounts
                                 gains the leave-one-out column
app/pages/6_Exporter_Scorecard.py  Exporter Detail and Compare Exporters gain
                                   the leave-one-out column
app/pages/7_Reports_and_Exports.py  peer_stats() call sites updated for the
                                    new return shape; outliers sheet added to
                                    the full export when any exist
tests/test_engine.py        7 new tests
```

All six call sites consuming `peer_stats()`'s previous single-return signature
were updated — three in the app pages, four in tests. A full page sweep and
the demo-data flow were re-verified after the change.
