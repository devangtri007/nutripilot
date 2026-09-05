#!/usr/bin/env python3
"""Normalize USDA FoodData Central bulk CSV archives into NutriPilot tables.

Foundation Foods note:
-----------------------
The Foundation archive contains both the 394 published Foundation foods and
many supporting/source foods used by those records.  Those supporting foods
are present in food.csv but are NOT themselves Foundation Foods.  Therefore,
Foundation ingestion must filter food.csv through foundation_food.csv before
building the canonical table.

Current Foundation Foods use nutrient IDs 2047/2048 for metabolizable energy;
FNDDS uses the FDC nutrient IDs mapped from its nutrient codes. Foundation
carbohydrate is carbohydrate-by-difference; rare negative values are normalized
to zero for the canonical application table and explicitly marked in data_basis.
"""
import argparse
from pathlib import Path
import zipfile
import tempfile
import pandas as pd

# FoodData Central nutrient IDs vary by data type.
# Foundation Foods use 2047/2048 for energy; FNDDS retains the
# traditional FNDDS nutrient codes (208=energy, 203=protein,
# 205=carbohydrate, 204=fat, 291=fiber). The FDC download
# may also contain the newer 100x IDs, so we support both.
NUTRIENTS = {
    # Energy
    1008: "calories_1008",
    2047: "calories_2047",
    2048: "calories_2048",
    208: "calories_fndds",
    # Macronutrients
    1003: "protein_g",
    203: "protein_g",
    1005: "carbs_g",
    205: "carbs_g",
    1004: "fat_g",
    204: "fat_g",
    # Fiber
    1079: "fiber_g",
    291: "fiber_g",
}

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


def _foundation_ids(root):
    """Return only FDC IDs that are actual Foundation Foods records."""
    path = find_csv(root, "foundation_food.csv")
    foundation = pd.read_csv(path, low_memory=False)
    if "fdc_id" not in foundation.columns:
        raise ValueError("foundation_food.csv does not contain fdc_id")
    return set(pd.to_numeric(foundation["fdc_id"], errors="coerce").dropna().astype("int64"))


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

        # Foundation archive: food.csv also contains supporting/source foods.
        # Keep only the foods explicitly listed in foundation_food.csv.
        is_foundation = "foundation" in source_system.lower()
        if is_foundation:
            foundation_ids = _foundation_ids(tmp)
            foods["fdc_id"] = pd.to_numeric(foods["fdc_id"], errors="coerce")
            foods = foods[foods["fdc_id"].isin(foundation_ids)].copy()
            if foods.empty:
                raise ValueError("No Foundation Foods found after filtering foundation_food.csv")

        nutrients["fdc_id"] = pd.to_numeric(nutrients["fdc_id"], errors="coerce")
        nutrients["nutrient_id"] = pd.to_numeric(nutrients["nutrient_id"], errors="coerce")
        nutrients = nutrients[nutrients["nutrient_id"].isin(NUTRIENTS)].copy()
        nutrients["field"] = nutrients["nutrient_id"].map(NUTRIENTS)
        nutrients["value_num"] = pd.to_numeric(nutrients.get("amount"), errors="coerce")

        pivot = (
            nutrients.pivot_table(
                index="fdc_id", columns="field", values="value_num", aggfunc="first"
            )
            .reset_index()
            .rename(columns={"fdc_id": "source_id"})
        )

        # Guarantee every canonical nutrient column exists even when a data type
        # does not publish that nutrient ID. This is especially important for
        # FNDDS, whose traditional nutrient codes differ from Foundation Foods.
        for col in [
            "calories_2048", "calories_2047", "calories_1008", "calories_fndds",
            "protein_g", "carbs_g", "fat_g", "fiber_g",
        ]:
            if col not in pivot.columns:
                pivot[col] = pd.NA

        # Foundation Foods carbohydrate is "carbohydrate by difference".
        # Because this is calculated from several measured proximates, USDA
        # data can contain small negative values caused by analytical error/
        # rounding. A negative amount is not meaningful for NutriPilot's
        # deterministic nutrition engine, so normalize it to zero and record
        # the transformation in data_basis below.
        pivot["carbs_g"] = pd.to_numeric(pivot["carbs_g"], errors="coerce")
        negative_carb = pivot["carbs_g"].lt(0).fillna(False)
        pivot["carbs_negative_normalized"] = negative_carb
        pivot.loc[negative_carb, "carbs_g"] = 0.0

        # Select the first available USDA energy field without relying on
        # chained combine_first calls (which can emit pandas warnings when
        # some candidate columns are entirely empty).
        energy_candidates = [
            "calories_2048", "calories_2047", "calories_1008", "calories_fndds"
        ]
        pivot["calories_kcal"] = (
            pivot[energy_candidates]
            .bfill(axis=1)
            .iloc[:, 0]
        )

        # If USDA does not publish an energy value but all three macronutrients
        # are available, derive kcal using the same Atwater general factors
        # documented by USDA: 4 kcal/g protein, 9 kcal/g fat, 4 kcal/g carbs.
        # This is a derived value, not a claim that USDA published that kcal
        # value directly. We preserve that distinction in data_basis below.
        direct_energy_missing = pivot["calories_kcal"].isna()
        derivable_energy = (
            direct_energy_missing
            & pivot["protein_g"].notna()
            & pivot["fat_g"].notna()
            & pivot["carbs_g"].notna()
        )
        pivot.loc[derivable_energy, "calories_kcal"] = (
            4.0 * pivot.loc[derivable_energy, "protein_g"]
            + 9.0 * pivot.loc[derivable_energy, "fat_g"]
            + 4.0 * pivot.loc[derivable_energy, "carbs_g"]
        )
        pivot["energy_derived"] = derivable_energy

        frame = foods[["fdc_id", "description"]].copy()
        frame = frame.rename(columns={"description": "food", "fdc_id": "source_id"})
        frame = frame.merge(pivot, on="source_id", how="left")

        if "carbs_negative_normalized" not in frame.columns:
            frame["carbs_negative_normalized"] = False
        frame["carbs_negative_normalized"] = frame["carbs_negative_normalized"].fillna(False).astype(bool)

        for field in ["calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"]:
            if field not in frame.columns:
                frame[field] = pd.NA

        if category_path is not None and "food_category_id" in foods.columns:
            categories = pd.read_csv(category_path, low_memory=False)
            if {"id", "description"}.issubset(categories.columns):
                categories = categories.rename(columns={"id": "food_category_id", "description": "category"})
                category_map = categories[["food_category_id", "category"]].drop_duplicates()
                frame = frame.merge(
                    foods[["fdc_id", "food_category_id"]],
                    left_on="source_id", right_on="fdc_id", how="left"
                )
                frame = frame.merge(category_map, on="food_category_id", how="left")

        if "category" not in frame.columns:
            frame["category"] = default_category
        frame["category"] = frame["category"].fillna(default_category)
        frame["meal_types"] = "Breakfast;Lunch;Dinner;Snack"
        frame["season"] = "All"
        frame["regions"] = "Global"
        frame["diet"] = "Unknown"
        frame["source_system"] = source_system
        frame["source_id"] = frame["source_id"].astype("Int64").astype(str)
        frame["source_version"] = source_version
        frame["data_basis"] = "USDA FoodData Central per 100 g"
        if "energy_derived" in frame.columns:
            frame.loc[frame["energy_derived"].eq(True), "data_basis"] = (
                "USDA FoodData Central per 100 g; calories derived using Atwater general factors (4/9/4)"
            )

        # Preserve provenance of the carbohydrate cleanup without adding a
        # new schema column. This makes the canonical value auditable.
        frame.loc[frame["carbs_negative_normalized"].eq(True), "data_basis"] = (
            frame.loc[frame["carbs_negative_normalized"].eq(True), "data_basis"]
            + "; negative carbohydrate-by-difference normalized to 0 g"
        )

        for flag in ["energy_derived", "carbs_negative_normalized"]:
            if flag in frame.columns:
                frame = frame.drop(columns=[flag])
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
