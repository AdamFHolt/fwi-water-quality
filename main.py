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
from src.plotting_functions import plot_oor_events, plot_water_quality

DATA_PATH = "data/Outcome Evaluation Phase 2 Data_Cleaned And Anonymized.xlsx"
DATA_PATH_REORD = "data/Outcome Evaluation Phase 2 Data_Cleaned And Anonymized.reordered.xlsx"

def main():
    print(f"Reordering {DATA_PATH} by Pond ID\n")
    reorder_by_pond(DATA_PATH, DATA_PATH_REORD)

    print(f"Loading data from: {DATA_PATH_REORD}\n")
    data = load_data(DATA_PATH_REORD)
    events = load_events(DATA_PATH_REORD)

    print(f"Doing basic descriptive data analysis:")
    describe_data(data, events)
    describe_water_quality(data)
    describe_variance_homogeneity(data)
    describe_wq_outliers(data)
    analyze_oor_events(data, events)
    describe_resolution_by_parameter(events)

    # Sensitivity variant: OOR figure with the WQ-anomalous ponds removed.
    flagged_ponds = set(wq_outliers(data)["Pond ID"])
    events_clean = events[~events["Pond ID"].isin(flagged_ponds)]

    print(f"Saved plots:")
    print(f"  {plot_oor_events(events)}")
    print(f"  {plot_oor_events(events_clean, 'oor_events.anoms_removed.png')}")
    print(f"  {plot_water_quality(data)}")
    print(f"  {plot_water_quality(data, 'water_qualities.anoms_highlighted.png', highlight_anoms=True)}")


if __name__ == "__main__":
    main()
