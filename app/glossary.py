"""Central definitions for tooltips and explainers.

One place, so "pure quantity" is explained identically on every page and a
wording fix lands everywhere at once.
"""
from __future__ import annotations

PURE_QUANTITY = (
    "**Pure quantity (contained metal).** Not the gross weight shipped — the "
    "weight of the valuable metal inside it.\n\n"
    "Pure quantity (kg) = Gross quantity (kg) × Grade (%) ÷ 100\n\n"
    "Example: 20,000 kg of cassiterite at 62% grade contains "
    "20,000 × 62 ÷ 100 = 12,400 kg of tin. The other 7,600 kg is waste rock "
    "and gangue, which nobody pays for.\n\n"
    "Every price in this tool is $ per kg of pure quantity, so a high-grade "
    "and a low-grade shipment can be compared directly."
)

GROSS_QUANTITY = (
    "**Gross quantity.** The total weight declared on the shipment, including "
    "the waste rock. Shown for reference only — all pricing and benchmarking "
    "uses pure quantity (contained metal) instead."
)

UNIT_PRICE = (
    "**$ per kg of contained metal**, not per kg shipped.\n\n"
    "Price = Shipment value ($) ÷ Pure quantity (kg)\n\n"
    "Computing it this way removes grade from the comparison: a 30% coltan lot "
    "and a 45% coltan lot are judged on what the metal inside them fetched."
)

GRADE_STD_DEV = (
    "**Standard deviation of grade — how consistent the material is.**\n\n"
    "Roughly two thirds of shipments fall within one standard deviation of the "
    "average grade.\n\n"
    "Example: average grade 60% with a standard deviation of 3 means most "
    "shipments run 57–63%. A standard deviation of 12 on the same average "
    "means most run 48–72% — far less predictable.\n\n"
    "In practice: a **low** figure means buyers know what they are getting and "
    "can price tightly. A **rising** figure means the material is becoming less "
    "consistent, which invites impurity penalties, wider assay disputes and "
    "weaker negotiating ground. It can signal a change of source deposit, "
    "looser sorting at the washing station, or blending of lots."
)

PEER_AVERAGE = (
    "**Peer average.** The volume-weighted average price achieved by every "
    "exporter shipping the SAME PRODUCT in the same period. Volume-weighted "
    "means large consignments count more than small ones, so it reflects what "
    "the market actually paid rather than an average of headline prices."
)

PEER_MAX = (
    "**Peer maximum.** The best price any single exporter achieved for that "
    "product in that period. Useful as a stretch target — it is not a "
    "realistic expectation for every exporter, since the best price often "
    "reflects a particular buyer relationship or an unusually clean lot."
)

PEER_MIN = (
    "**Peer minimum.** The lowest price any exporter achieved for that product "
    "in that period. It is a statistic and an error-detection aid, not a loss "
    "benchmark — nobody is 'losing' relative to the floor. An implausibly low "
    "minimum usually points at a record that needs checking or excluding. "
    "Together with the maximum it shows the trading range: a widening range "
    "means exporters are getting increasingly different outcomes for the same "
    "material."
)

VALUE_FORGONE = (
    "**Value forgone.** The additional revenue an exporter would have earned "
    "had it matched the peer benchmark, summed across periods.\n\n"
    "Per period: max(0, benchmark price − exporter price) × that exporter's "
    "pure quantity in the period.\n\n"
    "Floored at zero per period: a period where the exporter beat the "
    "benchmark contributes zero, never a negative offset."
)

PCT_QTY_BELOW = (
    "**% of contained tonnage sold below the peer average.**\n\n"
    "Of all the metal this exporter shipped in the year, the share that moved "
    "in periods when its price sat below the peer average.\n\n"
    "This is usually more telling than the count of periods: an exporter can "
    "be below average in only 2 of 10 months and still have 70% of its tonnage "
    "affected, if those two months carried the big consignments."
)

CONSISTENCY = (
    "**% of active periods below the peer average.** A large discount "
    "sustained across most periods is a pattern; the same discount in a single "
    "period may simply be timing — selling into a dip, or a contract priced "
    "off an earlier reference."
)

THIN_MARKET = (
    "**Thin period.** Fewer than 3 exporters were active for that product in "
    "that period, so the 'market' is largely the exporter itself and the "
    "benchmark carries little weight."
)

PRICE_RANGE = (
    "**Range of realised prices across the year's periods** (lowest to "
    "highest), alongside the volume-weighted average for the year. A wide "
    "range means the exporter's outcomes varied a lot month to month; a narrow "
    "range at a low level is more suggestive of a standing arrangement."
)

DISCOUNT_RANGE = (
    "**Range of the period-by-period discount** against the peer average. "
    "A range spanning zero means the exporter was above the average in some "
    "periods and below it in others."
)

WORST_TRADER_METHOD = """
### What "worst trader" means here

An exporter that repeatedly sold below what its direct peers achieved for the
**same product in the same period** — and moved enough tonnage for that gap to
represent real money.

It is a **screening result, not a finding**. See the caution at the bottom.

---

### How the calculation works

**Step 1 — put every exporter on the same footing.**
Prices are computed per kilogram of *contained metal*, so grade differences drop
out of the comparison:

> Pure quantity (kg) = Gross quantity (kg) × Grade (%) ÷ 100
> Exporter price ($/kg) = Shipment value ($) ÷ Pure quantity (kg)

**Step 2 — build the benchmark for each product and period.**
The peer average is volume-weighted across every exporter shipping that product
in that period:

> Peer average = Σ(all peers' value) ÷ Σ(all peers' pure quantity)

**Step 3 — measure the gap, period by period.**

> Discount % = (Peer average − Exporter price) ÷ Peer average
> Value forgone = max(0, Peer average − Exporter price) × Exporter's pure quantity

The `max(0, …)` matters: a period where the exporter **beat** the average
contributes **zero**, not a negative credit.

**Step 4 — sum across the year and rank.**

---

### Worked example

Exporter X, tin concentrate, three months:

| Month | Their price | Peer average | Their pure qty | Gap/kg | Value forgone |
|---|---|---|---|---|---|
| January | $44.00 | $48.00 | 30,000 kg | $4.00 | 30,000 × $4.00 = **$120,000** |
| February | $52.00 | $49.00 | 5,000 kg | −$3.00 | beat the average → **$0** |
| March | $46.00 | $50.00 | 25,000 kg | $4.00 | 25,000 × $4.00 = **$100,000** |

**Total value forgone = $220,000.**

Year figures for X:
- Total pure quantity = 60,000 kg
- Volume-weighted price = (30,000×44 + 5,000×52 + 25,000×46) ÷ 60,000 = **$45.67**
- Volume-weighted peer average = **$48.83**
- **Discount vs average = 6.5%**
- **Price range = $44.00 – $52.00**
- **% periods below average = 2 of 3 = 67%**
- **% contained tonnage sold below average = 55,000 ÷ 60,000 = 92%**

Note how the last two differ. X was below average in two thirds of its
*periods*, but those periods carried **92% of its tonnage**. The tonnage figure
is the one that tracks the money.

---

### How can the discount be negative while value forgone is positive?

This looks contradictory and is not.

The **discount** is an annual figure: one volume-weighted price against one
volume-weighted benchmark. The **value forgone** is built period by period and
floored at zero in each one.

So an exporter can finish the year *above* the peer average overall — a
negative discount — while still having sat below it in particular periods. Those
periods each contributed value forgone; the periods where it did well
contributed zero rather than cancelling them out.

**In practice it means:** the exporter is not systematically under-pricing, but
it had specific bad periods, or it is simply very large. A negative discount
with meaningful value forgone usually points at **volume**, not conduct — and it
is a materially different situation from an exporter sitting below the average
in every single period.

Read the columns together:

| Pattern | Likely reading |
|---|---|
| Large discount + high % tonnage below + below average in most periods | A sustained pattern. Worth asking about. |
| Small or negative discount + large value forgone | Mostly volume. Even a slim gap on big tonnage adds up. |
| Large discount + few periods, small tonnage | Probably timing or a one-off lot. Weak signal. |
| Any of the above with thin periods flagged | The benchmark itself is weak. Treat with care. |
"""

WORST_TRADER_CAUTION = (
    "Trading below the peer average is **not by itself evidence of "
    "wrongdoing**. Contract timing, impurity penalties outside the headline "
    "grade, smaller lot sizes, payment and prepayment terms, and long-term "
    "offtake agreements priced off an earlier reference all produce legitimate "
    "discounts. This screen tells you where to look — not what you will find."
)
