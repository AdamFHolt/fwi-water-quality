import pandas as pd


def load_data(path: str) -> pd.DataFrame:
    """Load the per-visit Data sheet from the anonymized workbook."""
    return pd.read_excel(path, sheet_name="Data")


def load_events(path: str) -> pd.DataFrame:
    """Load the one-row-per-OOR-event sheet from the anonymized workbook."""
    return pd.read_excel(path, sheet_name="OOR Events")


def describe_data(data: pd.DataFrame, events: pd.DataFrame) -> None:
    """Print a basic overview of the loaded dataset."""
    print("=" * 60)
    print("DATASET OVERVIEW")
    print("=" * 60)
    print(f"Visits: {len(data)} rows x {data.shape[1]} cols")
    print(f"Unique ponds: {data['Pond ID'].nunique()}")
    print(f"OOR events: {len(events)}")
    print()
    print("Visits by group:")
    print(data["Pond status"].value_counts().to_string())
    print()
    print("OOR events by group:")
    print(events["Group"].value_counts().to_string())
    print()


def reorder_by_pond(src: str, dst: str) -> None:
    """Sort the Data sheet by Pond ID, copying the other sheets verbatim."""
    # Data: stable sort, so order within a pond is preserved.
    data = pd.read_excel(src, sheet_name="Data").sort_values("Pond ID", kind="stable")

    # Other sheets: header=None keeps every cell exactly as-is.
    overview = pd.read_excel(src, sheet_name="Overview", header=None)
    oor = pd.read_excel(src, sheet_name="OOR Events", header=None)

    with pd.ExcelWriter(dst) as writer:
        overview.to_excel(writer, sheet_name="Overview", index=False, header=False)
        data.to_excel(writer, sheet_name="Data", index=False)
        oor.to_excel(writer, sheet_name="OOR Events", index=False, header=False)
