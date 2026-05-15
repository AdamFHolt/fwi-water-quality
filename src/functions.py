import pandas as pd

COLUMN_RENAME = {
    "Sr. No": "record_id",
    "Date of data collection": "date",
    "Time of data collection": "time",
    "Pond ID": "pond_id",
    "Farmer": "farmer",
    "Type": "visit_type",
    "Is follow up": "is_followup",
    "Is follow up possible": "followup_possible",
    "Reason follow up not possible": "followup_not_possible_reason",
    "Group": "group",
    "Pond status": "treatment_group",
    "Observer": "observer",
    "Equipment": "equipment",
    "Weather": "weather",
    "DO (mg/L)": "do_mgl",
    "pH": "ph",
    "Turbidity (in cm)": "turbidity_cm",
    "Ammonia—TAN (NH3-N) (mg/L)": "tan_nh3n_mgl",
    "Ammonia—TAN (NH3) (mg/L)": "tan_nh3_mgl",
    "Ammonia—NH3 (mg/L)": "nh3_mgl",
    "Temp (in °C)": "temp_c",
    "TDS (ppt)": "tds_ppt",
    "Alkalinity (mg/L)": "alkalinity_mgl",
    "Hardness (mg/L)": "hardness_mgl",
    "Water color": "water_color",
    "Is WQ in range?": "wq_in_range",
    "Parameters out of range": "params_out_of_range",
    "Corrective actions requested": "ca_requested",
    "Corrective actions requested (other)": "ca_requested_other",
    "Corrective actions amount requested": "ca_amount_requested",
    "Corrective actions": "corrective_actions",
    "Corrective actions implemented": "ca_implemented",
    "Corrective actions implementation date": "ca_implementation_date",
    "Corrective actions taken": "ca_taken",
    "Corrective actions taken (other)": "ca_taken_other",
    "Corrective actions taken (details)": "ca_taken_details",
    "Non-prescribed corrective actions taken": "non_prescribed_ca",
    "Reason not implemented": "reason_not_implemented",
    "Water quality improved after corrective actions": "wq_improved_after_ca",
    "Corrective action notes": "ca_notes",
    "Individuals air gulping": "individuals_air_gulping",
    "Individuals tail splashing": "individuals_tail_splashing",
    "Dead fish": "dead_fish",
    "Notes (mortalities)": "notes_mortalities",
    "Self-initiated corrective actions taken": "self_ca_taken",
    "Self-initiated corrective actions implemented on (exact date)": "self_ca_impl_date",
    "Self-initiated corrective actions implemented (date range)": "self_ca_impl_date_range",
    "Self-initiated corrective actions notes": "self_ca_notes",
    "Feed amount (kg)": "feed_kg",
    "Stocking density (per acre)": "stocking_density_per_acre",
    "Species": "species",
    "Weight": "weight",
    "Notes": "notes",
    "Have fish been helped": "fish_helped",
}

WQ_PARAMS = ["do_mgl", "ph", "turbidity_cm", "tan_nh3n_mgl", "tan_nh3_mgl",
             "nh3_mgl", "temp_c", "tds_ppt", "alkalinity_mgl", "hardness_mgl"]

CATEGORICAL_COLS = ["treatment_group", "visit_type", "is_followup", "weather",
                    "wq_in_range", "water_color", "observer"]


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Sheet1", dtype=str)
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_RENAME)

    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y", errors="coerce")

    for col in WQ_PARAMS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["individuals_air_gulping", "individuals_tail_splashing",
                "dead_fish", "feed_kg", "stocking_density_per_acre", "weight"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    bool_map = {"Yes": True, "No": False}
    for col in ["is_followup", "followup_possible", "wq_in_range"]:
        if col in df.columns:
            df[col] = df[col].map(bool_map)

    return df


def describe_data(df: pd.DataFrame) -> None:
    print("=" * 60)
    print("DATASET OVERVIEW")
    print("=" * 60)
    print(f"Rows: {df.shape[0]}  |  Columns: {df.shape[1]}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Unique ponds: {df['pond_id'].nunique()}")
    print(f"Unique farmers: {df['farmer'].nunique()}")
    print()

    print("Treatment group breakdown:")
    print(df["treatment_group"].value_counts().to_string())
    print()


def describe_water_quality(df: pd.DataFrame) -> None:
    present = [c for c in WQ_PARAMS if c in df.columns]
    stats = df[present].describe().T
    stats["missing_pct"] = (df[present].isnull().mean() * 100).round(1)

    print("=" * 60)
    print("WATER QUALITY PARAMETERS — DESCRIPTIVE STATS")
    print("=" * 60)
    print(stats[["count", "mean", "std", "min", "50%", "max", "missing_pct"]].to_string())
    print()

    print("By treatment group (mean):")
    print(df.groupby("treatment_group")[present].mean().round(3).to_string())
    print()

