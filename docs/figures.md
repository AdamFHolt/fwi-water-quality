# Figures & methods

What each figure in `plots/` shows, and definitions for the technical terms used
across them. All analysis is **blind**: cohorts are labelled **Group D** and
**Group E**, never Control/Treatment. Throughout, **blue = Group D**,
**orange = Group E**, and **grey = "not resolved"**.

Figures are produced by `main.py` (functions in `src/plotting_functions.py`,
which call the analysis functions in `src/functions.py`).

---

## Background concepts

These recur in several figures; defined once here.

- **OOR event** — an "out of range" water-quality detection. Day 0 is a routine
  (non-follow-up) visit where `Is WQ in range?` is "No". Morning + Evening
  readings on the same pond-day are collapsed into one event.

- **The V7 TRIAD / primary measure.** Each OOR event is followed up on a
  schedule: **Day 0** (detected) → **Day 2** (secondary check) → **Day 3** (the
  *primary* outcome). "Resolved" everywhere in these figures means the **Day-3
  primary** measure — i.e. the event's water quality was back in range at the
  latest follow-up (`2nd FU WQ improvement` = "Yes" in the OOR Events sheet).

- **Resolution rate.** The headline outcome: share of OOR events that are
  resolved at Day 3, compared between groups. Computed two ways:
  - **Event-level** — `resolved events / events`. Each *event* counts once, so
    a pond with several events is weighted more heavily.
  - **Pond-level** — collapse each pond to its own resolution proportion, then
    average those across ponds. Each *pond* counts once. This guards against
    **pseudoreplication**: multiple events from the same pond aren't independent
    (same pond, farmer, management), so the event-level rate can be dominated by
    a few repeat-event ponds. (See `oor_resolution.by_pond.png`.)

- **Denominator / "with follow-up".** Events with no Day-3 follow-up are
  excluded from the rate (they have no outcome to score). In this dataset every
  event has a follow-up, so the counts match the OOR Events sheet exactly; the
  cross-check in `analyze_oor_events` asserts this.

- **Baseline water quality.** Computed from **routine visits only** (follow-ups
  are conditional on an OOR event, so a biased subsample), then **averaged to one
  value per pond** to avoid pseudoreplication. **DO is split by time of day**
  (Morning vs Evening) because dissolved oxygen swings strongly over the day
  (~3 mg/L morning vs ~11 mg/L evening); pooling them would manufacture a huge,
  meaningless spread. So the per-pond parameters are: **DO (Morning)**,
  **DO (Evening)**, **pH**, **Ammonia–NH₃**. Only these three parameters are
  populated in the dataset.

---

## `oor_events.png`

The primary-outcome figure, built entirely from the **OOR Events** sheet. One
column per group. Rows, top to bottom:

1. **Overall resolution pies** (one per group). Fraction of that group's OOR
   events resolved at Day 3 (group colour) vs not resolved (grey). The slice
   labels show both the percentage and the raw count; the title shows `n` (number
   of events with a follow-up).

2. **OOR event drivers** (grouped bars). How many OOR events flagged each
   parameter (DO, pH, Ammonia), per group. A single event can flag several
   parameters (e.g. "DO, pH"), so it is counted under each — the bars sum to more
   than the number of events.

3. **Per-parameter resolution pies** — one row per parameter (DO, pH, Ammonia),
   one pie per group. The share of events *involving* that parameter that
   resolved at Day 3. **Caveat:** the sheet records only one overall Day-3
   outcome per event, not a per-parameter outcome, so these pies show the overall
   resolution of the *events that included* that parameter — not whether that
   specific parameter came back into range.

### `oor_events.anoms_removed.png`

Identical to the above, but with the **baseline-WQ outlier ponds removed**
(see "outliers" in the glossary). A sensitivity check: it shows the resolution
picture isn't being driven by a few atypical ponds.

---

## `oor_resolution.by_pond.png`

The **pond-level** companion to the pies — one point per pond.

- **Each point is one pond.** Vertical position = that pond's resolution rate
  (% of *its own* OOR events resolved at Day 3). Points are jittered horizontally
  within each group so they don't overlap.
- **Point size ∝ number of OOR events** the pond had.
- **Horizontal bar** per group = the **pond-level mean** (unweighted mean of the
  per-pond rates; labelled e.g. "mean 15.6%"). This is *not* the same number as
  the event-level pie, because here every pond counts equally regardless of how
  many events it had.
- **Right-hand key panel** does double duty:
  - **Horizontal bars** = how many ponds had 1, 2, 3, 4 events, split by group
    (the events-per-pond distribution).
  - **Grey dots** down the left edge = the **point-size key**, each sized like
    the main scatter and aligned to its event-count row.

Why this figure exists: it shows the D-vs-E gap survives when each pond counts
once, so the result isn't an artifact of repeat-event ponds, and it exposes the
per-pond spread the pies collapse away. Note per-pond rates are lumpy (0, 50,
100 %) because most ponds have very few events.

---

## `water_qualities.png`

**Baseline water quality per group**, one column per parameter (DO Morning,
DO Evening, pH, Ammonia–NH₃), using one value per pond (routine visits).

- **Top row — mean ± SD bars.** Bar height = group mean across ponds; error bar =
  ± 1 standard deviation across ponds. `n` in the x-label is the number of ponds.
  The subplot title shows **Hedges' g**, the standardized D-vs-E mean gap (see
  glossary).
- **Bottom row — box + strip.** A box plot of the per-pond values with every pond
  drawn as a jittered point on top. The subplot title shows **Levene p** for that
  parameter (see glossary).

Together the two titles give the standard baseline-balance pair: **Hedges' g**
(difference in *means*) and **Levene p** (difference in *spread*).

This is the figure to read for whether the two groups start out comparable.

### `water_qualities.anoms_highlighted.png`

Same layout, but the **WQ-outlier ponds are excluded from all statistics**
(bars, box, `n`, and Levene p all describe the cleaned distribution — matching
the pond set dropped in `oor_events.anoms_removed.png`). Each excluded outlier is
still drawn back in as a **red-ringed point**, labelled with its short Pond ID and
OOR-event count (e.g. `9252e874 (4 ev)`), in the panel for the parameter it is
extreme on — so you can see how far outside the cleaned distribution it sat.

---

## `water_qualities.visits.png`

The **visit-level** view of baseline water quality: **one point per routine
visit** (not collapsed to ponds). Same four columns (DO Morning, DO Evening, pH,
Ammonia). Top row: mean ± SD bars (`n` = number of visits). Bottom row: box plot
with a dense, semi-transparent strip of all visits.

Contrast with `water_qualities.png`: this one shows the raw visit-to-visit
spread, whereas the per-pond figure shows the spread *between ponds* (the unit
used for the statistics, to avoid pseudoreplication).

---

## Glossary

- **Group D / Group E.** Blinded cohort labels (Control vs Treatment is
  deliberately hidden from analysis). All comparisons are D vs E.

- **mean ± SD.** Standard deviation is a measure of spread around the mean. The
  error bars span one SD either side. (Note: for the *pond-level resolution*
  figure SD is deliberately **not** used — those rates are bounded [0, 100] and
  bimodal, so SD would misrepresent them; all points are shown instead.)

- **Box plot.** The box spans the interquartile range (IQR: 25th–75th
  percentile); the line inside is the **median**; whiskers extend to the most
  extreme points within 1.5×IQR. Outlier fliers are hidden here because the raw
  points are already drawn as a strip.

- **Jittered strip.** The individual data points, nudged sideways by a small
  random amount so overlapping values are visible. Jitter is reproducible (fixed
  random seed).

- **Levene's test (p).** Tests whether two groups have **equal variance**
  (equal spread), as opposed to equal means. We use the median-centred variant
  (**Brown–Forsythe**), which is robust to non-normal data, on the per-pond
  baseline values. Interpretation: **p > 0.05 ⇒ no evidence the variances
  differ** (spreads look similar between D and E); a small p (≤ 0.05) would
  suggest the groups differ in variability. It says nothing about the means.

- **Hedges' g (standardized mean difference).** The gap between the two groups'
  means expressed in pooled-SD units: `(mean_D - mean_E) / pooled_SD`, with a
  small-sample correction (the "Hedges" part, which matters at this n ~ 25). It
  is the *location* companion to Levene's *spread*: g measures how far apart the
  means are, scaled so it's comparable across parameters and independent of
  sample size. Convention: **|g| < 0.1 negligible**, 0.2 small, 0.5 medium, 0.8
  large. Reported descriptively, with **no significance test** — testing baseline
  differences for significance confounds effect size with sample size, so a bare
  effect size is the honest summary.

- **Baseline-WQ outliers (studentized residual).** For each parameter we fit a
  simple `value ~ group` model on the per-pond values and flag unusual ponds by
  their **internally studentized residual** — how many standard deviations a pond
  sits from its group mean, scaled by the model's residual spread. A pond is an
  **outlier** if its absolute studentized residual exceeds **2** (i.e. >2 SD from
  its group mean). These flagged ponds are what gets removed in the
  `anoms_removed` / `anoms_highlighted` variants.
  - *Why not Cook's distance?* It's the usual influence companion to the
    residual, but a two-group factor has constant within-group leverage, so
    Cook's distance is just a monotone function of the residual (rank correlation
    0.999 on this data) — it flags nothing the residual doesn't, so it's omitted.

- **Pseudoreplication.** Treating non-independent measurements as if they were
  independent — e.g. counting many visits (or events) from one pond as separate
  observations. Addressed by collapsing to one value per pond before computing
  group statistics.
</content>
</invoke>
