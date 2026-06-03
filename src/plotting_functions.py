from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")  # non-interactive: render straight to file
import matplotlib.pyplot as plt

# Clean, consistent typography across the figures.
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "figure.titlesize": 15,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

from matplotlib.lines import Line2D
from scipy.stats import levene

from src.functions import (
    POND_PARAMS,
    OOR_DRIVERS,
    wq_pond_means,
    wq_outliers,
    derive_oor_events,
    oor_resolution_by_parameter,
)

PLOTS_DIR = Path("plots")

# One consistent palette: each group has a single identity colour used
# everywhere, and grey always means "not resolved".
GROUP_COLORS = {"Group D": "#4c72b0", "Group E": "#dd8452"}
NOT_RESOLVED = "#cccccc"


def _save(fig, filename):
    PLOTS_DIR.mkdir(exist_ok=True)
    path = PLOTS_DIR / filename
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _resolution_pie(ax, resolved, not_resolved, color, title):
    """Draw one resolved-vs-not pie; resolved slice = group colour, rest grey."""
    total = resolved + not_resolved
    if total == 0:
        ax.text(0.5, 0.5, "no events", ha="center", va="center")
        ax.set_title(title, pad=10)
        ax.axis("off")
        return
    # Show the exact count alongside the percentage (iterate the slice values so
    # the displayed count is the true integer, not one back-computed from pct).
    counts = iter([resolved, not_resolved])
    _, _, autotexts = ax.pie(
        [resolved, not_resolved],
        labels=["Resolved", "Not resolved"],
        colors=[color, NOT_RESOLVED],
        autopct=lambda pct: f"{pct:.0f}%\n({next(counts)})",
        startangle=90,
        counterclock=False,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
        textprops={"fontsize": 11},
        pctdistance=0.6,
    )
    for t in autotexts:  # percentage labels: bold for readability on the wedges
        t.set_fontweight("bold")
    ax.set_title(title, pad=10)


def plot_oor_events(events, filename="oor_events.png"):
    """OOR-events figure: overall resolution pies, event-driver bars, and a
    per-parameter resolution pie for each group (Day-3 primary measure).

    One column per group; rows are Overall (pies), drivers (bars), then one pie
    row per OOR parameter. Built entirely from the OOR Events sheet.
    """
    res = oor_resolution_by_parameter(events).set_index(["parameter", "group"])
    # Driver counts are just the per-parameter event totals from `res`.
    drivers = res["events"].unstack("group").reindex(OOR_DRIVERS)  # rows=params, cols=groups
    groups = sorted(drivers.columns)

    # 6-col grid: overall pies (3 cols each), full-width driver bars, then the
    # per-parameter pies as a compact 3x2 block (params across, one group per row).
    def key(level, g):
        return f"{level}_{g.split()[-1]}"

    ncol = 2 * len(OOR_DRIVERS)  # 6
    overall_row = [k for g in groups for k in [key("Overall", g)] * len(OOR_DRIVERS)]
    driver_row = ["drv"] * ncol
    param_rows = [[k for p in OOR_DRIVERS for k in [key(p, g)] * 2] for g in groups]
    mosaic = [overall_row, driver_row] + param_rows
    heights = [1.4, 0.9] + [1.0] * len(groups)

    fig, axd = plt.subplot_mosaic(
        mosaic, figsize=(12, 14), gridspec_kw={"height_ratios": heights}
    )

    # --- Pies: overall + one row per parameter ---
    for level in ["Overall"] + OOR_DRIVERS:
        for g in groups:
            ax = axd[f"{level}_{g.split()[-1]}"]
            if (level, g) in res.index:
                ev = int(res.loc[(level, g), "events"])
                rv = int(res.loc[(level, g), "resolved"])
            else:
                ev = rv = 0
            _resolution_pie(ax, rv, ev - rv, GROUP_COLORS[g], f"{g} — {level} (n={ev})")

    # --- Grouped bars: how many OOR events flagged each parameter, per group ---
    ax = axd["drv"]
    x, width = range(len(drivers.index)), 0.38
    for i, g in enumerate(groups):
        ax.bar([xi + i * width for xi in x], drivers[g], width,
               label=g, color=GROUP_COLORS[g], edgecolor="white")
    ax.set_xticks([xi + width * (len(groups) - 1) / 2 for xi in x])
    ax.set_xticklabels(drivers.index)
    ax.set_ylabel("number of OOR events")
    ax.set_title("OOR event drivers (events flagging each parameter; an event may flag several)")
    ax.legend()

    fig.tight_layout()
    return _save(fig, filename)


def plot_water_quality(data, filename="water_qualities.png", highlight_anoms=False):
    """Pond-properties figure: per group, baseline WQ as mean +/- SD bars (top
    row) and per-pond distributions as box + jittered-strip plots (bottom row),
    one column per parameter (routine visits, averaged per pond).

    With highlight_anoms=True the baseline-WQ outlier ponds (|studentized resid| > 2)
    are dropped from every panel's statistics — bars, box/IQR, n, and Levene p all
    describe the cleaned distribution, matching the pond set removed in the
    oor_events.anoms_removed figure. Each outlier is still drawn (red ring, short
    Pond ID + OOR-event count) in the panel for the parameter it is extreme on, so
    you can see how far outside the cleaned distribution it sat.
    """
    pond = wq_pond_means(data)
    flagged = wq_outliers(data) if highlight_anoms else None
    # Stats use the cleaned pond set: drop the union of WQ-outlier ponds (the same
    # exclusion as oor_events.anoms_removed). Empty set => stats over all ponds.
    excluded = set(flagged.loc[flagged["outlier"], "Pond ID"]) if highlight_anoms else set()
    stat_pond = pond[~pond["Pond ID"].isin(excluded)]
    wq = stat_pond.groupby("Pond status")[POND_PARAMS].agg(["mean", "std"])
    n_ponds = stat_pond.groupby("Pond status").size()
    # OOR-event count per pond, so each ringed point can show how many events it drives.
    event_counts = derive_oor_events(data).groupby("Pond ID").size() if highlight_anoms else None
    groups = sorted(pond["Pond status"].unique())
    rng = np.random.default_rng(0)  # reproducible strip jitter

    fig, axes = plt.subplots(2, len(POND_PARAMS), figsize=(5 * len(POND_PARAMS), 9))
    for col, param in enumerate(POND_PARAMS):
        # Top: mean +/- SD bars (n = cleaned ponds).
        ax = axes[0, col]
        ax.bar(
            range(len(groups)),
            [wq.loc[g, (param, "mean")] for g in groups],
            yerr=[wq.loc[g, (param, "std")] for g in groups],
            color=[GROUP_COLORS[g] for g in groups],
            capsize=6,
            edgecolor="white",
        )
        ax.set_xticks(range(len(groups)))
        ax.set_xticklabels([f"{g.split()[-1]}\n(n={n_ponds[g]})" for g in groups])
        ax.set_title(param)
        ax.margins(y=0.15)

        # Bottom: per-pond distribution (box + strip) over the cleaned set; the
        # box, the strip, and the Levene p in the title all exclude the outliers.
        ax = axes[1, col]
        subs = [stat_pond[stat_pond["Pond status"] == g][["Pond ID", param]].dropna() for g in groups]
        bp = ax.boxplot([s[param].values for s in subs], widths=0.5, showfliers=False, patch_artist=True)
        for patch, g in zip(bp["boxes"], groups):
            patch.set_facecolor(GROUP_COLORS[g])
            patch.set_alpha(0.55)
        lev_p = round(levene(*[s[param].values for s in subs])[1], 3)
        if highlight_anoms:
            # This parameter's outliers, drawn back in as ringed points (they're
            # excluded from the box/strip above).
            fp = flagged[flagged["parameter"] == param]
            outlier_ids = set(fp.loc[fp["outlier"], "Pond ID"])
        for i, (g, sub) in enumerate(zip(groups, subs)):
            xj = rng.normal(i + 1, 0.06, len(sub))
            ax.scatter(xj, sub[param].values, color=GROUP_COLORS[g], s=15, edgecolor="white", zorder=3)
            if not highlight_anoms:
                continue
            ring = pond[(pond["Pond status"] == g) & pond["Pond ID"].isin(outlier_ids)][["Pond ID", param]].dropna()
            xr, yr = rng.normal(i + 1, 0.06, len(ring)), ring[param].values
            ax.scatter(xr, yr, color=GROUP_COLORS[g], s=15, edgecolor="white", zorder=4)
            ax.scatter(xr, yr, facecolors="none", edgecolors="#d62728", s=150, linewidths=1.8, zorder=5)
            # Label each ringed pond; flip side for the right-hand group.
            ha, dx = ("left", 14) if i < len(groups) - 1 else ("right", -14)
            for xk, yk, pid in zip(xr, yr, ring["Pond ID"].values):
                # Short pond id + how many OOR events it drives, e.g. "9252e874 (4 ev)".
                label = f"{pid.replace('pond_', '')} ({event_counts.get(pid, 0)} ev)"
                ax.annotate(label, (xk, yk), xytext=(dx, 0), textcoords="offset points",
                            fontsize=8, va="center", ha=ha, zorder=6)
        ax.set_xticks(range(1, len(groups) + 1))
        ax.set_xticklabels([g.split()[-1] for g in groups])
        ax.set_title(f"{param}\nLevene p = {lev_p}")

    if highlight_anoms:
        axes[1, -1].legend(
            handles=[
                Line2D([], [], marker="o", markerfacecolor="none", markeredgecolor="#d62728",
                       linestyle="none", markersize=9,
                       label="outlier (excluded): > 2 SD from mean"),
            ],
            loc="upper right", fontsize=8,
        )

    fig.tight_layout()
    return _save(fig, filename)


def plot_water_quality_visits(data, filename="water_qualities.visits.png"):
    """Visit-level WQ figure: routine visits only, one point per visit.

    Columns: DO (Morning), DO (Evening), pH, Ammonia — DO is split by time of
    day because morning and evening values differ substantially (~3 vs ~11 mg/L).
    Top row: mean +/- SD bars. Bottom row: box + dense jittered strip.
    """
    routine = data[data["Is follow up"] == "No"].copy()
    groups = sorted(routine["Pond status"].unique())
    rng = np.random.default_rng(0)

    # Each column is (param, time_filter, title).
    cols = [
        ("DO (mg/L)", "Morning", "DO — Morning (mg/L)"),
        ("DO (mg/L)", "Evening", "DO — Evening (mg/L)"),
        ("pH",        None,      "pH"),
        ("Ammonia—NH3 (mg/L)", None, "Ammonia—NH3 (mg/L)"),
    ]

    fig, axes = plt.subplots(2, len(cols), figsize=(5 * len(cols), 9))
    for col, (param, time, title) in enumerate(cols):
        df = routine[routine["Type"] == time] if time else routine

        # Top: mean +/- SD bars.
        ax = axes[0, col]
        grp = df.groupby("Pond status")[param].agg(["mean", "std"])
        n_visits = df.groupby("Pond status")[param].count()
        ax.bar(
            range(len(groups)),
            [grp.loc[g, "mean"] for g in groups],
            yerr=[grp.loc[g, "std"] for g in groups],
            color=[GROUP_COLORS[g] for g in groups],
            capsize=6,
            edgecolor="white",
        )
        ax.set_xticks(range(len(groups)))
        ax.set_xticklabels([f"{g.split()[-1]}\n(n={n_visits[g]})" for g in groups])
        ax.set_title(title)
        ax.margins(y=0.15)

        # Bottom: box + dense strip.
        ax = axes[1, col]
        subs = [df[df["Pond status"] == g][param].dropna() for g in groups]
        bp = ax.boxplot([s.values for s in subs], widths=0.5, showfliers=False, patch_artist=True)
        for patch, g in zip(bp["boxes"], groups):
            patch.set_facecolor(GROUP_COLORS[g])
            patch.set_alpha(0.55)
        for i, (g, s) in enumerate(zip(groups, subs)):
            xj = rng.normal(i + 1, 0.08, len(s))
            ax.scatter(xj, s.values, color=GROUP_COLORS[g], s=8, alpha=0.35,
                       edgecolor="none", zorder=3)
        ax.set_xticks(range(1, len(groups) + 1))
        ax.set_xticklabels([g.split()[-1] for g in groups])
        ax.set_title(title)

    fig.tight_layout()
    return _save(fig, filename)
