from pathlib import Path
from src.functions import load_data, clean_data, describe_data, describe_water_quality

DATA_PATH = "data/raw/OE Data Periods 1-4.xlsx"


def main():
    print(f"Loading data from: {DATA_PATH}\n")
    df_raw = load_data(DATA_PATH)
    df = clean_data(df_raw)

    describe_data(df)
    describe_water_quality(df)

if __name__ == "__main__":
    main()
