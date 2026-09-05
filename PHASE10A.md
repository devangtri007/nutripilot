# NutriPilot Phase 10A — USDA Foundation + FNDDS

Phase 10A replaces the small prototype food universe with a governed USDA ingestion pipeline. It covers two official FoodData Central data types:

- **Foundation Foods — April 2026**: minimally processed foods and ingredients.
- **FNDDS 2021–2023 — October 2024**: prepared foods and survey foods.

USDA currently lists the Foundation CSV at about 3.7 MB compressed / 32 MB uncompressed and FNDDS at about 200 MB compressed / 1.6 GB uncompressed. Do not commit the raw archives to Git.

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Download the official archives

From the repository root:

```bash
python scripts/download_usda_datasets.py --dataset foundation --output-dir data/raw
python scripts/download_usda_datasets.py --dataset fndds --output-dir data/raw
```

Or download both:

```bash
python scripts/download_usda_datasets.py --dataset foundation --output-dir data/raw
python scripts/download_usda_datasets.py --dataset fndds --output-dir data/raw
```

The script uses the official USDA FoodData Central release URLs pinned in the source. Check the USDA download page before a future refresh.

## 3. Normalize each source

```bash
python scripts/ingest_usda_bulk.py \
  --archive data/raw/FoodData_Central_foundation_food_csv_2026-04-30.zip \
  --source-system "USDA FoodData Central Foundation" \
  --source-version 2026-04 \
  --output data/usda_foundation_foods.csv

python scripts/ingest_usda_bulk.py \
  --archive data/raw/FoodData_Central_survey_food_csv_2024-10-31.zip \
  --source-system "USDA FoodData Central FNDDS" \
  --source-version 2024-10 \
  --output data/usda_fndds_foods.csv
```

## 4. Validate the imported tables

```bash
python scripts/validate_usda_phase10a.py
```

The validator checks required columns, positive record counts, unique source IDs, numeric nutrition fields, and nutrient coverage.

## 5. Build the canonical NutriPilot food table

To create a staging catalogue without replacing the current app catalogue:

```bash
python scripts/build_food_catalogue.py \
  --prototype data/foods.csv \
  --usda-foundation data/usda_foundation_foods.csv \
  --usda-fndds data/usda_fndds_foods.csv \
  --output data/foods_phase10a.csv
```

Review the counts, then promote it when satisfied:

```bash
cp data/foods_phase10a.csv data/foods.csv
```

The build is deterministic. For normalized name collisions, the source precedence is:

1. ICMR-NIN IFCT 2017
2. USDA Foundation
3. USDA FNDDS
4. other governed sources
5. NutriPilot prototype seed

The raw USDA archives are **not** required by the Streamlit runtime. Only the normalized canonical CSV is used by the application.

## What Phase 10A does not do

- It does not yet ingest USDA Branded Foods into the recipe ingredient table.
- It does not yet scrape recipe websites.
- It does not claim the resulting catalogue contains every food worldwide.
- It does not generate nutrition values with the LLM.

Branded products are reserved for Phase 10C and will remain a separate product layer.

## Official USDA sources

- FoodData Central downloads: https://fdc.nal.usda.gov/download-datasets/
- FoodData Central API guide: https://fdc.nal.usda.gov/api-guide/
- FoodData Central data documentation: https://fdc.nal.usda.gov/data-documentation/
