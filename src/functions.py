"""
Analysis functions for the FWI water-quality study. main.py calls these in order.

Rough reading order if you're going through this file:

  reorder_by_pond     write a Pond-ID-sorted copy of the workbook
  load_data/load_events   read the Data and OOR Events sheets

  describe_data       counts: visits, ponds, events, split by group
  wq_pond_means       one baseline row per pond (DO split AM/PM); most WQ
                      functions below build on this
  describe_water_quality   mean/SD per group
  levene_by_param     do the two groups have equal variance?
  wq_outliers         flag odd ponds (studentized residual + Cook's D)

  derive_oor_events   rebuild the OOR events from the raw visit rows
  oor_resolution_by_parameter   resolution rate by parameter, from the sheet
  oor_resolution_per_pond  one resolution proportion per pond (the per-pond unit)
  oor_resolution_by_pond   that, averaged within group (pond-level rate)
  analyze_oor_events  resolution rate (event- and pond-level) from the derived
                      events, plus a sanity check that they match the sheet

Two things to keep straight: the group column is "Pond status" in the Data
sheet but "Group" in the OOR Events sheet, and the resolution number always
means the Day-3 (primary) measure.
"""

import pandas as pd
from scipy.stats import levene


def _section(*lines: str) -> None:
    """Print a titled section header between === banners."""
    print("=" * 50)
    for line in lines:
        print(line)
    print("=" * 50)


def reorder_by_pond(src: str, dst: str) -> None:
    """Sort the Data sheet by Pond ID then chronologically, copying other sheets verbatim."""
    # Other sheets in one read; header=None keeps every cell exactly as-is.
    others = pd.read_excel(src, sheet_name=["Overview", "OOR Events"], header=None)
    overview, oor = others["Overview"], others["OOR Events"]

    # Within a pond, sort by date then time so visits read oldest->newest,
    # Morning before Evening. Time is an "HH:MM" 24h string, so it sorts as text.
    data = pd.read_excel(src, sheet_name="Data").sort_values(
        ["Pond ID", "Date of data collection", "Time of data collection"], kind="stable"
    )

    with pd.ExcelWriter(dst) as writer:
        overview.to_excel(writer, sheet_name="Overview", index=False, header=False)
        data.to_excel(writer, sheet_name="Data", index=False)
        oor.to_excel(writer, sheet_name="OOR Events", index=False, header=False)


def load_data(path: str) -> pd.DataFrame:
    """Load the Data sheet from the workbook."""
    return pd.read_excel(path, sheet_name="Data")


def load_events(path: str) -> pd.DataFrame:
    """Load the OOR-event sheet from the workbook."""
    return pd.read_excel(path, sheet_name="OOR Events")


def describe_data(data: pd.DataFrame, events: pd.DataFrame) -> None:
    """Print a basic overview of the loaded dataset."""
    _section("DATASET OVERVIEW")
    print(f"Visits: {len(data)} rows x {data.shape[1]} cols")
    print(f"Unique ponds: {data['Pond ID'].nunique()}")
    print(f"OOR events: {len(events)}")
    print()
    print("Visits by group:")
    print(data["Pond status"].value_counts().to_string())
    print()
    print("OOR events by group:")
    print(events["Group"].value_counts().to_string())
    print()


# Pond-level parameter names after splitting DO by time of day.
POND_PARAMS = ["DO Morning (mg/L)", "DO Evening (mg/L)", "pH", "Ammonia—NH3 (mg/L)"]


def wq_pond_means(data: pd.DataFrame) -> pd.DataFrame:
    """Baseline WQ as one row per pond: routine visits, averaged within pond.

    Drops follow-up visits (they are conditional on an OOR event, so a biased
    subsample) and collapses each pond to its mean so repeated visits within a
    pond aren't counted as independent observations (avoids pseudoreplication).
    DO is split by time of day (morning and evening differ by ~8 mg/L) and
    returned as two columns. pH and ammonia are averaged over all routine visits.
    Returns columns: Pond status, Pond ID, <POND_PARAMS>.
    """
    routine = data[data["Is follow up"] == "No"]
    do_am = (routine[routine["Type"] == "Morning"]
             .groupby(["Pond status", "Pond ID"])["DO (mg/L)"].mean()
             .rename("DO Morning (mg/L)"))
    do_pm = (routine[routine["Type"] == "Evening"]
             .groupby(["Pond status", "Pond ID"])["DO (mg/L)"].mean()
             .rename("DO Evening (mg/L)"))
    other = routine.groupby(["Pond status", "Pond ID"])[["pH", "Ammonia—NH3 (mg/L)"]].mean()
    return pd.concat([do_am, do_pm, other], axis=1).reset_index()


def describe_water_quality(data: pd.DataFrame) -> None:
    """Print baseline WQ mean/SD by group (routine visits, one value per pond)."""
    pond = wq_pond_means(data)
    stats = pond.groupby("Pond status")[POND_PARAMS].agg(["mean", "std"]).round(3)
    n = pond.groupby("Pond status").size()

    _section("WATER QUALITY — MEAN (SD) BY GROUP",
             "(routine visits, averaged per pond; DO split by time of day)")
    print(stats.to_string())
    print()
    print(f"ponds per group: {n.to_dict()}")
    print()


def levene_by_param(data: pd.DataFrame, exclude: set | None = None) -> pd.DataFrame:
    """Levene's variance-homogeneity test (Group D vs E) per WQ parameter.

    Uses the per-pond baseline values (see wq_pond_means) so ponds aren't
    pseudo-replicated. Median-centred (Brown-Forsythe), robust to non-normality.
    Pass `exclude` (a set of Pond IDs, e.g. the WQ outliers) to run on the
    outlier-removed set. Returns a DataFrame indexed by parameter with columns
    W (statistic) and p.
    """
    pond = wq_pond_means(data)
    if exclude:
        pond = pond[~pond["Pond ID"].isin(exclude)]
    groups = sorted(pond["Pond status"].unique())
    rows = {}
    for param in POND_PARAMS:
        samples = [pond.loc[pond["Pond status"] == g, param].dropna() for g in groups]
        w, p = levene(*samples)
        rows[param] = {"W": round(w, 3), "p": round(p, 3)}
    return pd.DataFrame(rows).T


def describe_variance_homogeneity(data: pd.DataFrame) -> None:
    """Print Levene's variance-homogeneity test (Group D vs E) per WQ parameter."""
    _section("VARIANCE HOMOGENEITY — LEVENE (Group D vs E)",
             "(per-pond baseline values; p > 0.05 = equal variance)")
    print(levene_by_param(data).to_string())
    print()


def wq_outliers(data: pd.DataFrame, resid_thresh: float = 2.0) -> pd.DataFrame:
    """Flag baseline-WQ outliers/influential ponds from the group-means model.

    For each parameter, fits param ~ group on per-pond values and computes each
    pond's internally studentized residual and Cook's distance. A pond is an
    *outlier* if |studentized resid| > resid_thresh, *influential* if Cook's D >
    4/n. NB: with a two-group factor, leverage is constant within a group
    (= 1/n_group), so Cook's D is essentially a function of the residual here.
    Returns only the flagged ponds (tidy).
    """
    pond = wq_pond_means(data)
    out = []
    for param in POND_PARAMS:
        df = pond[["Pond status", "Pond ID", param]].dropna().rename(columns={param: "value"})
        n, p = len(df), df["Pond status"].nunique()
        gmean = df.groupby("Pond status")["value"].transform("mean")
        h = 1 / df.groupby("Pond status")["value"].transform("size")  # leverage = 1/n_group
        resid = df["value"] - gmean
        s2 = (resid ** 2).sum() / (n - p)  # residual variance (model MSE)
        std = resid / (s2 * (1 - h)) ** 0.5  # internally studentized residual
        df["std_resid"] = std.round(2)
        df["cooks_d"] = ((std ** 2 / p) * (h / (1 - h))).round(3)
        df["outlier"] = df["std_resid"].abs() > resid_thresh
        df["influential"] = df["cooks_d"] > 4 / n
        out.append(df.assign(parameter=param))
    res = pd.concat(out, ignore_index=True)
    cols = ["parameter", "Pond status", "Pond ID", "value", "std_resid", "cooks_d", "outlier", "influential"]
    return res[res["outlier"] | res["influential"]][cols]


def describe_wq_outliers(data: pd.DataFrame) -> None:
    """Print baseline-WQ outliers and influential ponds (group-means model)."""
    flagged = wq_outliers(data)
    _section("WATER QUALITY OUTLIERS / INFLUENCE (per-pond, param ~ group)",
             "(|studentized residual| > 2; Cook's D > 4/n)")
    print("None flagged." if flagged.empty else flagged.to_string(index=False))
    print()


def derive_oor_events(data: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct OOR events and their resolution from the per-visit Data sheet.

    - An OOR *event* is a Day-0 detection: a first visit, found out of range.
    - Morning + Evening rows on the same pond-day are one event, so collapsed on
      (Pond ID, date). 
    - Whether resolved uses the V7 TRIAD primary measure (Day 3): the
      latest follow-up visit for that pond within 5 days of Day 0, counted resolved
      if `Is WQ in range?` is Yes for every visit on that day. 
    - This reproduces the `OOR Events` sheet's `2nd FU WQ improvement` exactly

    Returns one row per event with columns: Pond ID, date, group, resolved (bool).
    """
    data = data.copy()
    data["date"] = pd.to_datetime(data["Date of data collection"])              # convert dates to pd timestamps
    day0 = (data["Is WQ in range?"] == "No") & (data["Is follow up"] == "No")   # identify Day-0 OOR detections (boolean mask)

    # Build the event list from the Day-0 OOR detections: one row per event,
    # collapsing each pond-day's Morning+Evening rows into (Pond ID, date, group).
    events = (
        data[day0]
        .groupby(["Pond ID", "date"])
        .agg(group=("Pond status", "first"))
        .reset_index()
    )

    # Per-day resolution lookup from follow-up visits: for each (pond, date),
    # inrange is True only if EVERY reading that day is in range (strict .all()).
    fu = data[data["Is follow up"] == "Yes"]
    fu_day = (
        fu.groupby(["Pond ID", "date"])
        .agg(inrange=("Is WQ in range?", lambda s: (s == "Yes").all()))
        .reset_index()
    )

    # Resolve one event: among this pond's follow-ups in the window (Day0, Day0+5],
    # take the latest (the Day-3 primary measure) and return whether it was in range.
    # Assumes a pond's OOR events are >5 days apart, so every follow-up in the window
    # belongs to this event (verified: min same-pond gap is 12 days). If two events
    # fell within 5 days, the earlier one could absorb the later's follow-ups.
    def resolve(row):
        cand = fu_day[
            (fu_day["Pond ID"] == row["Pond ID"])
            & (fu_day["date"] > row["date"])
            & (fu_day["date"] <= row["date"] + pd.Timedelta(days=5))
        ]
        if cand.empty:
            return None
        # most recent follow-up = Day-3 measure (not Day-2)
        return bool(cand.sort_values("date").iloc[-1]["inrange"])

    # run resolve() on each event row. Gives True/False/None per event
    events["resolved"] = events.apply(resolve, axis=1)
    return events


# Parameters that can trigger an OOR event.
OOR_DRIVERS = ["DO", "pH", "Ammonia"]


def oor_resolution_by_parameter(events: pd.DataFrame) -> pd.DataFrame:
    """Resolution rate (Day-3 primary) by OOR parameter and group.

    "Resolved" is the event's overall Day-3 outcome (`2nd FU WQ improvement` ==
    "Yes"); the sheet has no per-parameter outcome, so this is the share of
    events *involving* each parameter that resolved. Events listing several
    parameters (e.g. "DO, pH") count toward each. The "Overall" row uses all
    events. Returns tidy rows: parameter, group, events, resolved, pct_resolved.
    """
    df = events.dropna(subset=["2nd FU WQ improvement"]).assign(
        _resolved=lambda x: x["2nd FU WQ improvement"].eq("Yes")
    )

    def summarize(sub, parameter):
        out = sub.groupby("Group")["_resolved"].agg(events="size", resolved="sum")
        out["pct_resolved"] = (out["resolved"] / out["events"] * 100).round(1)
        return out.reset_index().rename(columns={"Group": "group"}).assign(parameter=parameter)

    rows = [summarize(df, "Overall")]
    rows += [
        summarize(df[df["OOR Parameter"].str.contains(p, na=False)], p)
        for p in OOR_DRIVERS
    ]
    return pd.concat(rows, ignore_index=True)[
        ["parameter", "group", "events", "resolved", "pct_resolved"]
    ]


def describe_resolution_by_parameter(events: pd.DataFrame) -> None:
    """Print resolution rate (Day-3 primary) overall and by OOR parameter, per group."""
    tidy = oor_resolution_by_parameter(events)
    order = ["Overall"] + OOR_DRIVERS
    # Lay the tidy rows out group-major: each group's metrics side by side.
    table = pd.concat(
        {g: sub.set_index("parameter").reindex(order)[["events", "resolved", "pct_resolved"]]
         for g, sub in tidy.groupby("group")},
        axis=1,
    )

    _section("OOR RESOLUTION BY PARAMETER (Day-3 primary)",
             "(events flagging the parameter; multi-parameter events count in each)")
    print(table.to_string())
    print()


def oor_resolution_per_pond(derived: pd.DataFrame) -> pd.DataFrame:
    """One row per pond: its events, resolved count, and Day-3 resolution proportion.

    Collapses each pond to its share of OOR events resolved (mean of the 0/1
    `resolved` flag) — the per-pond unit used to guard against repeat-event ponds
    dominating the event-level rate (events within a pond aren't independent), the
    same per-pond move as `wq_pond_means` for baseline WQ. Takes the derived
    events; no-follow-up events (resolved is None) are dropped first. Returns
    tidy rows: group, Pond ID, events, resolved, proportion.
    """
    followed = derived.dropna(subset=["resolved"]).copy()
    followed["resolved"] = followed["resolved"].astype(int)
    per_pond = followed.groupby(["group", "Pond ID"])["resolved"].agg(
        events="size", resolved="sum"
    )
    per_pond["proportion"] = per_pond["resolved"] / per_pond["events"]
    return per_pond.reset_index()


def oor_resolution_by_pond(derived: pd.DataFrame) -> pd.DataFrame:
    """Pond-level resolution summary: per-pond proportions averaged within group.

    Builds on `oor_resolution_per_pond`, so every pond counts once regardless of
    how many events it had. `mean_pct` is the unweighted mean of the per-pond
    percentages (not the same as the overall event rate); `median_pct` is their
    median. Returns per-group: ponds, events, mean_pct, median_pct.
    """
    g = oor_resolution_per_pond(derived).groupby("group")
    return pd.DataFrame(
        {
            "ponds": g.size(),
            "events": g["events"].sum(),
            "mean_pct": (g["proportion"].mean() * 100).round(1),
            "median_pct": (g["proportion"].median() * 100).round(1),
        }
    )


def analyze_oor_events(data: pd.DataFrame, events: pd.DataFrame) -> None:
    """Count and resolve OOR events reconstructed from the per-visit Data sheet.

    Prints the Day-3 resolution rate per group two ways — event-level (each OOR
    event counts once) and pond-level (each pond counts once, removing the
    repeat-pond weighting) — then cross-checks the derived counts against the
    OOR Events sheet (the authoritative source). Raises AssertionError if they
    disagree.
    """
    derived = derive_oor_events(data)

    _section("OOR EVENTS — DERIVED FROM DATA SHEET")

    # Resolution rate excludes no-follow-up events (resolved is None); a clean
    # bool subset also keeps mean()/sum() well-defined.
    followed = derived.dropna(subset=["resolved"]).copy()
    followed["resolved"] = followed["resolved"].astype(bool)
    g = followed.groupby("group")["resolved"]

    summary = pd.DataFrame(
        {
            "oor_events": derived.groupby("group").size(),  # all detected events
            "with_followup": g.size(),                      # events with a follow-up
            "resolved": g.sum().astype(int),
            "pct_resolved": (g.mean() * 100).round(1),      # resolved / with_followup
        }
    )
    print("Event-level (each OOR event counts once):")
    print(summary.to_string())
    print()

    # Pond-level: one proportion per pond, then averaged — guards against
    # repeat-event ponds dominating the event-level rate (pseudoreplication).
    print("Pond-level (each pond counts once; mean_pct = mean of per-pond rates):")
    print(oor_resolution_by_pond(derived).to_string())
    print()

    # Cross-check: derived counts must match OOR Events sheet exactly.
    sheet = events.dropna(subset=["2nd FU WQ improvement"]).groupby("Group")["2nd FU WQ improvement"]
    sheet_n = sheet.size()
    sheet_res = sheet.apply(lambda s: s.eq("Yes").sum())
    for grp in sheet_n.index:
        dg = followed[followed["group"] == grp]
        assert len(dg) == sheet_n[grp] and dg["resolved"].sum() == sheet_res[grp], (
            f"Mismatch for {grp}: derived ({len(dg)}, {int(dg['resolved'].sum())}) "
            f"vs sheet ({sheet_n[grp]}, {sheet_res[grp]})"
        )



