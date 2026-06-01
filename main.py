#!/usr/bin/env python3
from src.functions import load_data, load_events, describe_data

DATA_PATH = "data/Outcome Evaluation Phase 2 Data_Cleaned And Anonymized.xlsx"


def main():
    print(f"Loading data from: {DATA_PATH}\n")
    data = load_data(DATA_PATH)
    events = load_events(DATA_PATH)
    describe_data(data, events)


if __name__ == "__main__":
    main()
