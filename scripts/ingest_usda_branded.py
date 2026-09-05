#!/usr/bin/env python3
"""Normalize USDA FoodData Central Branded Foods into data/products.csv.

Branded products are deliberately kept separate from ingredient foods. They can
be searched/recommended as packaged products without becoming recipe
ingredients automatically.
"""
import argparse
from pathlib import Path
import zipfile
import tempfile
import pandas as pd

NUTRIENTS = {1008: "calories_kcal", 1003: "protein_g", 1005: "carbs_g", 1004: "fat_g", 1079: "fiber_g"}
COLUMNS = [
    "product_id", "product_name", "brand", "category", "barcode", "serving_size_g",
    "calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "source_system",
    "source_id", "source_version", "data_basis", "license",
]


def find_csv(root, name):
    matches = list(Path(root).rglob(name))
    if not matches:
        raise FileNotFoundError(f"Could not find {name} in archive")
    return matches[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--output", default="data/products.csv")
    parser.add_argument("--source-version", default="2026-04")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(args.archive) as zf:
            zf.extractall(tmp)
        branded_path = find_csv(tmp, "branded_food.csv")
        nutrient_path = find_csv(tmp, "food_nutrient.csv")
        branded = pd.read_csv(branded_path, low_memory=False)
        nutrients = pd.read_csv(nutrient_path, low_memory=False)

        required = {"fdc_id"}
        if not required.issubset(branded.columns):
            raise SystemExit("branded_food.csv is missing fdc_id")
        nutrients = nutrients[nutrients["nutrient_id"].isin(NUTRIENTS)].copy()
        nutrients["field"] = nutrients["nutrient_id"].map(NUTRIENTS)
        nutrients["value_num"] = pd.to_numeric(nutrients.get("amount"), errors="coerce")
        pivot = nutrients.pivot_table(index="fdc_id", columns="field", values="value_num", aggfunc="first").reset_index()
        frame = branded.merge(pivot, on="fdc_id", how="left")

        def first_col(*names):
            for name in names:
                if name in frame.columns:
                    return frame[name].fillna("").astype(str).str.strip()
            return pd.Series([""] * len(frame))

        out = pd.DataFrame()
        out["product_id"] = frame["fdc_id"].astype(str)
        out["product_name"] = first_col("description")
        brand = first_col("brand_name", "brand_owner")
        owner = first_col("brand_owner")
        out["brand"] = brand.where(brand.ne(""), owner)
        out["category"] = first_col("branded_food_category")
        out["barcode"] = first_col("gtin_upc", "gtin_upc_code")
        out["serving_size_g"] = pd.to_numeric(first_col("serving_size"), errors="coerce")
        for field in ["calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"]:
            out[field] = pd.to_numeric(frame.get(field), errors="coerce")
        out["source_system"] = "USDA FoodData Central Branded"
        out["source_id"] = frame["fdc_id"].astype(str)
        out["source_version"] = args.source_version
        out["data_basis"] = "USDA FoodData Central branded label data"
        out["license"] = "CC0 1.0 Universal"
        out = out[COLUMNS].drop_duplicates(subset=["source_id"])
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(args.output, index=False)
        print(f"Wrote {len(out):,} branded products to {args.output}")


if __name__ == "__main__":
    main()
