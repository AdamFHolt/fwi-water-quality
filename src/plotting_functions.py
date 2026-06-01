from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive: render straight to file
import matplotlib.pyplot as plt

# Clean, consistent typography across the figure.
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "figure.titlesize": 15,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

from src.functions import WQ_PARAMS, wq_pond_means, oor_event_drivers

PLOTS_DIR = Path("plots")

# One consistent palette across the whole figure: each group has a single
# identity colour used everywhere, and grey always means "not resolved".
GROUP_COLORS = {"Group D": "#4c72b0", "Group E": "#dd8452"}
NOT_RESOLVED = "#cccccc"


def plot_summary(derived, data, events, filename="group_summary.png"):
    """Combined figure: OOR resolution pies (top), WQ mean/SD bars (middle),
    and OOR event drivers (bottom).

    `derived` is the output of derive_oor_events (one row per event with a
    boolean `resolved`); `data` is the per-visit Data sheet; `events` is the
    OOR Events sheet. Saves to plots/<filename> and returns the path.
    """
    groups = sorted(derived["group"].dropna().unique())
    # Baseline WQ: routine visits, one mean per pond (see wq_pond_means).
    pond = wq_pond_means(data)
    wq = pond.groupby("Pond status")[WQ_PARAMS].agg(["mean", "std"])
    n_ponds = pond.groupby("Pond status").size()
    drivers = oor_event_drivers(events)  # rows = params, cols = groups

    # Rows: pies (per group), WQ bars (per param), OOR drivers (full width).
    mosaic = [
        ["D", "D", "D", "E", "E", "E"],
        ["p0", "p0", "p1", "p1", "p2", "p2"],
        ["drv", "drv", "drv", "drv", "drv", "drv"],
    ]
    # Taller top row so the pies render larger than the bar panels.
    fig, axd = plt.subplot_mosaic(
        mosaic, figsize=(12, 15), gridspec_kw={"height_ratios": [1.6, 1, 1]}
    )

    # --- Pies: resolved vs not resolved ---
    for group in groups:
        ax = axd[group.split()[-1]]  # "Group D" -> "D"
        sub = derived[derived["group"] == group]
        resolved = int(sub["resolved"].sum())
        not_resolved = int((sub["resolved"] == False).sum())  # noqa: E712
        counts = [resolved, not_resolved]
        labels = ["Resolved", "Not resolved"]
        # Resolved slice = this group's colour; remainder grey.
        colors = [GROUP_COLORS[group], NOT_RESOLVED]

        wedges, texts, autotexts = ax.pie(
            counts,
            labels=labels,
            colors=colors,
            autopct=lambda pct: f"{pct:.0f}%\n({round(pct / 100 * sum(counts))})",
            startangle=90,
            counterclock=False,
            wedgeprops={"edgecolor": "white", "linewidth": 1.5},
            textprops={"fontsize": 12},
            pctdistance=0.6,
        )
        for t in autotexts:  # percentage labels: bold for readability on the wedges
            t.set_fontsize(12)
            t.set_fontweight("bold")
        ax.set_title(f"{group}\n(n = {resolved + not_resolved} OOR events)", pad=12)

    # --- Bars: WQ mean (+/- SD) by group ---
    for i, param in enumerate(WQ_PARAMS):
        ax = axd[f"p{i}"]
        means = [wq.loc[g, (param, "mean")] for g in groups]
        stds = [wq.loc[g, (param, "std")] for g in groups]
        ax.bar(
            range(len(groups)),
            means,
            yerr=stds,
            color=[GROUP_COLORS[g] for g in groups],
            capsize=6,
            edgecolor="white",
        )
        ax.set_xticks(range(len(groups)))
        # "D\n(n=28)" — n is ponds, not visits.
        ax.set_xticklabels([f"{g.split()[-1]}\n(n={n_ponds[g]})" for g in groups])
        ax.set_title(param)
        ax.margins(y=0.15)

    # --- Grouped bars: how many OOR events flagged each parameter, per group ---
    ax = axd["drv"]
    x = range(len(drivers.index))  # one cluster per parameter
    width = 0.38
    for i, g in enumerate(groups):
        ax.bar([xi + i * width for xi in x], drivers[g], width,
               label=g, color=GROUP_COLORS[g], edgecolor="white")
    ax.set_xticks([xi + width / 2 for xi in x])
    ax.set_xticklabels(drivers.index)
    ax.set_ylabel("number of OOR events")
    ax.set_title("OOR event drivers (events flagging each parameter; an event may flag several)")
    ax.legend()

    fig.tight_layout()

    PLOTS_DIR.mkdir(exist_ok=True)
    path = PLOTS_DIR / filename
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path
