#!/usr/bin/env python3
"""Validate USDA Foundation/FNDDS normalized tables before promotion."""
import argparse
from pathlib import Path
import pandas as pd

REQUIRED = [
    "food", "category", "calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g",
    "meal_types", "season", "regions", "diet", "source_system", "source_id",
    "source_version", "data_basis", "license",
]
NUMERIC = ["calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"]

def validate(path, expected_source):
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"Missing input: {path}")
    df = pd.read_csv(path, low_memory=False)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SystemExit(f"{path}: missing columns: {', '.join(missing)}")
    if df.empty:
        raise SystemExit(f"{path}: no records")
    if df["source_system"].nunique() != 1 or df["source_system"].iloc[0] != expected_source:
        raise SystemExit(f"{path}: unexpected source_system")
    if df["source_id"].duplicated().any():
        raise SystemExit(f"{path}: duplicate source_id values")
    for col in NUMERIC:
        values = pd.to_numeric(df[col], errors="coerce")
        coverage = values.notna().mean()
        if coverage < 0.95:
            raise SystemExit(f"{path}: {col} numeric coverage is only {coverage:.1%}")
        if (values.dropna() < 0).any():
            raise SystemExit(f"{path}: negative values found in {col}")
    print(f"PASS {path}: {len(df):,} records; nutrient coverage >=95%")
    print(df[NUMERIC].describe().loc[["mean", "min", "max"]].to_string())

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--foundation", default="data/usda_foundation_foods.csv")
    p.add_argument("--fndds", default="data/usda_fndds_foods.csv")
    args = p.parse_args()
    validate(args.foundation, "USDA FoodData Central Foundation")
    validate(args.fndds, "USDA FoodData Central FNDDS")
    print("Phase 10A USDA validation passed.")

if __name__ == "__main__":
    main()
