#!/usr/bin/env python3

import pandas as pd
from matplotlib import pyplot as plt
from matplotlib_venn import venn3
from pathlib import Path

def main():
    base_path = Path(__file__).parent
    files = [
        base_path / "commons-cli-manual-inspection.tsv",
        base_path / "commons-csv-manual-inspection.tsv",
        base_path / "commons-fileupload-manual-inspection.tsv"
    ]
    
    dfs = []
    for f in files:
        df = pd.read_csv(f, sep="\t", dtype=str)
        df.columns = df.columns.str.strip()
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    for col in ["Graal", "Mock", "Manual Inspection"]:
        df[col] = df[col].str.strip().str.capitalize()

    if "AMF" not in df.columns:
        print("Available columns:", list(df.columns))
        raise KeyError("Column 'AMF' not found — please check the header name in your TSVs.")

    graal_set = set(df.loc[df["Graal"] == "Success", "AMF"])
    mock_set = set(df.loc[df["Mock"] == "Success", "AMF"])
    manual_set = set(df.loc[df["Manual Inspection"] == "Success", "AMF"])

    venn3([graal_set, mock_set, manual_set],
          set_labels=("Graal", "Mock", "Manual"))

    plt.title("Success Overlap Across Graal, Mock, and Manual Inspection")
    plt.show()

    print("Graal only:", len(graal_set - mock_set - manual_set))
    print("Mock only:", len(mock_set - graal_set - manual_set))
    print("Manual only:", len(manual_set - graal_set - mock_set))
    print("Graal & Mock:", len(graal_set & mock_set - manual_set))
    print("Graal & Manual:", len(graal_set & manual_set - mock_set))
    print("Mock & Manual:", len(mock_set & manual_set - graal_set))
    print("All three:", len(graal_set & mock_set & manual_set))

if __name__ == "__main__":
    main()
