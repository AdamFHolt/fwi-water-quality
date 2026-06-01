#!/usr/bin/env python3
from src.functions import reorder_by_pond

SRC = "data/Outcome Evaluation Phase 2 Data_Cleaned And Anonymized.xlsx"
DST = "data/Outcome Evaluation Phase 2 Data_Cleaned And Anonymized.reordered.xlsx"

if __name__ == "__main__":
    reorder_by_pond(SRC, DST)
    print(f"Wrote {DST} (Data sorted by Pond ID; other sheets copied verbatim)")
