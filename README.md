# 🥗 NutriPilot

**AI-powered local nutrition copilot**

NutriPilot is a product-oriented meal-planning application designed to eventually recommend practical meals using:

- User nutrition goals
- Dietary preferences
- Allergies and foods to avoid
- Country, region and city
- Local and seasonal produce
- Current weather conditions
- Nutrition data

## Phase 2 — Nutrition & Local Food Data

Phase 2 introduces the first structured food layer.

### What was added

- `data/foods.csv` — starter food catalogue
- Category filtering
- Meal suitability filtering
- Nutrition snapshot for individual foods
- Nutrition fields for calories, protein, carbohydrates, fat and fiber
- Season and region metadata
- Diet metadata
- `st.cache_data` for efficient local dataset loading

The current starter catalogue contains **26 foods** spanning cereals, pulses, dairy, eggs, vegetables, fruits and nuts.

### Important data decision

This starter CSV is intended for **product development and prototyping**, not as a clinical nutrition database.

For a production-quality version, the next data step should use a properly sourced nutrition database. USDA FoodData Central provides REST access to food/nutrient data and downloadable datasets. See the official documentation:

- https://fdc.nal.usda.gov/api-guide/
- https://fdc.nal.usda.gov/download-datasets/

For India-specific research, the Indian Food Composition Tables (IFCT 2017) are published by the National Institute of Nutrition / ICMR and contain detailed Indian food-composition information. Before embedding that material into a distributed product, review the source's usage terms and permissions.

## Product architecture

```text
User Profile
     ↓
Location + Diet + Goal
     ↓
Food Catalogue
     ↓
Nutrition / Region / Season Filters
     ↓
Candidate Foods
```

AI is intentionally **not** generating recommendations yet.

The eventual architecture is:

```text
User Profile
     +
Location
     +
Season
     +
Weather
     ↓
Context Engine
     ↓
Local + Seasonal Food Data
     ↓
Nutrition Constraints
     ↓
AI Meal Planner
     ↓
Breakfast / Lunch / Dinner / Snacks
     ↓
Explanation + Iteration
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Tech Stack

- Python
- Streamlit
- Pandas
- CSV data layer

Planned:

- OpenAI API / LLMs
- Weather API
- Nutrition database
- Snowflake
- REST APIs

## Roadmap

### Phase 1 — Personalized Profile ✅
Collect location, diet, goals, restrictions and meal preferences.

### Phase 2 — Nutrition & Local Food Data ✅
Create the structured food catalogue and filtering layer.

### Phase 3 — Season & Weather Context
Infer season from location/date and integrate live weather.

### Phase 4 — AI Meal Recommendation
Use an LLM to select and explain meal recommendations from structured candidates.

### Phase 5 — Conversational Refinement
Support iterative requests such as:

> "Make dinner higher in protein."

> "I don't have paneer."

> "Give me a cheaper breakfast."

### Phase 6 — Evaluation & Product Analytics
Test constraint satisfaction, recommendation quality, hallucination resistance and personalization.

## Safety

NutriPilot is intended as a **meal discovery and planning prototype**, not medical diagnosis, treatment or individualized clinical dietary advice.

Nutrition values should be treated as estimates unless backed by a validated source and serving-specific calculation.
