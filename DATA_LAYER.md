# NutriPilot Phase 9 — Production Data Layer

NutriPilot now has a governed food-composition layer with explicit provenance.

## Canonical record

`data/foods.csv` requires:

- food identity and meal metadata
- calories, protein, carbs, fat and fiber per 100 g
- source system
- source ID
- source version
- data basis
- license

The application continues to calculate recipe nutrition deterministically from
the food catalogue; the LLM does not generate nutrition values.

## USDA

Use `scripts/ingest_usda.py` for selected-food ingestion from USDA FoodData
Central. Keep the API key in an environment/secret, never in Git.

## IFCT 2017

Use `scripts/import_ifct_csv.py` only with an approved structured IFCT export.
The application does not scrape or reproduce the official IFCT PDF.

## Production merge policy

Recommended precedence:

1. Approved IFCT record for an Indian food when an appropriate match exists.
2. USDA Foundation/SR Legacy otherwise.
3. USDA Branded for packaged/branded products where appropriate.
4. Preserve source IDs and versions; never silently overwrite conflicting records.

## Current state

The bundled 83-food catalogue is still prototype seed data. It now carries
provenance metadata explicitly marking it as such. It must be replaced or
supplemented by governed USDA/IFCT ingestion before the product claims
production-grade nutrition accuracy.
