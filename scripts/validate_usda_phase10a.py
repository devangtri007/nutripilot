#!/usr/bin/env python3
"""Validate USDA Foundation/FNDDS normalized tables before promotion.

Validation distinguishes required structural integrity from optional USDA
nutrient availability. Foundation Foods explicitly does not provide every
nutrient for every food, so missing fiber/calorie values are not automatically
a dataset failure. The ingestion step may derive calories from complete
protein/fat/carbohydrate values using USDA's documented Atwater 4/9/4 factors.
"""
import argparse
from pathlib import Path
import pandas as pd

REQUIRED = [
    "food", "category", "calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g",
    "meal_types", "season", "regions", "diet", "source_system", "source_id",
    "source_version", "data_basis", "license",
]
CORE_MACROS = ["protein_g", "carbs_g", "fat_g"]
OPTIONAL_NUTRIENTS = ["calories_kcal", "fiber_g"]


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

    print(f"Checking {path}: {len(df):,} records")

    # Negative carbohydrate-by-difference values should already have been
    # normalized by ingestion. If any remain, stop rather than promoting
    # physically meaningless values into the recipe nutrition engine.
    carbs = pd.to_numeric(df["carbs_g"], errors="coerce")
    remaining_negative_carbs = (carbs.dropna() < 0).sum()
    print(f"  negative carbs remaining after normalization: {remaining_negative_carbs}")
    if remaining_negative_carbs:
        raise SystemExit(f"{path}: negative values remain in carbs_g after ingestion normalization")

    # Core macros are important for deterministic recipe nutrition, but USDA
    # does not promise complete nutrient coverage for every Foundation food.
    for col in CORE_MACROS:
        values = pd.to_numeric(df[col], errors="coerce")
        coverage = values.notna().mean()
        print(f"  {col}: {coverage:.1%} numeric coverage")
        if (values.dropna() < 0).any():
            raise SystemExit(f"{path}: negative values found in {col}")

    for col in OPTIONAL_NUTRIENTS:
        values = pd.to_numeric(df[col], errors="coerce")
        coverage = values.notna().mean()
        print(f"  {col}: {coverage:.1%} numeric coverage (informational)")
        if (values.dropna() < 0).any():
            raise SystemExit(f"{path}: negative values found in {col}")

    macro_complete = df[CORE_MACROS].apply(pd.to_numeric, errors="coerce").notna().all(axis=1)
    calories_complete = pd.to_numeric(df["calories_kcal"], errors="coerce").notna()
    print(f"  complete core-macro rows: {macro_complete.mean():.1%}")
    print(f"  usable nutrition rows (macros + kcal): {(macro_complete & calories_complete).mean():.1%}")

    # Structural/data-integrity checks are the hard gate. Nutrient sparsity is
    # reported rather than rejected because USDA Foundation Foods documents
    # that not all nutrients are available for every food.
    if macro_complete.mean() < 0.80:
        raise SystemExit(f"{path}: core macro coverage is only {macro_complete.mean():.1%}; review ingestion")

    print(f"PASS {path}: structural validation passed")
    print(df[[*CORE_MACROS, *OPTIONAL_NUTRIENTS]].apply(pd.to_numeric, errors="coerce").describe().loc[["mean", "min", "max"]].to_string())


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
