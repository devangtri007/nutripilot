# Phase 10A

**V6 ingestion/validation patch:** canonicalizes negative carbohydrate-by-difference values to zero with provenance. — USDA Foundation + FNDDS

## Validation policy

Foundation Foods does not provide every nutrient for every food. USDA
documentation explicitly notes that some nutrients have not yet been analyzed
for particular foods. Therefore Phase 10A validation distinguishes:

- **Hard requirements:** schema, source identity, unique source IDs, non-empty
  records, and no negative nutrient values.
- **Core macros:** protein, carbohydrate, and fat coverage are reported and
  must be at least 80% for the imported table to pass.
- **Optional nutrients:** calories and fiber coverage are reported
  informationally and are not rejected solely because some values are absent.

### Energy handling

Current Foundation Foods use:

- nutrient 2047 — Metabolizable Energy (Atwater General Factor)
- nutrient 2048 — Metabolizable Energy (Atwater Specific Factor)

NutriPilot uses 2048 first, then 2047, then legacy 1008 where applicable.
If no USDA energy value is present but protein, fat, and carbohydrate are all
available, the ingestion script derives kcal as:

```text
kcal = 4 × protein_g + 9 × fat_g + 4 × carbohydrate_g
```

That derived value is explicitly marked in `data_basis`; it is not presented as
a directly published USDA energy value. USDA documents the 4/9/4 Atwater general
factors for Foundation Foods.

## Re-run after replacing the scripts

The USDA ZIP files already downloaded do not need to be downloaded again.

```bash
python scripts/ingest_usda_bulk.py \
  --archive data/raw/FoodData_Central_foundation_food_csv_2026-04-30.zip \
  --source-system "USDA FoodData Central Foundation" \
  --source-version 2026-04 \
  --output data/usda_foundation_foods.csv
```

```bash
python scripts/ingest_usda_bulk.py \
  --archive data/raw/FoodData_Central_survey_food_csv_2024-10-31.zip \
  --source-system "USDA FoodData Central FNDDS" \
  --source-version 2024-10 \
  --output data/usda_fndds_foods.csv
```

Then:

```bash
python scripts/validate_usda_phase10a.py
```

The validator should now report nutrient coverage without incorrectly failing
solely because Foundation Foods has incomplete optional nutrient coverage.


### V6 data-quality handling

Foundation Foods reports carbohydrate as **carbohydrate by difference**. Because
that calculation is based on measured proximate components, a small number of
records can have a negative computed carbohydrate value. USDA documentation
explains the by-difference calculation and its analytical basis.

NutriPilot's canonical nutrition layer cannot use a negative quantity of
carbohydrate. During ingestion, any negative `carbs_g` value is therefore
normalized to `0.0` and the `data_basis` field is annotated with
`negative carbohydrate-by-difference normalized to 0 g`. This is an explicit
application-level normalization, not a claim that USDA originally published
zero.

Calories derived with Atwater 4/9/4 use the normalized canonical carbohydrate
value. The raw USDA archive remains the source of record and is not modified.
