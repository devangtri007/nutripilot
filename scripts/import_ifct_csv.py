#!/usr/bin/env python3
"""Normalize an approved structured IFCT 2017 export.

This script intentionally does not scrape or extract the official IFCT PDF.
"""

import argparse
from pathlib import Path
import pandas as pd

REQUIRED = [
    "food", "category", "calories_kcal", "protein_g", "carbs_g",
    "fat_g", "fiber_g", "meal_types", "season", "regions", "diet",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="data/ifct_foods.csv")
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    missing = [c for c in REQUIRED if c not in frame.columns]
    if missing:
        raise SystemExit("Missing columns: " + ", ".join(missing))

    frame["source_system"] = "ICMR-NIN IFCT 2017"
    frame["source_id"] = frame["food"].astype(str).map(
        lambda x: "ifct2017:" + x.strip().lower().replace(" ", "_")
    )
    frame["source_version"] = "IFCT 2017"
    frame["data_basis"] = "ICMR-NIN IFCT 2017 structured approved import"
    frame["license"] = "Verify applicable publication/data-use terms"

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    print(f"Wrote {len(frame)} IFCT records to {output}")


if __name__ == "__main__":
    main()
