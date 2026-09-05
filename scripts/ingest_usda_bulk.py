#!/usr/bin/env python3
"""Normalize USDA FoodData Central bulk CSV archives into NutriPilot tables.

This parser is deliberately schema-tolerant: USDA archive folders contain
food.csv, food_nutrient.csv, nutrient.csv and related tables. The script only
needs the food and food_nutrient tables and maps the core nutrient IDs used by
NutriPilot.
"""
import argparse
from pathlib import Path
import zipfile
import tempfile
import pandas as pd

NUTRIENTS = {1008: "calories_kcal", 1003: "protein_g", 1005: "carbs_g", 1004: "fat_g", 1079: "fiber_g"}
CANONICAL = [
    "food", "category", "calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g",
    "meal_types", "season", "regions", "diet", "source_system", "source_id",
    "source_version", "data_basis", "license",
]


def find_csv(root, name):
    matches = list(Path(root).rglob(name))
    if not matches:
        raise FileNotFoundError(f"Could not find {name} in USDA archive")
    return matches[0]


def normalize_archive(archive, source_system, source_version, output, default_category="USDA"):
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
        food_path = find_csv(tmp, "food.csv")
        nutrient_path = find_csv(tmp, "food_nutrient.csv")
        category_path = next(iter(Path(tmp).rglob("food_category.csv")), None)

        foods = pd.read_csv(food_path, low_memory=False)
        nutrients = pd.read_csv(nutrient_path, low_memory=False)
        if "fdc_id" not in foods.columns or "description" not in foods.columns:
            raise ValueError("USDA food.csv does not contain fdc_id/description")
        if "fdc_id" not in nutrients.columns or "nutrient_id" not in nutrients.columns:
            raise ValueError("USDA food_nutrient.csv does not contain fdc_id/nutrient_id")

        nutrients = nutrients[nutrients["nutrient_id"].isin(NUTRIENTS)].copy()
        nutrients["field"] = nutrients["nutrient_id"].map(NUTRIENTS)
        # USDA nutrient rows may have amount/derivation fields; amount is the
        # numeric nutrient value per 100 g for these core nutrient records.
        nutrients["value_num"] = pd.to_numeric(nutrients.get("amount"), errors="coerce")
        pivot = nutrients.pivot_table(index="fdc_id", columns="field", values="value_num", aggfunc="first").reset_index()
        pivot = pivot.rename(columns={"fdc_id": "source_id"})

        frame = foods[["fdc_id", "description"]].copy()
        frame = frame.rename(columns={"description": "food", "fdc_id": "source_id"})
        frame = frame.merge(pivot, on="source_id", how="left")
        for field in NUTRIENTS.values():
            if field not in frame.columns:
                frame[field] = pd.NA

        if category_path is not None:
            categories = pd.read_csv(category_path, low_memory=False)
            if {"id", "description"}.issubset(categories.columns) and "food_category_id" in foods.columns:
                categories = categories.rename(columns={"id": "food_category_id", "description": "category"})
                frame = frame.merge(foods[["fdc_id", "food_category_id"]], left_on="source_id", right_on="fdc_id", how="left")
                frame = frame.merge(categories[["food_category_id", "category"]], on="food_category_id", how="left")
        if "category" not in frame.columns:
            frame["category"] = default_category
        frame["category"] = frame["category"].fillna(default_category)
        frame["meal_types"] = "Breakfast;Lunch;Dinner;Snack"
        frame["season"] = "All"
        frame["regions"] = "Global"
        frame["diet"] = "Unknown"
        frame["source_system"] = source_system
        frame["source_id"] = frame["source_id"].astype(str)
        frame["source_version"] = source_version
        frame["data_basis"] = "USDA FoodData Central per 100 g"
        frame["license"] = "USDA FoodData Central; verify applicable dataset terms"
        frame = frame[CANONICAL]
        frame = frame.dropna(subset=["food"]).drop_duplicates(subset=["source_system", "source_id"])
        frame.to_csv(output, index=False)
        print(f"Wrote {len(frame):,} records to {output}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--source-system", required=True)
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    normalize_archive(Path(args.archive), args.source_system, args.source_version, Path(args.output))


if __name__ == "__main__":
    main()
