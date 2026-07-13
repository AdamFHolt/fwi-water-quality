from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")  # non-interactive: render straight to file
import matplotlib.pyplot as plt

# House style for all the figures.
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "figure.titlesize": 15,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#888888",   # lighter spines
    "axes.labelcolor": "#222222",
    "xtick.color": "#555555",
    "ytick.color": "#555555",
    "axes.axisbelow": True,         # gridlines sit behind the data
    "grid.color": "#e7e7e7",
    "grid.linewidth": 0.8,
})

from matplotlib.lines import Line2D
from matplotlib.patches import Patch

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
    resolution_day2_vs_day3,
)

PLOTS_DIR = Path("outputs/plots")

# Each group keeps one identity colour everywhere; grey always means "not resolved".
GROUP_COLORS = {"Group D": "#4c72b0", "Group E": "#dd8452"}
# Unblinded display names (visit counts 532/466 pin D=Control, E=Treatment).
UNBLINDED_LABEL = {"Group D": "Control", "Group E": "Treatment"}
NOT_RESOLVED = "#cccccc"
INSET_GREY = "#666666"  # subdued axes for the events-per-pond inset
OUTLIER_RED = "#d62728"  # baseline-WQ outlier ponds, used in every figure
OUTLIER_LABEL = "baseline-WQ outlier (>2 SD)"  # one legend wording everywhere


def _save(fig, filename):
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = PLOTS_DIR / filename
    fig.savefig(path, dpi=400, bbox_inches="tight")
    plt.close(fig)
    return path


def _ygrid(ax):
    """Faint horizontal gridlines, kept behind the data."""
    ax.grid(axis="y", zorder=0)
    ax.set_axisbelow(True)


def _resolution_pie(ax, resolved, not_resolved, color, title):
    """Draw one resolved-vs-not pie; resolved slice = group colour, rest grey."""
    total = resolved + not_resolved
    if total == 0:
        ax.text(0.5, 0.5, "no events", ha="center", va="center")
        ax.set_title(title, pad=10)
        ax.axis("off")
        return
    # autopct only receives the percentage, so feed the true counts in via an iterator.
    counts = iter([resolved, not_resolved])
    _, _, autotexts = ax.pie(
        [resolved, not_resolved],
        colors=[color, NOT_RESOLVED],
        autopct=lambda pct: f"{pct:.0f}%\n({next(counts)})",
        startangle=90,
        counterclock=False,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
        textprops={"fontsize": 11},
        pctdistance=0.6,
    )
    for t in autotexts:
        t.set_fontweight("bold")
    ax.set_title(title, pad=10)


def plot_oor_events(events, filename="Fig4.oor_resolution.png"):
    """OOR-events figure (Fig4): overall resolution pies, event-driver bars, and
    per-parameter pies, one column per group. Built from the OOR Events sheet.
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
    # Each overall pie spans half the row; each per-parameter pie spans two columns.
    overall_row = []
    for g in groups:
        overall_row += [key("Overall", g)] * len(OOR_DRIVERS)
    driver_row = ["drv"] * ncol
    param_rows = []
    for g in groups:
        row = []
        for p in OOR_DRIVERS:
            row += [key(p, g)] * 2
        param_rows.append(row)
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
            _resolution_pie(ax, rv, ev - rv, GROUP_COLORS[g], f"{UNBLINDED_LABEL[g]} – {level} (n={ev})")

    # --- Grouped bars: how many OOR events flagged each parameter, per group ---
    ax = axd["drv"]
    x, width = range(len(drivers.index)), 0.38
    for i, g in enumerate(groups):
        ax.bar([xi + i * width for xi in x], drivers[g], width,
               label=UNBLINDED_LABEL[g], color=GROUP_COLORS[g], edgecolor="white")
    ax.set_xticks([xi + width * (len(groups) - 1) / 2 for xi in x])
    ax.set_xticklabels(drivers.index)
    ax.set_ylabel("number of OOR events")
    ax.set_title("OOR event drivers (events flagging each parameter; an event may flag several)")
    _ygrid(ax)

    fig.tight_layout()
    # One shared key for the whole figure: group colour = resolved slice / bar
    # identity, grey = not resolved.
    fig.legend(
        handles=[Patch(facecolor=GROUP_COLORS["Group D"], label=UNBLINDED_LABEL["Group D"]),
                 Patch(facecolor=GROUP_COLORS["Group E"], label=UNBLINDED_LABEL["Group E"]),
                 Patch(facecolor=NOT_RESOLVED, label="not resolved")],
        loc="lower center", ncol=3, frameon=False, fontsize=10,
        bbox_to_anchor=(0.5, -0.015),
    )
    return _save(fig, filename)


def plot_oor_resolution_by_pond(data, filename="Fig6.oor_resolution_by_pond.png"):
    """Pond-level OOR resolution (Fig6): one jittered point per pond, sized by its
    event count, with a horizontal bar at each group's mean per-pond rate.
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
    ax.set_xticklabels([f"{UNBLINDED_LABEL[g]}\n(n={n_ponds[g]} ponds)" for g in groups])
    ax.set_xlim(-0.6, len(groups) - 1 + 1.6)  # right margin reserved for the key panel
    ax.spines["bottom"].set_bounds(-0.6, len(groups) - 1 + 0.4)  # stop the axis before the key panel
    ax.set_ylim(-8, 108)
    ax.set_ylabel("pond resolution rate\n(% of its OOR events resolved at Day 3)")
    _ygrid(ax)

    # Right-hand panel: events-per-pond distribution (horizontal bars, D vs E),
    # doubling as the point-size key (one dot per row, sized like the scatter).
    ev_counts = sorted(per_pond["events"].unique())
    kax = ax.inset_axes([0.72, 0.30, 0.26, 0.46])
    h = 0.38
    maxn = 0
    for j, g in enumerate(groups):
        vc = per_pond[per_pond["group"] == g]["events"].value_counts()
        vals = [vc.get(e, 0) for e in ev_counts]
        maxn = max(maxn, *vals)
        kax.barh([e + (j - 0.5) * h for e in ev_counts], vals, h,
                 color=GROUP_COLORS[g], edgecolor="white", label=UNBLINDED_LABEL[g])
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


def plot_water_quality(data, filename="Fig2.water_quality_per_pond.png", highlight_anoms=False):
    """Per-pond baseline WQ (Fig2/Fig3): mean +/- SD bars (top) and box + strip
    (bottom), one column per parameter.

    With highlight_anoms=True the baseline-WQ outlier ponds are dropped from every
    panel's stats (Fig3), but still drawn as red-ringed points labelled with their
    Pond ID and OOR-event count in the parameter they're extreme on.
    """
    pond = wq_pond_means(data)
    flagged = wq_outliers(data) if highlight_anoms else None
    # Stats use the cleaned pond set: drop the union of WQ-outlier ponds (the same
    # exclusion as Fig5.oor_resolution_outliers_removed). Empty set => stats over all ponds.
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
        ax.set_xticklabels([f"{UNBLINDED_LABEL[g]}\n(n={n_ponds[g]})" for g in groups])
        ax.set_title(param, pad=24)  # pad leaves room for the stat line below
        ax.text(0.5, 1.0, f"Hedges' g = {bal.loc[param, 'g']}", transform=ax.transAxes,
                ha="center", va="bottom", fontsize=10, fontweight="normal")  # standardized D-E mean gap
        ax.margins(y=0.15)
        _ygrid(ax)

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
            ax.scatter(xr, yr, facecolors="none", edgecolors=OUTLIER_RED, s=150, linewidths=1.8, zorder=5)
            # Label each ringed pond; flip side for the right-hand group.
            ha, dx = ("left", 14) if i < len(groups) - 1 else ("right", -14)
            for xk, yk, pid in zip(xr, yr, ring["Pond ID"].values):
                # Short pond id + how many OOR events it drives, e.g. "9252e874 (4 ev)".
                label = f"{pid.replace('pond_', '')} ({event_counts.get(pid, 0)} ev)"
                ax.annotate(label, (xk, yk), xytext=(dx, 0), textcoords="offset points",
                            fontsize=8, va="center", ha=ha, zorder=6)
        ax.set_xticks(range(1, len(groups) + 1))
        ax.set_xticklabels([UNBLINDED_LABEL[g] for g in groups])
        ax.set_title("per-pond distribution", pad=24)
        ax.text(0.5, 1.0, f"Levene p = {bal.loc[param, 'p']}", transform=ax.transAxes,
                ha="center", va="bottom", fontsize=10, fontweight="normal")
        _ygrid(ax)

    if highlight_anoms:
        axes[1, -1].legend(
            handles=[
                Line2D([], [], marker="o", markerfacecolor="none", markeredgecolor=OUTLIER_RED,
                       linestyle="none", markersize=9,
                       label=OUTLIER_LABEL),
            ],
            loc="upper right", fontsize=8,
        )

    fig.tight_layout()
    return _save(fig, filename)


def plot_water_quality_visits(data, filename="Fig1.water_quality_all_visits.png"):
    """Visit-level baseline WQ (Fig1): one point per routine visit. Columns DO
    Morning, DO Evening, pH, Ammonia; top row mean +/- SD bars, bottom row box +
    jittered strip.
    """
    routine = data[data["Is follow up"] == "No"].copy()
    groups = sorted(routine["Pond status"].unique())
    rng = np.random.default_rng(0)

    # Each column is (param, time_filter, title).
    cols = [
        ("DO (mg/L)", "Morning", "DO – Morning (mg/L)"),
        ("DO (mg/L)", "Evening", "DO – Evening (mg/L)"),
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
        ax.set_xticklabels([f"{UNBLINDED_LABEL[g]}\n(n={n_visits[g]})" for g in groups])
        ax.set_title(title)
        ax.margins(y=0.15)
        _ygrid(ax)

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
        ax.set_xticklabels([UNBLINDED_LABEL[g] for g in groups])
        ax.set_title("per-visit distribution")
        _ygrid(ax)

    fig.tight_layout()
    return _save(fig, filename)


def _fmt_p(v):
    """Compact p-value label: '<0.001' below that floor, else 3 dp."""
    return "<0.001" if v < 0.001 else f"{v:.3f}"


def plot_oor_improvement(data, filename="Fig7.oor_improvement.png", exclude=None):
    """Per-pond OOR improvement by group (D vs E) — the data behind the t / U tests.

    One panel per OOR parameter: per-pond mean out-of-range gap closed (dist0 -
    dist3) in native units, +ve = moved toward the band. Box + jittered strip per
    group, titled with the Welch-t and Mann-Whitney p-values both with and without
    the baseline-WQ outlier ponds. Faint dots are individual events; solid dots are
    the pond means (the test unit; outlier ponds in red); the dashed line marks 0.

    `exclude` (a set of Pond IDs) drops those ponds from the boxes, dots and counts
    for the outliers-removed variant. The p-value table always shows both the
    all-ponds and outliers-removed stats, and the y-axis per parameter is fixed to
    the full-data range so the two variants line up panel-for-panel.
    """
    imp = oor_event_improvements(data)
    fl = wq_outliers(data)
    flagged_ponds = set(fl["Pond ID"])  # union across parameters (whole-pond removal)
    # Y-limits from the full (pre-exclusion) data so the all-ponds and
    # outliers-removed variants share an axis per parameter and compare directly.
    ylims = {}
    for scope in OOR_DRIVERS:
        v = imp.loc[imp["parameter"] == scope, "improvement"]
        pad = 0.08 * (v.max() - v.min())
        ylims[scope] = (v.min() - pad, v.max() + pad)
    if exclude:
        imp = imp[~imp["Pond ID"].isin(exclude)]
    tests = improvement_tests(data).set_index("parameter")
    tests_pond = improvement_tests(data, exclude=flagged_ponds).set_index("parameter")  # outlier ponds removed
    groups = ["Group D", "Group E"]
    units = {"DO": "mg/L", "pH": "pH units", "Ammonia": "mg/L"}
    rng = np.random.default_rng(0)

    fig, axes = plt.subplots(1, len(OOR_DRIVERS), figsize=(4.5 * len(OOR_DRIVERS), 5))
    for ax, scope in zip(axes, OOR_DRIVERS):
        ev = imp[imp["parameter"] == scope]  # one row per OOR event-instance
        per_pond = ev.groupby(["group", "Pond ID"])["improvement"].mean().reset_index()
        by_g = [per_pond[per_pond["group"] == g] for g in groups]

        # Box summarises the pond means (the inferential unit), not the events.
        bp = ax.boxplot([d["improvement"].values for d in by_g], widths=0.5,
                        showfliers=False, patch_artist=True)
        for patch, g in zip(bp["boxes"], groups):
            patch.set_facecolor(GROUP_COLORS[g])
            patch.set_alpha(0.55)

        for i, (g, d) in enumerate(zip(groups, by_g)):
            # Faint raw events behind, for context only (NOT independent — the
            # stats are pond-level); solid pond means on top.
            eg = ev[ev["group"] == g]
            ax.scatter(rng.normal(i + 1, 0.07, len(eg)), eg["improvement"].values,
                       color=GROUP_COLORS[g], s=9, alpha=0.25, edgecolor="none", zorder=2)
            xj = rng.normal(i + 1, 0.07, len(d))
            vals = d["improvement"].values
            # Colour the baseline-WQ outlier ponds (those dropped in the sensitivity)
            # red; the rest take the group colour.
            is_out = d["Pond ID"].isin(flagged_ponds).values
            ax.scatter(xj[~is_out], vals[~is_out], color=GROUP_COLORS[g], s=30,
                       edgecolor="black", linewidths=0.8, zorder=3)
            ax.scatter(xj[is_out], vals[is_out], color=OUTLIER_RED, s=30,
                       edgecolor="black", linewidths=0.8, zorder=4)

        ax.axhline(0, color="#999999", lw=1, ls="--", zorder=1)  # no change
        _ygrid(ax)
        ax.set_ylim(ylims[scope])
        ax.set_xticks([1, 2])
        ax.set_xticklabels([f"{UNBLINDED_LABEL[g]}\n(n={len(d)})" for g, d in zip(groups, by_g)])
        ax.set_ylabel(f"out-of-range gap closed ({units[scope]})")
        # Under the title: monospace p-value table, one row per outlier rule.
        ax.set_title(scope, fontsize=13, fontweight="bold", pad=42)
        rows = [
            ("",                "Welch", "MWU"),
            ("all ponds",       _fmt_p(tests.loc[scope, "t_p"]),      _fmt_p(tests.loc[scope, "u_p"])),
            ("outliers removed", _fmt_p(tests_pond.loc[scope, "t_p"]), _fmt_p(tests_pond.loc[scope, "u_p"])),
        ]
        block = "\n".join(f"{lab:<18}{w:>6}{u:>6}" for lab, w, u in rows)
        ax.text(0.5, 1.0, block, transform=ax.transAxes, ha="center", va="bottom",
                family="monospace", fontsize=8, color="#333333", linespacing=1.35)

    fig.tight_layout()

    def legend_dot(fc, ec, a, ms, lab):
        return Line2D([], [], marker="o", markerfacecolor=fc, markeredgecolor=ec,
                      alpha=a, linestyle="none", markersize=ms, label=lab)

    handles = [legend_dot("#888888", "black", 1.0, 8, "pond mean"),
               legend_dot("#888888", "none", 0.25, 6, "event")]
    if not exclude:
        handles.append(legend_dot(OUTLIER_RED, "black", 1.0, 8, OUTLIER_LABEL))
    fig.legend(
        handles=handles, loc="lower center", ncol=len(handles), fontsize=8,
        frameon=False, bbox_to_anchor=(0.5, -0.04),
    )
    return _save(fig, filename)


def plot_day2_vs_day3(events, filename="Fig8.day2_vs_day3.png"):
    """Day-2 vs Day-3 resolution pies (Fig8): 2x2 grid, rows = Day 2 / Day 3,
    columns = Group D / E, over events with both follow-ups (the §5 McNemar story).
    """
    res = resolution_day2_vs_day3(events)
    groups = ["Group D", "Group E"]
    days = [("Day 2", "day2_res"), ("Day 3", "day3_res")]

    fig, axes = plt.subplots(2, 2, figsize=(7.5, 8))
    for col, g in enumerate(groups):
        n = int(res.loc[g, "n"])
        for row, (day, rescol) in enumerate(days):
            rv = int(res.loc[g, rescol])
            _resolution_pie(axes[row, col], rv, n - rv, GROUP_COLORS[g],
                            f"{UNBLINDED_LABEL[g]} – {day} (n={n})")

    fig.tight_layout()
    fig.legend(
        handles=[Patch(facecolor=GROUP_COLORS["Group D"], label=UNBLINDED_LABEL["Group D"]),
                 Patch(facecolor=GROUP_COLORS["Group E"], label=UNBLINDED_LABEL["Group E"]),
                 Patch(facecolor=NOT_RESOLVED, label="not resolved")],
        loc="lower center", ncol=3, frameon=False, fontsize=10,
        bbox_to_anchor=(0.5, -0.02),
    )
    return _save(fig, filename)
