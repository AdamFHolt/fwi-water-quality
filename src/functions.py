import pandas as pd

def reorder_by_pond(src: str, dst: str) -> None:
    """Sort the Data sheet by Pond ID then chronologically, copying other sheets verbatim."""
    # Within a pond, sort by date then time so visits read oldest->newest,
    # Morning before Evening. Time is an "HH:MM" 24h string, so it sorts as text.
    data = pd.read_excel(src, sheet_name="Data").sort_values(
        ["Pond ID", "Date of data collection", "Time of data collection"], kind="stable"
    )

    # Other sheets: header=None keeps every cell exactly as-is.
    overview = pd.read_excel(src, sheet_name="Overview", header=None)
    oor = pd.read_excel(src, sheet_name="OOR Events", header=None)

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
    print("=" * 50)
    print("DATASET OVERVIEW")
    print("=" * 50)
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


# Water-quality reading columns present in this dataset.
WQ_PARAMS = ["DO (mg/L)", "pH", "Ammonia—NH3 (mg/L)"]


def wq_pond_means(data: pd.DataFrame) -> pd.DataFrame:
    """Baseline WQ as one row per pond: routine visits, averaged within pond.

    Drops follow-up visits (they are conditional on an OOR event, so a biased
    subsample) and collapses each pond to its mean so repeated visits within a
    pond aren't counted as independent observations (avoids pseudoreplication).
    Returns columns: Pond status, Pond ID, <WQ_PARAMS>.
    """
    routine = data[data["Is follow up"] == "No"]
    return routine.groupby(["Pond status", "Pond ID"])[WQ_PARAMS].mean().reset_index()


def describe_water_quality(data: pd.DataFrame) -> None:
    """Print baseline WQ mean/SD by group (routine visits, one value per pond)."""
    pond = wq_pond_means(data)
    stats = pond.groupby("Pond status")[WQ_PARAMS].agg(["mean", "std"]).round(3)
    n = pond.groupby("Pond status").size()

    print("=" * 50)
    print("WATER QUALITY — MEAN (SD) BY GROUP")
    print("(routine visits, averaged per pond)")
    print("=" * 50)
    print(stats.to_string())
    print()
    print(f"ponds per group: {n.to_dict()}")
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
    df = events.assign(_resolved=events["2nd FU WQ improvement"].eq("Yes"))

    def summarize(sub, parameter):
        out = sub.groupby("Group")["_resolved"].agg(events="size", resolved="sum")
        out["pct_resolved"] = (out["resolved"] / out["events"] * 100).round(1)
        return out.reset_index().rename(columns={"Group": "group"}).assign(parameter=parameter)

    rows = [summarize(df, "Overall")]
    rows += [
        summarize(df[df["OOR Parameter"].str.contains(p, case=False, na=False)], p)
        for p in OOR_DRIVERS
    ]
    return pd.concat(rows, ignore_index=True)[
        ["parameter", "group", "events", "resolved", "pct_resolved"]
    ]


def describe_resolution_by_parameter(events: pd.DataFrame) -> None:
    """Print resolution rate (Day-3 primary) overall and by OOR parameter, per group."""
    tidy = oor_resolution_by_parameter(events)
    groups = sorted(tidy["group"].unique())
    metrics = ["events", "resolved", "pct_resolved"]

    table = (
        tidy.pivot(index="parameter", columns="group", values=metrics)
        .reorder_levels([1, 0], axis=1)  # (group, metric)
        .reindex(columns=pd.MultiIndex.from_product([groups, metrics]))
        .reindex(["Overall"] + OOR_DRIVERS)
    )
    int_cols = [(g, m) for g in groups for m in ("events", "resolved")]
    table[int_cols] = table[int_cols].astype(int)

    print("=" * 50)
    print("OOR RESOLUTION BY PARAMETER (Day-3 primary)")
    print("(events flagging the parameter; multi-parameter events count in each)")
    print("=" * 50)
    print(table.to_string())
    print()


def analyze_oor_events(data: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Count and resolve OOR events from Data, cross-checking the OOR Events sheet.

    Prints (i) event counts per group derived from Data, (ii) a check against the
    OOR Events sheet, (iii) resolved # and % per group, and (iv) a check of those
    against the sheet's Day-3 primary measure (`2nd FU WQ improvement`).

    Events with no follow-up in the window (resolved is None) are excluded from
    the resolution rate; the denominator is events that had a follow-up.
    """
    derived = derive_oor_events(data)

    print("=" * 50)
    print("OOR EVENTS — DERIVED FROM DATA SHEET")
    print("=" * 50)

    # Resolution rate excludes no-follow-up events (resolved is None); a clean
    # bool subset also keeps mean()/sum() well-defined.
    followed = derived.dropna(subset=["resolved"]).copy()
    followed["resolved"] = followed["resolved"].astype(bool)
    g = followed.groupby("group")["resolved"]

    # (i) + (iii) counts and resolution per group from Data.
    summary = pd.DataFrame(
        {
            "oor_events": derived.groupby("group").size(),  # all detected events
            "with_followup": g.size(),                      # events with a follow-up
            "resolved": g.sum().astype(int),
            "pct_resolved": (g.mean() * 100).round(1),      # resolved / with_followup
        }
    )
    print(summary.to_string())
    print()

    # Reference figures from the OOR Events sheet.
    sheet_events = events["Group"].value_counts()
    sheet_resolved = (
        events.assign(res=events["2nd FU WQ improvement"] == "Yes")
        .groupby("Group")["res"]
        .sum()
    )

    # (ii)+(iv) cross-check derived counts against the OOR Events sheet.
    def _check(label, col, sheet):
        diffs = [
            f"{grp} (Data={a} Sheet={b})"
            for grp in summary.index
            for a, b in [(int(summary.loc[grp, col]), int(sheet.get(grp, 0)))]
            if a != b
        ]
        print(f"CHECK — {label}: {'OK' if not diffs else 'MISMATCH ' + ', '.join(diffs)}")

    _check("event counts vs sheet", "oor_events", sheet_events)
    _check("resolved counts vs sheet", "resolved", sheet_resolved)
    print()

    return derived



