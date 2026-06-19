"""
Post-hoc (unblinded) analysis: do self-initiated actions (SIA) — corrective
steps farmers took on their own — affect OOR outcomes?

Runs on the non-anonymized workbook (Control/Treatment labels; same hashed
Pond IDs and core schema as the anonymized file, plus the SIA columns), via
main_sia.py. Unlike the cohort comparison in main.py, SIA exposure is
self-selected, so everything here is exploratory/descriptive, not causal.

  sia_actions           tidy table of SIA records with implementation windows
  event_sia_exposure    flag each OOR event with SIA exposure in its
                        Day-0..Day-3 window (exact / possible / none)
  describe_sia_exposure print the exposure summary by group
  resolution_by_exposure        Day-3 resolution, exposed vs unexposed, within group
  resolution_groups_by_stratum  the D-vs-E comparison within each exposure stratum
  describe_resolution_by_exposure  print both + the exact-only sensitivity line
  timing_by_exposure            the §5 gained/lost split by full-window exposure
  gains_by_action_timing        do late actions (Day 2 -> Day 3) predict the gains?
  describe_timing_by_exposure   print both timing cuts + exact-only sensitivity
"""

import re

import pandas as pd
from scipy.stats import fisher_exact

from src.functions import _section

# The OOR Events sheet's date columns (the Day-0 header contains newlines).
DAY0_COL = "\nDate Initial OOR\n(Day 0)"
DAY2_COL = "Date 1st FU (day 2)"
DAY3_COL = "Date 2nd FU (day 3)"

# Unblinding map to the labels used throughout the blind analysis (the visit
# counts pin it: Control 532 = Group D, Treatment 466 = Group E).
BLIND_LABEL = {"Control": "Group D", "Treatment": "Group E"}


def sia_actions(data: pd.DataFrame) -> pd.DataFrame:
    """One row per visit-recorded self-initiated action, with the window
    [start, end] in which it was implemented.

    An exact implementation date gives a one-day window (start = end). Rows
    with only a range like "0-7 days ago" (relative to the visit date) get the
    corresponding interval [visit - 7, visit - 0]. Every SIA row in the dataset
    has one or the other. Returns columns: Pond ID, group, visit, actions,
    start, end, basis ("exact"/"range").
    """
    sia = data[data["Self-initiated actions taken"].notna()].copy()
    sia["visit"] = pd.to_datetime(sia["Date of data collection"])
    sia["exact"] = pd.to_datetime(sia["Self-initiated actions implemented on (exact date)"])

    rows = []
    for _, r in sia.iterrows():
        ex = r["exact"]
        if pd.notna(ex):
            start = end = ex
            basis = "exact"
        else:
            m = re.fullmatch(r"(\d+)-(\d+) days ago",
                             str(r["Self-initiated actions implemented (date range)"]).strip())
            if not m:
                raise ValueError(f"unparsed SIA date range: {r['Self-initiated actions implemented (date range)']!r}")
            a, b = int(m.group(1)), int(m.group(2))
            start, end = r["visit"] - pd.Timedelta(days=b), r["visit"] - pd.Timedelta(days=a)
            basis = "range"
        rows.append({
            "Pond ID": r["Pond ID"], "group": r["Pond status"], "visit": r["visit"],
            "actions": r["Self-initiated actions taken"],
            "start": start, "end": end, "basis": basis,
        })
    return pd.DataFrame(rows)


def _classify_overlap(a: pd.DataFrame, lo, hi) -> str:
    """Grade one pond's actions against the window [lo, hi]:
    exact if an exact-dated action lands inside, possible if only a
    range-dated action's window overlaps, none otherwise."""
    hit = a[(a["start"] <= hi) & (a["end"] >= lo)]
    if (hit["basis"] == "exact").any():
        return "exact"
    return "possible" if len(hit) else "none"


def event_sia_exposure(events: pd.DataFrame, actions: pd.DataFrame) -> pd.DataFrame:
    """Flag each OOR event with its SIA exposure (exact / possible / none).

    Three windows per event, all graded by `_classify_overlap`:
      sia        — the full [Day 0, Day-3 follow-up] span (the step-2 flag)
      sia_early  — [Day 0, Day 2]
      sia_late   — [Day 2 + 1, Day 3], i.e. strictly after the Day-2 visit date
    An action dated exactly on Day 2 counts as early only (daily dates can't be
    ordered against the Day-2 measure). sia_early/sia_late are NA for the one
    event with no Day-2 follow-up. Returns one row per event:
    Pond ID, group, day0, day2, day3, res2/res3 (the Day-2/Day-3 outcomes as
    booleans), sia, sia_early, sia_late.
    """
    ev = pd.DataFrame({
        "Pond ID": events["Pond ID"],
        "group": events["Group"],
        "day0": pd.to_datetime(events[DAY0_COL]),
        "day2": pd.to_datetime(events[DAY2_COL]),
        "day3": pd.to_datetime(events[DAY3_COL]),
        "res2": events["1st FU WQ improvement"].eq("Yes"),
        "res3": events["2nd FU WQ improvement"].eq("Yes"),
    })

    def classify(e):
        a = actions[actions["Pond ID"] == e["Pond ID"]]
        full = _classify_overlap(a, e["day0"], e["day3"])
        if pd.isna(e["day2"]):
            return pd.Series([full, pd.NA, pd.NA])
        return pd.Series([
            full,
            _classify_overlap(a, e["day0"], e["day2"]),
            _classify_overlap(a, e["day2"] + pd.Timedelta(days=1), e["day3"]),
        ])

    ev[["sia", "sia_early", "sia_late"]] = ev.apply(classify, axis=1)
    return ev


def describe_sia_exposure(events: pd.DataFrame, actions: pd.DataFrame) -> None:
    """Print the per-event SIA exposure summary, by group (with blind labels)."""
    ev = event_sia_exposure(events, actions)
    table = pd.crosstab(ev["group"], ev["sia"]).reindex(
        columns=[c for c in ["exact", "possible", "none"] if c in ev["sia"].values]
    )
    table["events"] = table.sum(axis=1)
    exposed = table["events"] - table["none"]
    table["exposed"] = exposed
    table["pct_exposed"] = (exposed / table["events"] * 100).round(1)
    table.index = [f"{g} ({BLIND_LABEL[g]})" for g in table.index]

    _section("SELF-INITIATED ACTIONS — EVENT EXPOSURE (Day 0 .. Day-3 follow-up)",
             "(exact = action date inside the window; possible = only a",
             " range-dated action overlaps; exposed = exact + possible)")
    print(f"SIA records: {len(actions)} "
          f"(exact-dated {int((actions['basis'] == 'exact').sum())}, "
          f"range-dated {int((actions['basis'] == 'range').sum())}) "
          f"across {actions['Pond ID'].nunique()} ponds")
    print()
    print(table.to_string())
    print()


# sia levels counted as exposed; the sensitivity variants pass ("exact",),
# dropping "possible" events as ambiguous (unexposed is always "none").
EXPOSED = ("exact", "possible")


def resolution_by_exposure(ev: pd.DataFrame, exposed: tuple) -> pd.DataFrame:
    """Day-3 resolution, SIA-exposed vs unexposed events, within each group.

    Fisher's exact per group on the 2x2 [exposure x resolved]. `exposed` names
    the sia levels counted as exposed; unexposed is always "none", so any level
    left out (e.g. "possible" in the exact-only split) is excluded entirely.
    Returns one row per group: n/resolved/% for each arm, odds ratio, p.
    """
    rows = []
    for g, sub in ev.groupby("group"):
        e = sub[sub["sia"].isin(exposed)]
        u = sub[sub["sia"] == "none"]
        table = [[int(e["res3"].sum()), int((~e["res3"]).sum())],
                 [int(u["res3"].sum()), int((~u["res3"]).sum())]]
        odds, p = fisher_exact(table)
        rows.append({
            "group": f"{g} ({BLIND_LABEL[g]})",
            "exp_n": len(e), "exp_res": table[0][0],
            "exp_pct": round(table[0][0] / len(e) * 100, 1) if len(e) else float("nan"),
            "none_n": len(u), "none_res": table[1][0],
            "none_pct": round(table[1][0] / len(u) * 100, 1) if len(u) else float("nan"),
            "odds": round(odds, 3), "fisher_p": p,
        })
    return pd.DataFrame(rows).set_index("group")


def resolution_groups_by_stratum(ev: pd.DataFrame, exposed: tuple) -> pd.DataFrame:
    """The primary D-vs-E Day-3 resolution comparison, within each exposure stratum.

    Fisher's exact (Group D vs E) run separately on the SIA-exposed events and
    the unexposed ones. If the Treatment advantage holds in the unexposed
    stratum, it isn't explained by farmers' own actions. Returns one row per
    stratum: per-group n/resolved/%, odds ratio, p.
    """
    groups = sorted(ev["group"].unique())            # ["Control", "Treatment"]
    rows = []
    for stratum, levels in (("exposed", exposed), ("unexposed", ("none",))):
        sub = ev[ev["sia"].isin(levels)]
        row = {"stratum": stratum}
        table = []
        for g in groups:
            r = sub[sub["group"] == g]["res3"]
            table.append([int(r.sum()), int((~r).sum())])
            k = BLIND_LABEL[g].split()[-1]           # "D" / "E"
            row[f"n_{k}"] = len(r)
            row[f"res_{k}"] = int(r.sum())
            row[f"pct_{k}"] = round(r.mean() * 100, 1) if len(r) else float("nan")
        odds, p = fisher_exact(table)
        row["odds"], row["fisher_p"] = round(odds, 3), p
        rows.append(row)
    return pd.DataFrame(rows).set_index("stratum")


def describe_resolution_by_exposure(events: pd.DataFrame, actions: pd.DataFrame) -> None:
    """Print Day-3 resolution by SIA exposure: within-group, then D vs E by
    stratum, with the exact-only sensitivity condensed to one line."""
    ev = event_sia_exposure(events, actions)

    def show(df):
        disp = df.copy()
        disp["fisher_p"] = disp["fisher_p"].map(lambda v: f"{v:.3g}")
        print(disp.to_string())
        print()

    _section("SIA STEP 2 — DAY-3 RESOLUTION BY SIA EXPOSURE",
             "(post-hoc, descriptive: SIA is self-selected, not assigned;",
             " Fisher's exact throughout; exposed = exact + possible)")
    print("(a) exposed vs unexposed events, within each cohort:")
    show(resolution_by_exposure(ev, EXPOSED))
    print("(b) D vs E, within each exposure stratum:")
    show(resolution_groups_by_stratum(ev, EXPOSED))

    sens_a = resolution_by_exposure(ev, ("exact",))
    sens_b = resolution_groups_by_stratum(ev, ("exact",))
    print("Sensitivity (exact-dated exposure only, 'possible' events dropped):")
    print(f"  within-cohort p = {sens_a['fisher_p'].iloc[0]:.3g} (D) / "
          f"{sens_a['fisher_p'].iloc[1]:.3g} (E); D-vs-E p = "
          f"{sens_b.loc['exposed', 'fisher_p']:.3g} (exposed) / "
          f"{sens_b.loc['unexposed', 'fisher_p']:.3g} (unexposed)")
    print()


def timing_by_exposure(ev: pd.DataFrame, exposed: tuple) -> pd.DataFrame:
    """The §5 Day-2 vs Day-3 gained/lost split, by full-window SIA exposure.

    Events with both follow-ups only (57 of 58). gained = unresolved at Day 2,
    resolved at Day 3; lost = the reverse. Returns one row per group x stratum:
    n, day2_res, day3_res, gained, lost. Counts only — the inferential cut is
    gains_by_action_timing, which conditions on being unresolved at Day 2.
    """
    sub = ev.dropna(subset=["day2", "day3"])
    rows = []
    for g, gsub in sub.groupby("group"):
        for stratum, ssub in (("exposed", gsub[gsub["sia"].isin(exposed)]),
                              ("unexposed", gsub[gsub["sia"] == "none"])):
            d2, d3 = ssub["res2"], ssub["res3"]
            rows.append({
                "group": f"{g} ({BLIND_LABEL[g]})", "stratum": stratum,
                "n": len(ssub),
                "day2_res": int(d2.sum()), "day3_res": int(d3.sum()),
                "gained": int((~d2 & d3).sum()), "lost": int((d2 & ~d3).sum()),
            })
    return pd.DataFrame(rows).set_index(["group", "stratum"])


def gains_by_action_timing(ev: pd.DataFrame, exposed: tuple) -> pd.DataFrame:
    """Among events unresolved at Day 2: does a LATE action predict gaining?

    Only events still out of range at Day 2 can gain, so the analysis
    conditions on them ("at risk"). Each is classed by action timing:
      late        — an action window overlaps (Day 2, Day 3] (sia_late)
      early only  — actions overlap [Day 0, Day 2] but none late
      no action   — neither sub-window hit
    `exposed` sets which grades count (as in the step-2 splits). Fisher's
    exact tests gained vs not, late vs the rest. Returns one row per group:
    at_risk, n/gained per timing class, odds, fisher_p.
    """
    atrisk = ev.dropna(subset=["day2", "day3"])
    atrisk = atrisk[~atrisk["res2"]]
    rows = []
    for g, gsub in atrisk.groupby("group"):
        late = gsub["sia_late"].isin(exposed)
        early_only = ~late & gsub["sia_early"].isin(exposed)
        none = ~late & ~early_only
        gained = gsub["res3"]
        table = [[int((late & gained).sum()), int((late & ~gained).sum())],
                 [int((~late & gained).sum()), int((~late & ~gained).sum())]]
        odds, p = fisher_exact(table)
        rows.append({
            "group": f"{g} ({BLIND_LABEL[g]})", "at_risk": len(gsub),
            "late_n": int(late.sum()), "late_gain": table[0][0],
            "early_n": int(early_only.sum()),
            "early_gain": int((early_only & gained).sum()),
            "none_n": int(none.sum()), "none_gain": int((none & gained).sum()),
            "odds": round(odds, 3), "fisher_p": p,
        })
    return pd.DataFrame(rows).set_index("group")


def describe_timing_by_exposure(events: pd.DataFrame, actions: pd.DataFrame) -> None:
    """Print step 3: the Day-2->Day-3 gained/lost split by SIA exposure, and
    whether late actions (between the two follow-ups) predict the gains."""
    ev = event_sia_exposure(events, actions)

    _section("SIA STEP 3 — ARE THE DAY-3 GAINS ACTION-DRIVEN?",
             "(the Treatment effect appears between the Day-2 and Day-3",
             " follow-ups; if farmers' actions caused those gains, the actions",
             " should fall in that window. Events with both follow-ups only)")
    print("(a) gained/lost, by SIA exposure anywhere in Day 0 .. Day 3:")
    print(timing_by_exposure(ev, EXPOSED).to_string())
    print()

    print("(b) events still unresolved at Day 2, by action timing (late = after")
    print("    the Day-2 visit date; Fisher: gained x [late vs rest]):")
    disp = gains_by_action_timing(ev, EXPOSED)
    disp["fisher_p"] = disp["fisher_p"].map(lambda v: f"{v:.3g}")
    print(disp.to_string())
    print()

    sens = gains_by_action_timing(ev, ("exact",))
    print("Sensitivity (exact-dated actions only):")
    for g, r in sens.iterrows():
        print(f"  {g}: late {int(r['late_gain'])}/{int(r['late_n'])} gained vs "
              f"rest {int(r['early_gain'] + r['none_gain'])}/"
              f"{int(r['early_n'] + r['none_n'])}, Fisher p = {r['fisher_p']:.3g}")
    print()
