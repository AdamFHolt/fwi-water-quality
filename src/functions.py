"""Analysis functions for the FWI water-quality study; main.py calls these in order.

Two gotchas: the group column is "Pond status" in the Data sheet but "Group" in
the OOR Events sheet, and "resolution" always means the Day-3 (primary) measure.
"""

import pandas as pd
from scipy.stats import levene, ttest_ind, fisher_exact, mannwhitneyu, binomtest


def _section(*lines: str) -> None:
    """Print a titled section header between === banners."""
    print("=" * 50)
    for line in lines:
        print(line)
    print("=" * 50)


def reorder_by_pond(src: str, dst: str) -> None:
    """Sort the Data sheet by Pond ID then chronologically, copying other sheets verbatim."""
    # header=None: these two sheets are copied verbatim, no header parsing.
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
    """Baseline WQ as one row per pond: routine visits only, averaged within pond.

    Follow-ups are dropped (biased subsample) and each pond collapsed to its mean
    (avoids pseudoreplication). DO is split into Morning/Evening columns; pH and
    ammonia are single averages. Columns: Pond status, Pond ID, <POND_PARAMS>.
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


def baseline_balance_by_param(data: pd.DataFrame, exclude: set | None = None) -> pd.DataFrame:
    """Baseline balance (Group D vs E) per WQ parameter, on per-pond values.

    Levene's W/p (variance homogeneity, median-centred) and Hedges' g
    (standardized mean difference, small-sample corrected); both descriptive.
    `exclude` (a set of Pond IDs) drops those ponds first. Indexed by parameter,
    columns W, p, g.
    """
    pond = wq_pond_means(data)
    if exclude:
        pond = pond[~pond["Pond ID"].isin(exclude)]
    groups = sorted(pond["Pond status"].unique())
    rows = {}
    for param in POND_PARAMS:
        a, b = (pond.loc[pond["Pond status"] == g, param].dropna() for g in groups)
        w, p = levene(a, b)
        na, nb = len(a), len(b)
        pooled_sd = (((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2)) ** 0.5
        d = (a.mean() - b.mean()) / pooled_sd
        g = d * (1 - 3 / (4 * (na + nb) - 9))  # Hedges' small-sample correction
        rows[param] = {"W": round(w, 3), "p": round(p, 3), "g": round(g, 3)}
    return pd.DataFrame(rows).T


def describe_baseline_balance(data: pd.DataFrame) -> None:
    """Print baseline balance (Group D vs E) per WQ parameter: Levene W/p + Hedges' g."""
    _section("BASELINE BALANCE (Group D vs E)",
             "(per-pond values; Levene p > 0.05 = equal variance; |g| < 0.1 = negligible mean gap)")
    print(baseline_balance_by_param(data).to_string())
    print()


def wq_outliers(data: pd.DataFrame, resid_thresh: float = 2.0) -> pd.DataFrame:
    """Flag baseline-WQ outlier ponds, per parameter, against the group mean.

    Computes each pond's internally studentized residual and flags it when the
    absolute value exceeds `resid_thresh`. Returns only the flagged ponds.
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
        df["outlier"] = df["std_resid"].abs() > resid_thresh
        out.append(df.assign(parameter=param))
    res = pd.concat(out, ignore_index=True)
    cols = ["parameter", "Pond status", "Pond ID", "value", "std_resid", "outlier"]
    return res[res["outlier"]][cols]


def describe_wq_outliers(data: pd.DataFrame) -> None:
    """Print baseline-WQ outlier ponds (group-means model)."""
    flagged = wq_outliers(data)
    _section("WATER QUALITY OUTLIERS (per-pond)",
             "(|studentized residual| > 2 from group mean)")
    print("None flagged." if flagged.empty else flagged.to_string(index=False))
    print()


def derive_oor_events(data: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct OOR events and Day-3 resolution from the per-visit Data sheet.

    An event is a Day-0 detection (first visit out of range), with same-day
    Morning+Evening rows collapsed to one (Pond ID, date). Resolution is the V7
    TRIAD Day-3 measure: the latest follow-up within 5 days, resolved if every
    reading that day is in range. Reproduces the sheet's `2nd FU WQ improvement`.
    Returns one row per event: Pond ID, date, group, resolved (bool).
    """
    data = data.copy()
    data["date"] = pd.to_datetime(data["Date of data collection"])
    day0 = (data["Is WQ in range?"] == "No") & (data["Is follow up"] == "No")

    # Same-day Morning+Evening detections collapse to one (Pond ID, date) row.
    events = (
        data[day0]
        .groupby(["Pond ID", "date"])
        .agg(group=("Pond status", "first"))
        .reset_index()
    )

    # Per-day lookup over follow-up visits: a pond-day is in range only if
    # every reading that day is.
    fu = data[data["Is follow up"] == "Yes"]
    fu_day = (
        fu.groupby(["Pond ID", "date"])
        .agg(inrange=("Is WQ in range?", lambda s: (s == "Yes").all()))
        .reset_index()
    )

    # Latest follow-up in (Day0, Day0+5] is the Day-3 primary measure. The window
    # can't bleed into a later event's follow-ups: same-pond events are at least
    # 12 days apart in this dataset.
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

    Collapses each pond to its share of events resolved (the per-pond unit, so
    repeat-event ponds don't dominate the event-level rate). No-follow-up events
    are dropped. Returns tidy rows: group, Pond ID, events, resolved, proportion.
    """
    followed = derived.dropna(subset=["resolved"]).copy()
    followed["resolved"] = followed["resolved"].astype(int)
    per_pond = followed.groupby(["group", "Pond ID"])["resolved"].agg(
        events="size", resolved="sum"
    )
    per_pond["proportion"] = per_pond["resolved"] / per_pond["events"]
    return per_pond.reset_index()


def oor_resolution_by_pond(derived: pd.DataFrame) -> pd.DataFrame:
    """Pond-level resolution: per-pond proportions averaged within group.

    Every pond counts once (builds on `oor_resolution_per_pond`). `mean_pct` is
    the unweighted mean of per-pond rates, `median_pct` their median. Per group:
    ponds, events, mean_pct, median_pct.
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
    """Print Day-3 resolution per group, event-level and pond-level.

    Cross-checks the derived counts against the OOR Events sheet (authoritative)
    and raises AssertionError if they disagree.
    """
    derived = derive_oor_events(data)

    _section("OOR EVENTS — DERIVED FROM DATA SHEET")

    # Events that never got a follow-up (resolved is None) drop out of the rate.
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


# ---------------------------------------------------------------------------
# Comparative tests: does the intervention improve WQ?
#   resolution_fisher        Fisher's exact on the binary Day-3 outcome
#   oor_event_improvements   per-event distance-to-range closed, Day 0 -> Day 3
#   improvement_tests        independent Welch t + Mann-Whitney U on improvement
# ---------------------------------------------------------------------------

# In-range bands from protocol V7 Table 1: (low, high); None = unbounded that
# side. DO's band depends on time of day; ammonia is one-sided (upper only).
# Verified to reproduce the dataset's `Is WQ in range?` flag exactly (998/998).
WQ_BANDS = {
    "DO Morning": (3, 5),
    "DO Evening": (8, 12),
    "pH": (6.5, 8.5),
    "Ammonia": (None, 0.05),
}


def _range_distance(x: float, lo: float | None, hi: float | None) -> float:
    """How far x sits outside [lo, hi] (0 if inside, NaN if x is NaN)."""
    if pd.isna(x):
        return float("nan")
    d = 0.0
    if lo is not None and x < lo:
        d = lo - x
    if hi is not None and x > hi:
        d = max(d, x - hi)
    return d


def _pond_day_distances(rows: pd.DataFrame) -> dict:
    """Worst (max) distance-to-range per parameter over one pond-day's visits.

    Takes the max across the day's Morning/Evening rows so a parameter reads
    distance 0 only when every reading that day is in range — matching the
    all-readings-in-range rule used for resolution. DO uses the time-of-day band.
    """
    do, ph, nh = [], [], []
    for _, r in rows.iterrows():
        band = WQ_BANDS["DO Morning"] if r["Type"] == "Morning" else WQ_BANDS["DO Evening"]
        do.append(_range_distance(r["DO (mg/L)"], *band))
        ph.append(_range_distance(r["pH"], *WQ_BANDS["pH"]))
        nh.append(_range_distance(r["Ammonia—NH3 (mg/L)"], *WQ_BANDS["Ammonia"]))

    def mx(v):
        v = [d for d in v if not pd.isna(d)]
        return max(v) if v else float("nan")

    return {"DO": mx(do), "pH": mx(ph), "Ammonia": mx(nh)}


def oor_event_improvements(data: pd.DataFrame) -> pd.DataFrame:
    """Per-parameter WQ improvement toward the band for each OOR event.

    For each event and each parameter out of range at Day 0, takes the
    distance-to-range at Day 0 minus at the Day-3 follow-up (improvement, native
    units, +ve = toward range). Same window rule as derive_oor_events. One row per
    (event, OOR parameter) with a Day-3 reading: Pond ID, group, date, parameter,
    dist0, dist3, improvement.
    """
    data = data.copy()
    data["date"] = pd.to_datetime(data["Date of data collection"])
    day0 = (data["Is WQ in range?"] == "No") & (data["Is follow up"] == "No")
    events = (
        data[day0]
        .groupby(["Pond ID", "date"])
        .agg(group=("Pond status", "first"))
        .reset_index()
    )
    fu = data[data["Is follow up"] == "Yes"]

    rows = []
    for _, e in events.iterrows():
        d0 = _pond_day_distances(
            data[(data["Pond ID"] == e["Pond ID"]) & (data["date"] == e["date"])]
        )
        cand = fu[
            (fu["Pond ID"] == e["Pond ID"])
            & (fu["date"] > e["date"])
            & (fu["date"] <= e["date"] + pd.Timedelta(days=5))
        ]
        if cand.empty:
            continue
        d3 = _pond_day_distances(cand[cand["date"] == cand["date"].max()])
        for p in OOR_DRIVERS:
            if pd.isna(d0[p]) or d0[p] <= 0:  # parameter wasn't OOR at Day 0
                continue
            if pd.isna(d3[p]):  # parameter not measured at the Day-3 follow-up
                continue
            imp = d0[p] - d3[p]
            rows.append({
                "Pond ID": e["Pond ID"], "group": e["group"], "date": e["date"],
                "parameter": p, "dist0": d0[p], "dist3": d3[p],
                "improvement": imp,
            })
    return pd.DataFrame(rows)


def improvement_tests(data: pd.DataFrame, exclude: set | None = None) -> pd.DataFrame:
    """Welch t + Mann-Whitney U on OOR improvement, Group D vs E, per parameter.

    Pond-level (each pond's mean over its events, so ponds aren't
    pseudo-replicated); two tests for robustness to the small-n normality
    assumption. `exclude` drops those Pond IDs first (sensitivity variant).
    Returns tidy rows: parameter, n_D, mean_D, n_E, mean_E, t, t_p, U, u_p.
    """
    imp = oor_event_improvements(data)
    if exclude:
        imp = imp[~imp["Pond ID"].isin(exclude)]
    groups = sorted(imp["group"].unique())       # ["Group D", "Group E"]
    ka, kb = (g.split()[-1] for g in groups)     # column suffixes: "D", "E"
    rows = []

    for p in OOR_DRIVERS:
        pond = (imp[imp["parameter"] == p]
                .groupby(["group", "Pond ID"])["improvement"].mean().reset_index())
        a, b = (pond.loc[pond["group"] == g, "improvement"] for g in groups)
        t, t_p = ttest_ind(a, b, equal_var=False)
        u, u_p = mannwhitneyu(a, b, alternative="two-sided")
        rows.append({
            "parameter": p,
            f"n_{ka}": len(a), f"mean_{ka}": round(a.mean(), 3),
            f"n_{kb}": len(b), f"mean_{kb}": round(b.mean(), 3),
            "t": round(t, 3), "t_p": t_p,
            "U": round(u, 1), "u_p": u_p,
        })
    return pd.DataFrame(rows)


def describe_improvement_tests(data: pd.DataFrame, exclude: set | None = None) -> None:
    """Print the independent improvement tests (Welch t + Mann-Whitney U), D vs E."""
    note = " — baseline-WQ outliers removed" if exclude else ""
    _section(
        f"OOR IMPROVEMENT — INDEPENDENT TESTS (Group D vs E){note}",
        "(pond-level; improvement = distance-to-range closed, native units;",
        " +mean = more improvement.",
        " t = Welch t [means], t_p its p; U = Mann-Whitney [ranks], u_p its p)",
    )
    disp = improvement_tests(data, exclude=exclude)
    for col in ("t_p", "u_p"):
        disp[col] = disp[col].map(lambda v: f"{v:.3g}")
    print(disp.to_string(index=False))
    print()


def resolution_fisher(events: pd.DataFrame, exclude: set | None = None,
                      col: str = "2nd FU WQ improvement"):
    """Fisher's exact test on Day-3 resolution (resolved vs not), Group D vs E.

    Event-level (the protocol's primary-outcome unit). `exclude` drops those
    ponds' events; `col` selects a different follow-up (e.g. `1st FU WQ
    improvement` for Day 2). Returns (table, odds_ratio, p); table is the 2x2
    [group x outcome], columns ordered resolved, unresolved.
    """
    e = events.dropna(subset=[col])
    if exclude:
        e = e[~e["Pond ID"].isin(exclude)]
    outcome = e[col].map({"Yes": "resolved", "No": "unresolved"})
    table = pd.crosstab(e["Group"], outcome)[["resolved", "unresolved"]]
    odds, p = fisher_exact(table.values)
    return table, odds, p


def describe_resolution_fisher(events: pd.DataFrame, exclude: set | None = None) -> None:
    """Print Fisher's exact test on the Day-3 resolution outcome (Group D vs E)."""
    table, odds, p = resolution_fisher(events, exclude=exclude)
    pct = (table["resolved"] / table.sum(axis=1) * 100).round(1)
    note = " — baseline-WQ outliers removed" if exclude else ""
    _section(
        f"OOR RESOLUTION — FISHER'S EXACT (Group D vs E){note}",
        "(event-level Day-3 primary outcome; resolved = back in range)",
    )
    print(table.to_string())
    print()
    print(f"% resolved: {pct.to_dict()}")
    print(f"odds ratio = {odds:.3f}   p = {p:.3g}")
    print()


def resolution_day2_vs_day3(events: pd.DataFrame, exclude: set | None = None) -> pd.DataFrame:
    """Day-2 vs Day-3 resolution within events (McNemar), protocol §4.4.

    The same events measured twice (1st/2nd FU), so paired binary data. Restricted
    to events with both follow-ups; `exclude` drops those Pond IDs first. Per
    group: resolved counts/% each day, the discordant pairs `gained` (No->Yes) and
    `lost` (Yes->No), and `mcnemar_p` (exact two-sided binomial on those pairs).
    """
    e = events.dropna(subset=["1st FU WQ improvement", "2nd FU WQ improvement"])
    if exclude:
        e = e[~e["Pond ID"].isin(exclude)]
    rows = []
    for g, sub in e.groupby("Group"):
        d2 = sub["1st FU WQ improvement"].eq("Yes")
        d3 = sub["2nd FU WQ improvement"].eq("Yes")
        gained = int((~d2 & d3).sum())  # unresolved at Day 2, resolved by Day 3
        lost = int((d2 & ~d3).sum())    # resolved at Day 2, not at Day 3
        disc = gained + lost
        p = binomtest(lost, disc, 0.5).pvalue if disc else 1.0  # exact McNemar
        rows.append({
            "group": g, "n": len(sub),
            "day2_res": int(d2.sum()), "day2_pct": round(d2.mean() * 100, 1),
            "day3_res": int(d3.sum()), "day3_pct": round(d3.mean() * 100, 1),
            "gained": gained, "lost": lost, "mcnemar_p": p,
        })
    return pd.DataFrame(rows).set_index("group")


def describe_resolution_day2_vs_day3(events: pd.DataFrame, exclude: set | None = None) -> None:
    """Print the Day-2 vs Day-3 resolution comparison (McNemar, per group)."""
    res = resolution_day2_vs_day3(events, exclude=exclude)
    disp = res.copy()
    disp["mcnemar_p"] = disp["mcnemar_p"].map(lambda v: f"{v:.3g}")
    note = " — baseline-WQ outliers removed" if exclude else ""
    _section(
        f"DAY 2 vs DAY 3 RESOLUTION — McNEMAR (within-event, secondary analysis){note}",
        "(events with both follow-ups; gained = No@Day2->Yes@Day3, lost = reverse;",
        " McNemar = exact binomial on the discordant pairs; tests if timing matters)",
    )
    print(disp.to_string())
    print()
    # Between-group check at Day 2: confirms the groups are still indistinguishable
    # before the Day-3 divergence.
    _, odds, p = resolution_fisher(events, exclude=exclude, col="1st FU WQ improvement")
    print(f"Day-2 between-group Fisher (D vs E): odds ratio = {odds:.3f}   p = {p:.3g}")
    print()
