# NutriPilot Phase 10 — Comprehensive Food & Product Data Layer

Phase 10 changes NutriPilot from a small prototype food list into a governed,
source-aware catalogue pipeline.

## What is covered

### Ingredient foods
- USDA FoodData Central Foundation Foods
- USDA FNDDS survey foods
- Existing NutriPilot seed foods retained as a fallback
- ICMR-NIN IFCT 2017 through an approved structured import
- Alias/entity-resolution layer for common names and Indian regional terms

### Food products
- USDA FoodData Central Branded Foods is supported as a separate product layer.
- Product records are intentionally kept separate from recipe ingredients.
- The current app package contains the product schema and ingestion path, not the
  multi-gigabyte USDA branded archive.

### Recipes
- Existing structured NutriPilot recipes remain the authoritative recipe layer.
- `data/recipe_import_template.csv` defines the import contract for future large
  recipe expansions.
- Recipes must reference canonical ingredient names (or approved aliases), and
  recipe nutrition is calculated deterministically from the ingredient catalogue.

## USDA releases used by the pipeline

The USDA download page currently lists:
- Foundation Foods — April 2026
- FNDDS 2021–2023 — October 2024
- Branded Foods — April 2026

USDA describes Foundation Foods as analytically derived data, FNDDS as foods and
beverages reported in What We Eat in America/NHANES, and Branded Foods as label
data from commercial food brands. USDA FoodData Central data are public domain
and published under CC0 1.0 Universal.

Because the bulk archives are large, they are downloaded locally and are not
committed to this repository.

## Pipeline

```text
USDA bulk archives / IFCT structured export
                |
                v
        source-specific importers
                |
                v
       canonical food records
                |
        +-------+-------+
        |               |
        v               v
   aliases          products
        |               |
        +-------+-------+
                |
                v
       data/foods.csv
                |
                v
       deterministic recipe
          nutrition engine
```

## Commands

### 1. Download USDA Foundation Foods

```bash
python scripts/download_usda_datasets.py --dataset foundation
```

### 2. Download FNDDS

```bash
python scripts/download_usda_datasets.py --dataset fndds
```

### 3. Download Branded Foods

```bash
python scripts/download_usda_datasets.py --dataset branded
```

Branded Foods is very large. Do not put the raw archive into GitHub.

Normalize it into the separate product table:

```bash
python scripts/ingest_usda_branded.py \
  --archive data/raw/FoodData_Central_branded_food_csv_2026-04-30.zip \
  --output data/products.csv
```

### 4. Normalize a USDA archive

Foundation example:

```bash
python scripts/ingest_usda_bulk.py \
  --archive data/raw/FoodData_Central_foundation_food_csv_2026-04-30.zip \
  --source-system "USDA FoodData Central Foundation" \
  --source-version "2026-04" \
  --output data/usda_foundation_foods.csv
```

### 5. Import approved IFCT data

```bash
python scripts/import_ifct_csv.py \
  --input path/to/approved_ifct_export.csv \
  --output data/ifct_foods.csv
```

The project deliberately does not scrape the IFCT PDF.

### 6. Build the canonical catalogue

```bash
python scripts/build_food_catalogue.py
```

The script merges the available sources and uses source precedence to choose a
single canonical record per normalized food name.

### 7. Validate before deployment

```bash
python scripts/validate_catalogue.py
```

## Source precedence

For canonical ingredient nutrition:

1. ICMR-NIN IFCT 2017 for an appropriate Indian match
2. USDA FoodData Central Foundation Foods
3. USDA FNDDS
4. NutriPilot prototype seed only when no governed source is available

Branded products are **not** automatically merged into ingredient foods.

## Recipe expansion

Use `data/recipe_import_template.csv` for governed structured recipes. Validate and merge them with:

```bash
python scripts/import_recipes.py --input path/to/recipes.csv --output data/recipes.csv
```

A recipe is accepted only when every referenced ingredient exists in the canonical food table. This keeps nutrition deterministic and prevents the refinement engine from selecting recipes that cannot be nutritionally verified.

## Entity resolution

`data/food_aliases.csv` maps common variants such as:

- chana → Chickpeas
- kabuli chana → Chickpeas
- chole → Chickpeas
- garbanzo beans → Chickpeas
- rajma → Kidney beans
- moong dal → Moong dal
- besan → Besan (chickpea flour)
- atta → Whole wheat flour
- dahi → Curd
- flattened rice → Poha

This layer can be expanded independently of the recipe catalogue.

## Important limitation

Phase 10 provides the **data architecture and ingestion pipeline** for broad
coverage; it does not falsely claim that the bundled app already contains every
USDA food, every Indian food, every commercial product, or thousands of recipes.
Those source datasets are intentionally fetched/imported rather than silently
fabricated or bundled as a giant repository file.
