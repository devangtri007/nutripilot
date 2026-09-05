# 🥗 NutriPilot

**AI-powered local nutrition copilot**

NutriPilot recommends practical meal ideas using user preferences, local context, seasonality and structured nutrition data.

## Phase 4 — AI Meal Recommendation

Phase 4 turns the previous data/context layers into an AI-assisted meal planner.

### User flow

```text
Country
   ↓
State / Region
   ↓
City
   ↓
Diet + Goal + Restrictions + Meals
   ↓
Open-Meteo location validation
   ↓
Live Weather + Season
   ↓
Food Candidate Filtering
   ↓
LLM Meal Planner
   ↓
Deterministic Nutrition Calculation
   ↓
Breakfast / Lunch / Dinner / Snacks
```

### What Phase 4 adds

- Cascading Country → Region → City selectors
- Open-Meteo validation of the selected location
- Live weather context
- Season context
- Candidate-food filtering based on diet, restrictions and season
- OpenAI-powered meal planning
- Structured JSON output from the model
- Deterministic nutrition calculations from the food catalogue
- Meal-specific explanations
- Multiple meal types
- No LLM-generated nutrition totals

## Location selector design

The dropdowns use a local `data/locations.csv` catalogue for the initial product scope.

The selected city is then **validated against Open-Meteo's geocoding API** before weather is requested.

This is intentional: Open-Meteo's geocoding endpoint is a search API rather than a complete country → admin1 → city directory. It accepts a location name and can be narrowed with country/admin1 qualifiers, and returns fields including `country`, `country_code`, `admin1`, latitude, longitude and timezone.

Official documentation:
https://open-meteo.com/en/docs/geocoding-api

The initial catalogue can be expanded later as the product adds supported markets.

## AI design

The LLM is not treated as the source of truth for nutrition.

The workflow is:

```text
Structured context
       ↓
Candidate food catalogue
       ↓
LLM chooses meals + quantities
       ↓
Validate every food against catalogue
       ↓
Calculate nutrition from database
       ↓
Display result
```

If the model returns a food that does not exist in the catalogue, the application rejects that meal instead of silently accepting invented nutrition information.

### Model

The prototype uses `gpt-4o-mini`.

The model receives:

- User location
- Season
- Current weather
- Diet
- Nutrition goal
- Foods to avoid
- Requested meals
- Candidate food catalogue

The model is instructed to return structured JSON.

## API configuration

Create `.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "your-api-key"
```

Do **not** commit this file to Git.

For Streamlit Community Cloud, add `OPENAI_API_KEY` through the app's Secrets settings instead.

OpenAI API documentation:
https://platform.openai.com/docs/api-reference

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Data layer

Current starter food catalogue:

- `data/foods.csv`

Current location catalogue:

- `data/locations.csv`

The food catalogue is still a prototype dataset. It should eventually be replaced/expanded using properly sourced nutrition data.

## Tech Stack

- Python
- Streamlit
- Pandas
- Requests
- OpenAI API / LLM
- Open-Meteo Geocoding API
- Open-Meteo Weather API
- CSV data layer

## Product architecture

```text
                  NUTRIPILOT
                      │
          ┌───────────┴───────────┐
          │                       │
     User Profile            Location
          │                       │
          │                 Open-Meteo
          │                       │
          └───────────┬───────────┘
                      ↓
                Context Engine
                      ↓
             Food Candidate Layer
                      ↓
                  AI Planner
                      ↓
              Structured Output
                      ↓
             Deterministic Checks
                      ↓
              Nutrition Calculation
                      ↓
            Personalized Meal Plan
```

## Roadmap

### Phase 1 — Personalized Profile ✅
Collect user location, diet, goals, restrictions and meals.

### Phase 2 — Nutrition & Local Food Data ✅
Create structured food and nutrition data.

### Phase 3 — Season & Weather Context ✅
Resolve location and obtain current weather.

### Phase 4 — AI Meal Recommendation ✅
Generate personalized breakfast, lunch, dinner and snack recommendations.

### Phase 5 — Conversational Refinement
Allow users to iteratively modify plans:

> "Make dinner higher in protein."

> "I don't have paneer."

> "Make breakfast cheaper."

> "Replace this with something local."

### Phase 6 — Evaluation & Product Analytics
Build a test suite for:

- Constraint satisfaction
- Diet compliance
- Food-catalogue grounding
- Nutritional calculation correctness
- Local/seasonal relevance
- Weather-context relevance
- Hallucination resistance
- Recommendation consistency

## Safety

NutriPilot is a meal-planning prototype and should not be treated as medical diagnosis, treatment or individualized clinical dietary advice.

Allergy information should be treated conservatively. The prototype's text matching is not a substitute for professional allergen verification or packaged-food label checks.
