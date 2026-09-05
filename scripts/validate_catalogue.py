#!/usr/bin/env python3
"""Validate food and recipe tables before deployment."""
import argparse
from pathlib import Path
import pandas as pd


def parse_ingredients(value):
    items=[]
    for token in str(value).split(";"):
        if not token.strip(): continue
        name, grams = token.rsplit(":", 1)
        items.append(name.strip())
    return items


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--foods",default="data/foods.csv")
    parser.add_argument("--recipes",default="data/recipes.csv")
    args=parser.parse_args()
    foods=pd.read_csv(args.foods,low_memory=False)
    recipes=pd.read_csv(args.recipes,low_memory=False)
    required={"food","calories_kcal","protein_g","carbs_g","fat_g","fiber_g","source_system","source_id","source_version","data_basis","license"}
    missing=required-set(foods.columns)
    if missing: raise SystemExit("Food schema missing: "+", ".join(sorted(missing)))
    names=set(foods["food"].astype(str).str.strip())
    errors=[]
    for _,row in recipes.iterrows():
        missing_foods=[x for x in parse_ingredients(row["ingredients"]) if x not in names]
        if missing_foods: errors.append((row["recipe_id"],missing_foods))
    print(f"Foods: {len(foods):,}")
    print(f"Recipes: {len(recipes):,}")
    print(f"Sources: {foods['source_system'].nunique():,}")
    if errors:
        for rid,miss in errors[:25]: print(f"{rid}: {', '.join(miss)}")
        raise SystemExit(f"Validation failed: {len(errors)} recipes have missing ingredients")
    print("Catalogue validation passed.")

if __name__ == "__main__": main()
