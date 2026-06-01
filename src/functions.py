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


def analyze_oor_events(data: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Count and resolve OOR events from Data, cross-checking the OOR Events sheet.

    Prints (i) event counts per group derived from Data, (ii) a check against the
    OOR Events sheet, (iii) resolved # and % per group, and (iv) a check of those
    against the sheet's Day-3 primary measure (`2nd FU WQ improvement`).
    """
    derived = derive_oor_events(data)

    print("=" * 50)
    print("OOR EVENTS — DERIVED FROM DATA SHEET")
    print("=" * 50)

    # (i) + (iii) counts and resolution per group from Data.
    g = derived.groupby("group")["resolved"]

    summary = pd.DataFrame(
        {
            "oor_events": g.size(),
            "resolved": g.sum().astype(int),
            "pct_resolved": (g.mean() * 100).round(1),
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

    # (ii) event counts agree?
    print("CHECK — event counts vs OOR Events sheet:")
    for grp in summary.index:
        a, b = int(summary.loc[grp, "oor_events"]), int(sheet_events.get(grp, 0))
        print(f"  {grp}: Data={a}  Sheet={b}  {'OK' if a == b else 'MISMATCH'}")

    # (iv) resolved counts agree?
    print("CHECK — resolved counts vs OOR Events sheet (Day-3 primary):")
    for grp in summary.index:
        a, b = int(summary.loc[grp, "resolved"]), int(sheet_resolved.get(grp, 0))
        print(f"  {grp}: Data={a}  Sheet={b}  {'OK' if a == b else 'MISMATCH'}")
    print()

    return derived



