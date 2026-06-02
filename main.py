#!/usr/bin/env python3
from src.functions import (
    load_data,
    load_events,
    describe_data,
    describe_water_quality,
    analyze_oor_events,
    describe_resolution_by_parameter,
    reorder_by_pond,
)
from src.plotting_functions import plot_summary

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
    derived = analyze_oor_events(data, events)
    describe_resolution_by_parameter(events)

    path = plot_summary(derived, data, events)
    print(f"Saved plot: {path}")


if __name__ == "__main__":
    main()
