#!/usr/bin/env python3
import pandas as pd

SRC = "data/Outcome Evaluation Phase 2 Data_Cleaned And Anonymized.xlsx"
DST = "data/Outcome Evaluation Phase 2 Data_Cleaned And Anonymized.reordered.xlsx"

# Data: sort by Pond ID (stable, so order within a pond is preserved)
data = pd.read_excel(SRC, sheet_name="Data")
data = data.sort_values("Pond ID", kind="stable")

# Other sheets: copy verbatim (header=None keeps every cell exactly as-is)
overview = pd.read_excel(SRC, sheet_name="Overview", header=None)
oor = pd.read_excel(SRC, sheet_name="OOR Events", header=None)

with pd.ExcelWriter(DST) as writer:
    overview.to_excel(writer, sheet_name="Overview", index=False, header=False)
    data.to_excel(writer, sheet_name="Data", index=False)
    oor.to_excel(writer, sheet_name="OOR Events", index=False, header=False)

print(f"Wrote {DST} (Data sorted by Pond ID; other sheet just copied over)")
