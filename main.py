#!/usr/bin/env python3
from src.functions import (
    load_data,
    load_events,
    describe_data,
    describe_water_quality,
    describe_variance_homogeneity,
    describe_wq_outliers,
    wq_outliers,
    analyze_oor_events,
    describe_resolution_by_parameter,
    reorder_by_pond,
)
from src.plotting_functions import plot_oor_events, plot_water_quality, plot_water_quality_visits

DATA_PATH = "data/Outcome Evaluation Phase 2 Data_Cleaned And Anonymized.xlsx"
DATA_PATH_REORD = "data/Outcome Evaluation Phase 2 Data_Cleaned And Anonymized.reordered.xlsx"

def main():
    # Write a Pond-ID-sorted copy of the workbook, then analyse that.
    print(f"Reordering {DATA_PATH} by Pond ID\n")
    reorder_by_pond(DATA_PATH, DATA_PATH_REORD)

    # Load the per-visit Data sheet and the one-row-per-OOR-event sheet.
    print(f"Loading data from: {DATA_PATH_REORD}\n")
    data = load_data(DATA_PATH_REORD)
    events = load_events(DATA_PATH_REORD)

    # Descriptive statistics (printed to console).
    print(f"Doing basic descriptive data analysis:")
    describe_data(data, events)                 # overview: counts by group
    describe_water_quality(data)                # baseline WQ mean/SD per pond
    describe_variance_homogeneity(data)         # Levene's test, D vs E
    describe_wq_outliers(data)                  # outlier / influence diagnostics
    analyze_oor_events(data, events)            # OOR resolution rate + cross-check vs OOR Events sheet
    describe_resolution_by_parameter(events)    # resolution rate by parameter

    # Sensitivity variant: OOR figure with the WQ-anomalous ponds removed.
    flagged_ponds = set(wq_outliers(data)["Pond ID"])
    events_clean = events[~events["Pond ID"].isin(flagged_ponds)]

    # Figures.
    print(f"Saved plots:")
    print(f"  {plot_oor_events(events)}")                                        # resolution pies + drivers
    print(f"  {plot_oor_events(events_clean, 'oor_events.anoms_removed.png')}")  # same, anomalous ponds removed
    print(f"  {plot_water_quality(data)}")                                       # WQ bars + distributions
    print(f"  {plot_water_quality(data, 'water_qualities.anoms_highlighted.png', highlight_anoms=True)}")  # WQ with outliers ringed
    print(f"  {plot_water_quality_visits(data)}")                                  # WQ visit-level distributions


if __name__ == "__main__":
    main()
