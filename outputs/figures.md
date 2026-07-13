# Figures & methods

What each figure in `plots/` shows, and definitions for the technical terms used
across them. The analysis was run blind: cohorts are labelled Group D and
Group E rather than Control/Treatment. Throughout, blue = Group D,
orange = Group E, grey = "not resolved", and red = baseline-WQ outlier pond.

Figures are numbered `Fig1`–`Fig9` in reading order (baseline water quality
first, then the OOR outcomes). They are produced by `main.py` (functions in
`src/plotting_functions.py`, which call the analysis functions in
`src/functions.py`). For the numeric results and statistical tests in table form,
see [`results.md`](results.md).

---

## Background concepts

These recur in several figures; defined once here.

- **OOR event** — an "out of range" water-quality detection. Day 0 is a routine
  (non-follow-up) visit where `Is WQ in range?` is "No". Morning + Evening
  readings on the same pond-day are collapsed into one event.

- **The V7 TRIAD / primary measure.** Each OOR event is followed up on a
  schedule: Day 0 (detected) → Day 2 (first follow-up) → Day 3 (second follow-up,
  the *primary* outcome). "Resolved" everywhere in these figures means the Day-3
  primary measure, i.e. the event's water quality was back in range on every
  parameter at the latest follow-up (`2nd FU WQ improvement` = "Yes" in the OOR
  Events sheet).

- **Resolution rate.** The headline outcome: share of OOR events that are
  resolved at Day 3, compared between groups. Computed two ways:
  - **Event-level** — `resolved events / events`. Each *event* counts once, so
    a pond with several events is weighted more heavily.
  - **Pond-level** — collapse each pond to its own resolution proportion, then
    average those across ponds. Each *pond* counts once. This guards against
    pseudoreplication: multiple events from the same pond aren't independent
    (same pond, farmer, management), so the event-level rate can be dominated by
    a few repeat-event ponds. (See `Fig6.oor_resolution_by_pond.png`.)

- **Baseline water quality.** Computed from routine visits only (follow-ups
  are conditional on an OOR event, so a biased subsample), then averaged to one
  value per pond to avoid pseudoreplication. DO is split by time of day
  (Morning vs Evening) because dissolved oxygen swings strongly over the day
  (~3 mg/L morning vs ~11 mg/L evening). The study records three water-quality
  parameters (DO, pH, and ammonia), so with DO split in two the per-pond parameters
  are DO (Morning), DO (Evening), pH, and Ammonia–NH₃.

---

## `Fig1.water_quality_all_visits.png`

The visit-level view of baseline water quality: one point per routine
visit (not collapsed to ponds). Four columns (DO Morning, DO Evening, pH,
Ammonia). Top row: mean ± SD bars (`n` = number of visits). Bottom row: box plot
(box = median and interquartile range) over a dense, semi-transparent strip of
all visits.

Contrast with `Fig2.water_quality_per_pond.png`: this one shows the raw
visit-to-visit spread, whereas the per-pond figure shows the spread *between
ponds* (the unit used for the statistics).

---

## `Fig2.water_quality_per_pond.png`

Baseline water quality per group, one column per parameter (DO Morning,
DO Evening, pH, Ammonia–NH₃), using one value per pond (routine visits). This is
the figure to read for whether the two groups start out comparable.

- **Top row — mean ± SD bars.** Bar height = group mean across ponds; error bar =
  ± 1 standard deviation across ponds. `n` in the x-label is the number of ponds.
  The subplot title shows Hedges' g, the standardized D-vs-E mean gap (defined
  in [`results.md`](results.md)).
- **Bottom row — box + strip.** A box plot of the per-pond values with every pond
  drawn as a jittered point on top. The subplot title shows Levene p for that
  parameter (defined in [`results.md`](results.md)).

Together the two titles give the standard baseline-balance pair: Hedges' g
(difference in *means*) and Levene p (difference in *spread*).

---

## `Fig3.water_quality_outliers.png`

Same layout as `Fig2`, but the WQ-outlier ponds are excluded from all
statistics (bars, box, `n`, and Levene p all describe the cleaned distribution,
matching the pond set dropped in `Fig5.oor_resolution_outliers_removed.png`).
Each excluded outlier is still drawn as a red-ringed point and labelled
with its short Pond ID and OOR-event count (e.g. `9252e874 (4 ev)`), in the panel
for the parameter it is extreme on, showing how far outside the cleaned
distribution it sat.

---

## `Fig4.oor_resolution.png`

The primary-outcome figure, built entirely from the OOR Events sheet. One
column per group. Rows, top to bottom:

1. **Overall resolution pies** (one per group). Fraction of that group's OOR
   events resolved at Day 3 (group colour) vs not resolved (grey). The slice
   labels show both the percentage and the raw count; the title shows `n` (number
   of events with a follow-up).

2. **OOR event drivers** (grouped bars). How many OOR events flagged each
   parameter (DO, pH, Ammonia), per group. A single event can flag several
   parameters (e.g. "DO, pH"), so it is counted under each; the bars sum to more
   than the number of events.

3. **Per-parameter resolution pies** — one row per parameter (DO, pH, Ammonia),
   one pie per group. The share of events *involving* that parameter that
   resolved at Day 3. **Caveat:** this figure is built from the OOR Events sheet,
   which stores one overall Day-3 outcome per event, so each pie shows whole-event
   resolution among the events that involved that parameter, not whether that
   parameter itself came back into range.

A single shared legend (group colour = resolved, grey = not resolved) sits below
the figure.

---

## `Fig5.oor_resolution_outliers_removed.png`

Identical to `Fig4`, but with the baseline-WQ outlier ponds removed (see
"outliers" in the glossary). This is a sensitivity check demonstrating that
the resolution gap isn't driven by a few atypical ponds.

---

## `Fig6.oor_resolution_by_pond.png`

The pond-level companion to the `Fig4` pies, one point per pond.

- **Each point is one pond.** Vertical position = that pond's resolution rate
  (% of *its own* OOR events resolved at Day 3). Points are jittered horizontally
  within each group so they don't overlap.
- **Point size** is proportional to the number of OOR events the pond had.
- **Horizontal bar** per group = the pond-level mean (unweighted mean of the
  per-pond rates; labelled e.g. "mean 15.6%"). This is *not* the same number as
  the event-level pie, because here every pond counts equally regardless of how
  many events it had.
- **Right-hand key panel** does double duty:
  - **Horizontal bars** = how many ponds had 1, 2, 3, 4 events, split by group
    (the events-per-pond distribution).
  - **Grey dots** down the left edge = the point-size key.

It shows the D-vs-E gap survives when each pond counts once, and exposes the
per-pond spread the pies hide. Most ponds have only one or two events, so the
per-pond rates cluster at 0, 50, and 100%.

---

## `Fig7.oor_improvement.png`

The continuous companion to the resolution pies: instead of "did it resolve,"
this shows how far each pond closed its out-of-range gap between Day 0 and Day 3. One
panel per OOR parameter (DO, pH, Ammonia). This is the data behind the Welch-t /
Mann-Whitney tests in [`results.md`](results.md) §4.

- **Y-axis — out-of-range gap closed**, in the parameter's native units (mg/L for
  DO/ammonia, pH units for pH): the distance outside the band at Day 0 minus at
  Day 3, with direction folded in so that moving toward the band counts as positive
  whichever side the reading was out on, and the change is cut off at the band edge
  (i.e. no credit for overshooting into range). The dashed line marks 0 (no change).
- **Box + points per group.** The box summarises the pond means (the
  inferential unit); solid black-edged dots are those pond means, faint dots
  behind are the individual OOR events (for context only), since events within a pond
  aren't independent, so the box, `n`, and tests are all pond-level.
  Baseline-WQ outlier ponds' means are drawn in red.
- **Title table** — the Welch-t and Mann-Whitney p-values two ways: all ponds,
  then with the baseline-WQ outlier ponds removed (whole-pond).

---

## `Fig7.oor_improvement.outliers_removed.png`

Identical to `Fig7`, but with the baseline-WQ outlier ponds dropped from the boxes,
dots, and `n` counts (see "outliers" in the glossary) — the sensitivity companion to
`Fig7`. The y-axis per parameter is held to the same range as `Fig7`, so the two
compare panel-for-panel and the empty space shows what was removed; the title table
still reports both the all-ponds and outliers-removed p-values.

---

## `Fig8.day2_vs_day3.png`

The secondary timing analysis (see [`results.md`](results.md) §5). A 2×2 grid of
resolution pies on the events with both follow-ups recorded (one Group-D event
has no Day-2 reading, so D shows 29 of its 30 events): rows = Day 2 (`1st FU`) /
Day 3 (`2nd FU`), columns = Group D / E. Each pie is that group's resolved
(group colour) vs not resolved (grey) share on the given day, with the percentage
and raw count.

At Day 2 both groups are near-identical (~20–25% resolved); only by Day 3
does Group E fill in (82%) while Group D barely changes. The entire effect therefore
appears in that one extra day.

---

## `Fig9.day2_vs_day3_outliers_removed.png`

Identical to `Fig8`, but with the baseline-WQ outlier ponds removed (the same
pond set dropped in `Fig5`). At Day 2 the groups are indistinguishable
(if anything E sits slightly *behind* D, 18% vs 29%), and the Day-3 divergence
still occurs (E 86% vs D 24%). So the pattern, all the separation appearing on
the last day, is not an artifact of a few atypical ponds.

---

## Glossary

- **mean ± SD.** Standard deviation is a measure of spread around the mean. The
  error bars span one SD either side. (Note: for the *pond-level resolution*
  figure SD is deliberately *not* used: those rates are bounded [0, 100] and
  bimodal, so SD would misrepresent them; all points are shown instead.)

- **Box plot.** The box spans the interquartile range (IQR: 25th–75th
  percentile); the line inside is the median; whiskers extend to the most
  extreme points within 1.5×IQR.

- **Jittered strip.** The individual data points, nudged sideways by a small
  random amount so overlapping values are visible. Jitter is reproducible (fixed
  random seed).

- **Baseline-WQ outliers (studentized residual).** For each parameter we compare
  each pond's value to its own group's mean and flag unusual ponds by their
  internally studentized residual: how many standard deviations a pond sits from
  its group mean, scaled by the spread of the residuals. A pond is an outlier if
  its absolute studentized residual exceeds 2. These flagged ponds are the ones
  removed in the `Fig3` / `Fig5` / `Fig9` variants.

(Levene's test, Hedges' g, and pseudoreplication are defined in the
[`results.md`](results.md) glossary.)
