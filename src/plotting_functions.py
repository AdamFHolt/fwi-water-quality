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

from src.functions import (
    POND_PARAMS,
    OOR_DRIVERS,
    wq_pond_means,
    baseline_balance_by_param,
    wq_outliers,
    derive_oor_events,
    oor_resolution_by_parameter,
    oor_resolution_per_pond,
    oor_event_improvements,
    improvement_tests,
)

PLOTS_DIR = Path("plots")

# One consistent palette: each group has a single identity colour used
# everywhere, and grey always means "not resolved".
GROUP_COLORS = {"Group D": "#4c72b0", "Group E": "#dd8452"}
NOT_RESOLVED = "#cccccc"
INSET_GREY = "#666666"  # subdued axes for the events-per-pond inset


def _save(fig, filename):
    PLOTS_DIR.mkdir(exist_ok=True)
    path = PLOTS_DIR / filename
    fig.savefig(path, dpi=400, bbox_inches="tight")
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
            _resolution_pie(ax, rv, ev - rv, GROUP_COLORS[g], f"{g} - {level} (n={ev})")

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


def plot_oor_resolution_by_pond(data, filename="oor_resolution.by_pond.png"):
    """Pond-level OOR resolution: one point per pond, sized by its event count.

    Each pond's Day-3 resolution rate (resolved events / its events) is a
    jittered point, one column per group; point area is proportional to how many
    OOR events the pond had. A horizontal bar marks each group's mean per-pond
    rate (the `mean_pct` from oor_resolution_by_pond). Companion to the
    event-level pies in oor_events.png: it shows the D-vs-E gap survives when
    every pond counts once (repeat-event ponds aren't driving it) and exposes the
    per-pond spread the pies hide.
    """
    per_pond = oor_resolution_per_pond(derive_oor_events(data))
    groups = sorted(per_pond["group"].unique())
    rng = np.random.default_rng(0)  # reproducible jitter

    fig, ax = plt.subplots(figsize=(8, 6))
    for i, g in enumerate(groups):
        sub = per_pond[per_pond["group"] == g]
        y = sub["proportion"].values * 100
        x = rng.normal(i, 0.07, len(sub))
        ax.scatter(x, y, s=sub["events"].values * 45, color=GROUP_COLORS[g],
                   alpha=0.55, edgecolor="white", linewidth=1, zorder=3)
        mean = y.mean()
        ax.hlines(mean, i - 0.25, i + 0.25, color=GROUP_COLORS[g], linewidth=3, zorder=4)
        ax.annotate(f"mean {mean:.1f}%", (i, mean), xytext=(0, 7),
                    textcoords="offset points", ha="center", va="bottom",
                    fontweight="bold", color=GROUP_COLORS[g])

    n_ponds = per_pond.groupby("group").size()
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([f"{g}\n(n={n_ponds[g]} ponds)" for g in groups])
    ax.set_xlim(-0.6, len(groups) - 1 + 1.6)  # right margin reserved for the key panel
    ax.spines["bottom"].set_bounds(-0.6, len(groups) - 1 + 0.4)  # stop the axis before the key panel
    ax.set_ylim(-8, 108)
    ax.set_ylabel("pond resolution rate\n(% of its OOR events resolved at Day 3)")
    ax.set_title("Pond-level OOR resolution")

    # Combined right-hand panel: the events-per-pond distribution (horizontal
    # bars, D vs E) that doubles as the point-size key - each row carries a dot
    # sized like the main scatter, so size <-> #events is read off the same panel.
    # This is the spread the event-level rate would weight by (motivates the
    # pond-level view).
    ev_counts = sorted(per_pond["events"].unique())
    kax = ax.inset_axes([0.72, 0.30, 0.26, 0.46])
    h = 0.38
    maxn = 0
    for j, g in enumerate(groups):
        vc = per_pond[per_pond["group"] == g]["events"].value_counts()
        vals = [vc.get(e, 0) for e in ev_counts]
        maxn = max(maxn, *vals)
        kax.barh([e + (j - 0.5) * h for e in ev_counts], vals, h,
                 color=GROUP_COLORS[g], edgecolor="white", label=g)
    # Size key: one representative dot per row, sized like the scatter, left of 0.
    for e in ev_counts:
        kax.scatter(-maxn * 0.22, e, s=e * 45, color="#999999",
                    edgecolor="white", clip_on=False, zorder=5)
    kax.set_xlim(-maxn * 0.42, maxn * 1.08)
    kax.set_xticks(range(0, maxn + 1, 2))  # integer pond counts only (skip the dot gutter)
    kax.set_yticks(ev_counts)
    kax.set_ylabel("events per pond", fontsize=8, color=INSET_GREY)
    kax.set_xlabel("ponds", fontsize=8, color=INSET_GREY)
    kax.tick_params(labelsize=8, colors=INSET_GREY)
    for spine in kax.spines.values():
        spine.set_color(INSET_GREY)
    kax.legend(fontsize=7, loc="upper right", frameon=False, handlelength=1,
               labelcolor=INSET_GREY)

    fig.tight_layout()
    return _save(fig, filename)


def plot_water_quality(data, filename="water_qualities.png", highlight_anoms=False):
    """Pond-properties figure: per group, baseline WQ as mean +/- SD bars (top
    row) and per-pond distributions as box + jittered-strip plots (bottom row),
    one column per parameter (routine visits, averaged per pond).

    With highlight_anoms=True the baseline-WQ outlier ponds (|studentized resid| > 2)
    are dropped from every panel's statistics - bars, box/IQR, n, and Levene p all
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
    bal = baseline_balance_by_param(data, exclude=excluded)  # same exclusion as the stats above
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
        ax.set_title(f"{param}\nHedges' g = {bal.loc[param, 'g']}")  # standardized D-E mean gap
        ax.margins(y=0.15)

        # Bottom: per-pond distribution (box + strip) over the cleaned set; the
        # box, the strip, and the Levene p in the title all exclude the outliers.
        ax = axes[1, col]
        subs = [stat_pond[stat_pond["Pond status"] == g][["Pond ID", param]].dropna() for g in groups]
        bp = ax.boxplot([s[param].values for s in subs], widths=0.5, showfliers=False, patch_artist=True)
        for patch, g in zip(bp["boxes"], groups):
            patch.set_facecolor(GROUP_COLORS[g])
            patch.set_alpha(0.55)
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
        ax.set_title(f"{param}\nLevene p = {bal.loc[param, 'p']}")

    if highlight_anoms:
        axes[1, -1].legend(
            handles=[
                Line2D([], [], marker="o", markerfacecolor="none", markeredgecolor="#d62728",
                       linestyle="none", markersize=9,
                       label="outlier (> 2 SD)"),
            ],
            loc="upper right", fontsize=8,
        )

    fig.tight_layout()
    return _save(fig, filename)


def plot_water_quality_visits(data, filename="water_qualities.visits.png"):
    """Visit-level WQ figure: routine visits only, one point per visit.

    Columns: DO (Morning), DO (Evening), pH, Ammonia - DO is split by time of
    day because morning and evening values differ substantially (~3 vs ~11 mg/L).
    Top row: mean +/- SD bars. Bottom row: box + dense jittered strip.
    """
    routine = data[data["Is follow up"] == "No"].copy()
    groups = sorted(routine["Pond status"].unique())
    rng = np.random.default_rng(0)

    # Each column is (param, time_filter, title).
    cols = [
        ("DO (mg/L)", "Morning", "DO - Morning (mg/L)"),
        ("DO (mg/L)", "Evening", "DO - Evening (mg/L)"),
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


def _fmt_p(v):
    """Compact p-value label: '<0.001' below that floor, else 3 dp."""
    return "<0.001" if v < 0.001 else f"{v:.3f}"


def plot_oor_improvement(data, filename="oor_improvement.png"):
    """Per-pond OOR improvement by group (D vs E) — the data behind the t / U tests.

    One panel per OOR parameter (DO, pH, Ammonia): per-pond mean out-of-range gap
    closed in that parameter's native units (mg/L for DO/ammonia, pH units for
    pH), +ve = moved toward the in-range band. This is dist0 - dist3 (change in
    how far outside the band the reading sits), not the raw Day-0->Day-3 change:
    it clamps at the band edge (no credit for overshoot) and is direction-folded
    so improvement is always positive whichever way the parameter was OOR.
    Each panel is a box + jittered strip per group, titled with the Welch-t and
    Mann-Whitney p-values both for all ponds and with the baseline-WQ outliers
    removed — so the figure shows the effect, why the two tests agree (rank
    separation), and the outlier sensitivity at once. The outlier ponds (the set
    dropped in the sensitivity) are drawn as red rings. A dashed line at 0 marks
    "no change". The cross-parameter "overall" story is left to the binary
    resolution rate (Fisher) — a cleaner pooled summary than a continuous metric.
    """
    imp = oor_event_improvements(data)
    flagged_ponds = set(wq_outliers(data)["Pond ID"])  # union across parameters
    tests = improvement_tests(data).set_index("scope")
    tests_out = improvement_tests(data, exclude=flagged_ponds).set_index("scope")  # outliers removed
    groups = ["Group D", "Group E"]
    units = {"DO": "mg/L", "pH": "pH units", "Ammonia": "mg/L"}
    rng = np.random.default_rng(0)

    fig, axes = plt.subplots(1, len(OOR_DRIVERS), figsize=(4.5 * len(OOR_DRIVERS), 5))
    for ax, scope in zip(axes, OOR_DRIVERS):
        per_pond = (imp[imp["parameter"] == scope]
                    .groupby(["group", "Pond ID"])["improvement"].mean().reset_index())
        by_g = [per_pond[per_pond["group"] == g] for g in groups]

        bp = ax.boxplot([d["improvement"].values for d in by_g], widths=0.5,
                        showfliers=False, patch_artist=True)
        for patch, g in zip(bp["boxes"], groups):
            patch.set_facecolor(GROUP_COLORS[g])
            patch.set_alpha(0.55)

        for i, (g, d) in enumerate(zip(groups, by_g)):
            xj = rng.normal(i + 1, 0.07, len(d))
            ax.scatter(xj, d["improvement"].values, color=GROUP_COLORS[g], s=22,
                       edgecolor="white", zorder=3)
            # Ring the baseline-WQ outlier ponds (those dropped in the sensitivity).
            ring = d["Pond ID"].isin(flagged_ponds).values
            ax.scatter(xj[ring], d["improvement"].values[ring], facecolors="none",
                       edgecolors="#d62728", s=150, linewidths=1.8, zorder=5)

        ax.axhline(0, color="#999999", lw=1, ls="--", zorder=1)  # no change
        ax.set_xticks([1, 2])
        ax.set_xticklabels([f"{g.split()[-1]}\n(n={len(d)})" for g, d in zip(groups, by_g)])
        ax.set_ylabel(f"out-of-range gap closed ({units[scope]})")
        # Title carries both the all-ponds and outliers-removed test p-values.
        ax.set_title(
            f"{scope}\n"
            f"all: Welch {_fmt_p(tests.loc[scope, 't_p'])} · MWU {_fmt_p(tests.loc[scope, 'u_p'])}\n"
            f"−outliers: Welch {_fmt_p(tests_out.loc[scope, 't_p'])} · MWU {_fmt_p(tests_out.loc[scope, 'u_p'])}",
            fontsize=10,
        )

    axes[-1].legend(
        handles=[Line2D([], [], marker="o", markerfacecolor="none",
                        markeredgecolor="#d62728", linestyle="none", markersize=9,
                        label="baseline-WQ outlier")],
        loc="lower right", fontsize=8,
    )
    fig.tight_layout()
    return _save(fig, filename)
