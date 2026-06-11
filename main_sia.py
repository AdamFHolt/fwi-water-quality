#!/usr/bin/env python3
"""Post-hoc self-initiated-actions (SIA) analysis, on the unblinded workbook.

main.py stays the as-run blind primary analysis; this script is the
exploratory unblinded follow-up: did farmers' self-initiated actions
affect the OOR outcomes?
"""
from src.functions import load_data, load_events
from src.sia_functions import (
    sia_actions,
    describe_sia_exposure,
    describe_resolution_by_exposure,
)

DATA_PATH = "inputs/data/Outcome Evaluation Phase 2 Data_Cleaned.xlsx"


def main():
    print(f"Loading data from: {DATA_PATH}\n")
    data = load_data(DATA_PATH)
    events = load_events(DATA_PATH)
    actions = sia_actions(data)

    describe_sia_exposure(events, actions)
    describe_resolution_by_exposure(events, actions)


if __name__ == "__main__":
    main()
