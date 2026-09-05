#!/usr/bin/env python3
"""Ingest selected USDA FoodData Central records into NutriPilot's canonical schema.

Example:
  export USDA_FDC_API_KEY="your-key"
  python scripts/ingest_usda.py --query "oats" --query "chickpeas"
"""

import argparse
import os
from pathlib import Path
import time
import pandas as pd
import requests

SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

NUTRIENT_MAP = {
    1008: "calories_kcal",
    1003: "protein_g",
    1005: "carbs_g",
    1004: "fat_g",
    1079: "fiber_g",
}

CANONICAL = [
    "food", "category", "calories_kcal", "protein_g", "carbs_g", "fat_g",
    "fiber_g", "meal_types", "season", "regions", "diet",
    "source_system", "source_id", "source_version", "data_basis", "license",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", action="append", required=True)
    parser.add_argument("--output", default="data/usda_foods.csv")
    parser.add_argument("--page-size", type=int, default=5)
    return parser.parse_args()


def nutrient_values(food):
    result = {field: None for field in NUTRIENT_MAP.values()}
    for nutrient in food.get("foodNutrients", []):
        field = NUTRIENT_MAP.get(nutrient.get("nutrientId"))
        if field:
            result[field] = nutrient.get("value")
    return result


def main():
    args = parse_args()
    api_key = os.getenv("USDA_FDC_API_KEY")
    if not api_key:
        raise SystemExit("USDA_FDC_API_KEY is not set.")

    session = requests.Session()
    rows = []

    for query in args.query:
        response = session.get(
            SEARCH_URL,
            params={
                "api_key": api_key,
                "query": query,
                "pageSize": args.page_size,
                "dataType": "Foundation,SR Legacy",
            },
            timeout=30,
        )
        response.raise_for_status()
        matches = response.json().get("foods", [])
        if not matches:
            print(f"No USDA match: {query}")
            continue

        food = matches[0]
        nutrients = nutrient_values(food)
        if any(value is None for value in nutrients.values()):
            print(f"Skipping incomplete USDA match: {food.get('description')}")
            continue

        rows.append({
            "food": food["description"].strip(),
            "category": "USDA",
            **nutrients,
            "meal_types": "Breakfast;Lunch;Dinner;Snack",
            "season": "All",
            "regions": "Global",
            "diet": "Non-vegetarian",
            "source_system": "USDA FoodData Central",
            "source_id": str(food["fdcId"]),
            "source_version": str(food.get("dataType", "unknown")),
            "data_basis": "USDA FoodData Central per 100 g",
            "license": "CC0 1.0 Universal",
        })
        time.sleep(0.2)

    if not rows:
        raise SystemExit("No foods were successfully ingested.")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=CANONICAL).drop_duplicates(
        subset=["source_system", "source_id"]
    ).to_csv(output, index=False)
    print(f"Wrote {len(rows)} USDA records to {output}")


if __name__ == "__main__":
    main()
