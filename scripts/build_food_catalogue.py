#!/usr/bin/env python3
"""Build the NutriPilot canonical ingredient catalogue from governed sources.

Inputs are optional. The script always retains the existing prototype catalogue
so the app remains runnable, then adds approved source tables when present.
"""
import argparse
from pathlib import Path
import re
import pandas as pd

REQUIRED = [
    "food", "category", "calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g",
    "meal_types", "season", "regions", "diet", "source_system", "source_id",
    "source_version", "data_basis", "license",
]
PRIORITY = {"ICMR-NIN IFCT 2017": 1, "USDA FoodData Central Foundation": 2, "USDA FoodData Central FNDDS": 3, "NutriPilot prototype seed": 9}


def norm(value):
    value = str(value or "").strip().casefold()
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def read_optional(path):
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=REQUIRED)
    frame = pd.read_csv(p, low_memory=False)
    missing = [c for c in REQUIRED if c not in frame.columns]
    if missing:
        raise SystemExit(f"{p} missing columns: {', '.join(missing)}")
    return frame[REQUIRED].copy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prototype", default="data/foods.csv")
    parser.add_argument("--ifct", default="data/ifct_foods.csv")
    parser.add_argument("--usda-foundation", default="data/usda_foundation_foods.csv")
    parser.add_argument("--usda-fndds", default="data/usda_fndds_foods.csv")
    parser.add_argument("--output", default="data/foods.csv")
    args = parser.parse_args()

    frames = [read_optional(args.prototype), read_optional(args.ifct), read_optional(args.usda_foundation), read_optional(args.usda_fndds)]
    frame = pd.concat(frames, ignore_index=True)
    frame["_priority"] = frame["source_system"].map(PRIORITY).fillna(8)
    frame["_norm"] = frame["food"].map(norm)
    frame = frame.sort_values(["_norm", "_priority", "source_id"])
    frame = frame.drop_duplicates(subset=["_norm"], keep="first")
    frame = frame.drop(columns=["_priority", "_norm"])
    frame.to_csv(args.output, index=False)
    print(f"Built {len(frame):,} canonical ingredient records at {args.output}")
    print(frame.groupby("source_system").size().sort_values(ascending=False).to_string())


if __name__ == "__main__":
    main()
