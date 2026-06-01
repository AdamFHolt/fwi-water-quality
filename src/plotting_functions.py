from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive: render straight to file
import matplotlib.pyplot as plt

PLOTS_DIR = Path("plots")

# Resolved = green, not resolved = grey. Group labels stay blind (D/E).
COLORS = {"Resolved": "#2ca02c", "Not resolved": "#bdbdbd"}


def plot_resolution_pies(derived, filename="oor_resolution_by_group.png"):
    """One pie per group: resolved vs not-resolved OOR events (Day-3 primary).

    `derived` is the output of derive_oor_events (one row per event with a
    boolean `resolved`). Saves to plots/<filename> and returns the path.
    """
    groups = sorted(derived["group"].dropna().unique())

    fig, axes = plt.subplots(1, len(groups), figsize=(5 * len(groups), 5))
    if len(groups) == 1:
        axes = [axes]

    for ax, group in zip(axes, groups):
        sub = derived[derived["group"] == group]
        resolved = int(sub["resolved"].sum())
        not_resolved = int((sub["resolved"] == False).sum())  # noqa: E712
        counts = [resolved, not_resolved]
        labels = ["Resolved", "Not resolved"]

        ax.pie(
            counts,
            labels=labels,
            colors=[COLORS[l] for l in labels],
            autopct=lambda pct: f"{pct:.1f}%\n({round(pct / 100 * sum(counts))})",
            startangle=90,
            counterclock=False,
            wedgeprops={"edgecolor": "white"},
        )
        ax.set_title(f"{group}\n(n = {resolved + not_resolved} OOR events)")

    fig.suptitle("OOR event resolution by group (Day-3 primary measure)", fontsize=13)
    fig.tight_layout()

    PLOTS_DIR.mkdir(exist_ok=True)
    path = PLOTS_DIR / filename
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path
