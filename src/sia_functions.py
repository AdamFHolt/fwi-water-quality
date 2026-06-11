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
  describe_resolution_by_exposure  print both, under both exposure splits
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
    exact = pd.to_datetime(sia["Self-initiated actions implemented on (exact date)"])

    rows = []
    for (_, r), ex in zip(sia.iterrows(), exact):
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


def event_sia_exposure(events: pd.DataFrame, actions: pd.DataFrame) -> pd.DataFrame:
    """Flag each OOR event with its SIA exposure over [Day 0, Day-3 follow-up].

    Exposure is graded by how certain the timing is:
      exact    — an action with an exact implementation date inside the window
      possible — only range-dated actions whose window overlaps the event's
      none     — no action window overlaps
    Returns one row per event: Pond ID, group, day0, day2, day3,
    res2/res3 (the Day-2/Day-3 outcomes as booleans), sia.
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
        a = actions[(actions["Pond ID"] == e["Pond ID"])
                    & (actions["start"] <= e["day3"])
                    & (actions["end"] >= e["day0"])]
        if (a["basis"] == "exact").any():
            return "exact"
        return "possible" if len(a) else "none"

    ev["sia"] = ev.apply(classify, axis=1)
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


# sia levels counted as exposed under each split; unexposed is always "none",
# so the exact-only split drops "possible" events as ambiguous.
EXPOSURE_SPLITS = {
    "MAIN SPLIT: exposed = exact + possible": ("exact", "possible"),
    "SENSITIVITY: exposed = exact only ('possible' events dropped)": ("exact",),
}


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
    """Print Day-3 resolution by SIA exposure: within-group, then D vs E by stratum,
    under the main exposure split and the exact-only sensitivity."""
    ev = event_sia_exposure(events, actions)

    def show(df):
        disp = df.copy()
        disp["fisher_p"] = disp["fisher_p"].map(lambda v: f"{v:.3g}")
        print(disp.to_string())
        print()

    _section("SIA STEP 2 — DAY-3 RESOLUTION BY SIA EXPOSURE",
             "(post-hoc, descriptive: SIA is self-selected, not assigned;",
             " all tests Fisher's exact, event-level, Day-3 primary outcome)")
    for split_name, exposed in EXPOSURE_SPLITS.items():
        print(f"------------ {split_name} ------------")
        print()
        print("(a) Within each cohort: do SIA-exposed events resolve more often?")
        print("    (exp_* = exposed events, none_* = unexposed; Fisher compares the two)")
        show(resolution_by_exposure(ev, exposed))
        print("(b) Control vs Treatment within each stratum: does the cohort gap")
        print("    survive where no SIA occurred? (the primary D-vs-E test, stratified;")
        print("    D = Control, E = Treatment)")
        show(resolution_groups_by_stratum(ev, exposed))
