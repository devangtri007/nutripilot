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

## Phase 3 — Season & Weather Context

Phase 3 connects the user's location to external geographic and weather data.

### What was added

- City/region/country geocoding
- Latitude/longitude resolution
- Automatic season inference
- Live current weather
- Temperature
- Feels-like temperature
- Relative humidity
- Precipitation
- Wind speed
- Simple weather context such as Hot, Cold, Mild, Rainy or Thunderstorm
- Cached API responses to reduce repeated requests
- Graceful error handling when external services are unavailable

### APIs

NutriPilot uses Open-Meteo for this prototype:

1. **Geocoding API**
   - Converts a user-entered location into coordinates.
   - Returns location hierarchy and timezone.

2. **Weather Forecast API**
   - Uses those coordinates to retrieve current conditions.

Open-Meteo documents both APIs at:
- https://open-meteo.com/en/docs/geocoding-api
- https://open-meteo.com/en/docs

The Open-Meteo public service currently states that no authentication is required for non-commercial use and provides a CC BY 4.0 data licence. Review its current terms before deploying a commercial product.

## Season logic

Season is intentionally derived rather than entered manually.

For the prototype:

- India uses a simplified food-oriented model:
  - March–May → Summer
  - June–September → Monsoon
  - October–November → Post-monsoon
  - December–February → Winter

- Other locations use a hemisphere-based four-season model.

This is a product heuristic, not a scientific climate classification. Later versions can replace it with region-specific seasonality and agricultural/local-produce data.

## Current product flow

```text
Country + Region + City
          ↓
     Geocoding API
          ↓
    Coordinates + TZ
          ↓
      Weather API
          ↓
 Temperature / Rain / Humidity / Wind
          ↓
       Season Logic
          ↓
    Local Context Object
```

That context is now available in Streamlit session state and is ready for the Phase 4 recommendation engine.

## Planned AI architecture

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
Candidate Meals
     ↓
AI Meal Planner
     ↓
Breakfast / Lunch / Dinner / Snacks
     ↓
Explanation + Iteration
```

The LLM should **not** be responsible for inventing weather, season or nutrition facts. Those should come from deterministic/data-backed components.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Tech Stack

### Current
- Python
- Streamlit
- Pandas
- Requests
- Open-Meteo Geocoding API
- Open-Meteo Weather API
- CSV food data

### Planned
- OpenAI API / LLMs
- Validated nutrition database
- Local/seasonal produce data
- Snowflake
- Recommendation evaluation framework

## Roadmap

### Phase 1 — Personalized Profile ✅
Collect location, diet, goals, restrictions and meal preferences.

### Phase 2 — Nutrition & Local Food Data ✅
Create the structured food catalogue and filtering layer.

### Phase 3 — Season & Weather Context ✅
Resolve location, infer season and retrieve live weather.

### Phase 4 — AI Meal Recommendation
Generate personalized breakfast, lunch, dinner and snack recommendations using the structured context and food data.

### Phase 5 — Conversational Refinement
Support iterative requests such as:

> "Make dinner higher in protein."

> "I don't have paneer."

> "Give me a cheaper breakfast."

### Phase 6 — Evaluation & Product Analytics
Test constraint satisfaction, recommendation quality, hallucination resistance, local relevance and personalization.

## Safety

NutriPilot is intended as a **meal discovery and planning prototype**, not medical diagnosis, treatment or individualized clinical dietary advice.

Nutrition values should be treated as estimates unless backed by a validated source and serving-specific calculation.
