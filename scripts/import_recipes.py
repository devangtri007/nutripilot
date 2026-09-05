#!/usr/bin/env python3
"""Import a governed structured recipe CSV into NutriPilot's recipe catalogue."""
import argparse
from pathlib import Path
import pandas as pd

REQUIRED = [
    "recipe_id", "name", "meal_type", "cuisine", "regions", "season", "diet",
    "goal_tags", "weather_tags", "ingredients", "prep_time_min", "cook_time_min",
    "total_time_min", "difficulty",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="data/recipes.csv")
    parser.add_argument("--foods", default="data/foods.csv")
    args = parser.parse_args()

    incoming = pd.read_csv(args.input, low_memory=False)
    missing = [c for c in REQUIRED if c not in incoming.columns]
    if missing:
        raise SystemExit("Recipe file missing columns: " + ", ".join(missing))
    if incoming["recipe_id"].duplicated().any():
        raise SystemExit("Recipe IDs must be unique inside the imported file.")

    foods = pd.read_csv(args.foods, low_memory=False)
    food_names = set(foods["food"].astype(str).str.strip())
    bad = []
    for _, row in incoming.iterrows():
        for token in str(row["ingredients"]).split(";"):
            if not token.strip():
                continue
            try:
                name, grams = token.rsplit(":", 1)
                float(grams)
            except ValueError:
                bad.append((row["recipe_id"], token))
                continue
            if name.strip() not in food_names:
                bad.append((row["recipe_id"], name.strip()))
    if bad:
        sample = "; ".join(f"{rid}: {name}" for rid, name in bad[:20])
        raise SystemExit("Recipe ingredients not present in foods.csv: " + sample)

    output = Path(args.output)
    if output.exists():
        existing = pd.read_csv(output, low_memory=False)
        existing = existing[~existing["recipe_id"].astype(str).isin(incoming["recipe_id"].astype(str))]
        merged = pd.concat([existing, incoming[REQUIRED]], ignore_index=True)
    else:
        merged = incoming[REQUIRED].copy()
    merged.to_csv(output, index=False)
    print(f"Recipe catalogue now contains {len(merged):,} recipes")


if __name__ == "__main__":
    main()
