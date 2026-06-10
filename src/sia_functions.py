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
"""

import re

import pandas as pd

from src.functions import _section

# The OOR Events sheet's date columns (the Day-0 header contains newlines).
DAY0_COL = "\nDate Initial OOR\n(Day 0)"
DAY2_COL = "Date 1st FU (day 2)"
DAY3_COL = "Date 2nd FU (day 3)"


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
    """Print the per-event SIA exposure summary, by group."""
    ev = event_sia_exposure(events, actions)
    table = pd.crosstab(ev["group"], ev["sia"]).reindex(
        columns=[c for c in ["exact", "possible", "none"] if c in ev["sia"].values]
    )
    _section("SELF-INITIATED ACTIONS — EVENT EXPOSURE (Day 0 .. Day-3 follow-up)",
             "(exact = action date inside the window; possible = only a",
             " range-dated action overlaps; none = no overlap)")
    print(f"SIA records: {len(actions)} "
          f"(exact-dated {int((actions['basis'] == 'exact').sum())}, "
          f"range-dated {int((actions['basis'] == 'range').sum())}) "
          f"across {actions['Pond ID'].nunique()} ponds")
    print()
    print(table.to_string())
    print()
