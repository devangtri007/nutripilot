# NutriPilot Data Sources

## Phase 10A — active ingestion targets

| Source | Release | Role | Status |
|---|---|---|---|
| USDA FoodData Central Foundation | April 2026 | Canonical minimally processed ingredients | Ready for bulk ingestion |
| USDA FoodData Central FNDDS | 2021–2023 / October 2024 | Prepared/survey foods | Ready for bulk ingestion |

USDA FoodData Central currently lists 394 Foundation Foods and 5,432 FNDDS foods in its searchable catalogue. The bulk download page lists the April 2026 Foundation release and FNDDS 2021–2023 release.

## Phase 10C — future product layer

| Source | Release | Role | Status |
|---|---|---|---|
| USDA FoodData Central Branded Foods | April 2026 download; API updates monthly | Packaged/branded products | Pipeline present, ingestion deferred to Phase 10C |

Branded Foods remain separate from recipe ingredients.

## Indian source

| Source | Release | Role | Status |
|---|---|---|---|
| ICMR-NIN IFCT | 2017 | Indian ingredient reference | Structured import pipeline present; Phase 10B |

## Provenance rule

Every governed food record must retain source system, source ID, source version, data basis, and license/terms. The LLM does not generate nutrition values.
