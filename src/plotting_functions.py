from pathlib import Path

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

from src.functions import (
    WQ_PARAMS,
    OOR_DRIVERS,
    wq_pond_means,
    oor_event_drivers,
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
    _, _, autotexts = ax.pie(
        [resolved, not_resolved],
        labels=["Resolved", "Not resolved"],
        colors=[color, NOT_RESOLVED],
        autopct=lambda pct: f"{pct:.0f}%\n({round(pct / 100 * total)})",
        startangle=90,
        counterclock=False,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
        textprops={"fontsize": 11},
        pctdistance=0.6,
    )
    for t in autotexts:  # percentage labels: bold for readability on the wedges
        t.set_fontweight("bold")
    ax.set_title(title, pad=10)


def _group_bars(ax, x, values_by_group, groups, width=0.38):
    """Side-by-side bars per group at integer x positions; returns centre offsets."""
    for i, g in enumerate(groups):
        ax.bar([xi + i * width for xi in x], values_by_group[g], width,
               label=g, color=GROUP_COLORS[g], edgecolor="white")
    ax.set_xticks([xi + width * (len(groups) - 1) / 2 for xi in x])


def plot_oor_events(events, filename="oor_events.png"):
    """OOR-events figure: overall resolution pies, event-driver bars, and a
    per-parameter resolution pie for each group (Day-3 primary measure).

    One column per group; rows are Overall (pies), drivers (bars), then one pie
    row per OOR parameter. Built entirely from the OOR Events sheet.
    """
    res = oor_resolution_by_parameter(events).set_index(["parameter", "group"])
    drivers = oor_event_drivers(events)  # rows = params, cols = groups
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
    _group_bars(ax, range(len(drivers.index)), drivers, groups)
    ax.set_xticklabels(drivers.index)
    ax.set_ylabel("number of OOR events")
    ax.set_title("OOR event drivers (events flagging each parameter; an event may flag several)")
    ax.legend()

    fig.tight_layout()
    return _save(fig, filename)


def plot_water_quality(data, filename="water_quality.png"):
    """Pond-properties figure: baseline WQ mean +/- SD by group, one panel per
    parameter (routine visits, averaged per pond). Room to grow (e.g. add
    distribution-plot rows later).
    """
    pond = wq_pond_means(data)
    wq = pond.groupby("Pond status")[WQ_PARAMS].agg(["mean", "std"])
    n_ponds = pond.groupby("Pond status").size()
    groups = sorted(wq.index)

    fig, axes = plt.subplots(1, len(WQ_PARAMS), figsize=(5 * len(WQ_PARAMS), 5))
    for ax, param in zip(axes, WQ_PARAMS):
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

    fig.tight_layout()
    return _save(fig, filename)
