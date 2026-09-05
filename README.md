# NutriPilot

> **Your local, seasonal nutrition copilot**

NutriPilot is a Streamlit-based AI-assisted meal-planning prototype. It
recommends meals based on **diet, goals, location, season, current
weather, and foods to avoid**.

## Table of Contents

-   [Features](#features)
-   [Architecture](#architecture)
-   [Tech Stack](#tech-stack)
-   [Project Structure](#project-structure)
-   [Setup](#setup)
-   [Usage](#usage)
-   [Configuration](#configuration)
-   [Data Layer](#data-layer)
-   [Limitations](#limitations)
-   [Roadmap](#roadmap)
-   [License & Credits](#license--credits)

## Features

-   Personalized recommendations using diet, goal, location, season, and
    weather.
-   Country → State/Region → City location selection.
-   Vegetarian, Vegan, Eggetarian, and Non-vegetarian diets.
-   Allergy / foods-to-avoid filtering.
-   **Just one meal** mode.
-   **Multi-day schedule** mode for 3, 5, or 7 days.
-   Optional calorie and protein targets.
-   Standard or tighter portion flexibility with deterministic
    serving-size optimization.
-   Live weather and local-context integration through Open-Meteo.
-   AI-assisted recipe selection using OpenAI `gpt-4o-mini`.
-   Recipe and meal-type validation before results are shown.
-   Deterministic nutrition calculation from the food catalogue.
-   Ingredient quantities and preparation information.
-   Conversational refinement of multi-day plans.
-   Aggregated shopping list with CSV download.
-   Food-data provenance metadata and USDA/IFCT ingestion utilities.
-   Light/Dark/System Streamlit theme support.

## Architecture

``` mermaid
flowchart TD
    A[Streamlit UI] --> B[User Profile]
    B --> C[Location + Weather]
    C --> D[Open-Meteo]
    B --> E[Recipe Candidate Filtering]
    C --> E
    E --> F[Recipe Catalogue]
    F --> G[OpenAI gpt-4o-mini]
    G --> H[Validation & Repair]
    H --> I[Nutrition Calculation]
    I --> J[Meal / Multi-Day Plan]
    J --> K[Portion Optimization]
    J --> L[Shopping List]
    J --> M[Plan Refinement]

    N[data/foods.csv] --> I
    O[data/recipes.csv] --> E
    P[data/locations.csv] --> C
```

### Data flow

1.  User enters profile and planning preferences.
2.  The selected city is resolved and current weather is fetched.
3.  Season and local context are derived.
4.  Recipes are filtered by meal type, diet, restrictions, region,
    season, and catalogue integrity.
5.  `gpt-4o-mini` selects recipes from the candidate catalogue.
6.  Deterministic validation prevents invalid recipe IDs, wrong meal
    types, and unsupported ingredients.
7.  Nutrition is calculated from `data/foods.csv`.
8.  Multi-day plans can be portion-optimized against selected targets.
9.  Users can refine an existing plan without unnecessarily changing
    unaffected meals.

The current workflow uses `st.session_state`; there is no external
application database or persistent user account system.

## Tech Stack

  Technology          Purpose
  ------------------- -----------------------------------------
  Python              Application and planning logic
  Streamlit           Interactive UI
  Pandas              CSV/data processing
  Requests            Open-Meteo API calls
  OpenAI Python SDK   AI integration
  `gpt-4o-mini`       Recipe selection and refinement
  Open-Meteo          Geocoding and weather
  CSV files           Food, recipe, location, and source data

The application does not use a SQL database.

## Project Structure

``` text
NutriPilot/
├── streamlit_app.py              # Main Streamlit application
├── requirements.txt              # Python dependencies
├── .streamlit/
│   ├── config.toml               # Theme configuration
│   └── secrets.toml              # Local API secrets (not committed)
├── data/
│   ├── foods.csv                 # Food nutrition + provenance
│   ├── recipes.csv               # Recipe catalogue
│   ├── locations.csv             # Location options
│   ├── source_registry.csv       # Food-source metadata
│   └── ifct_import_template.csv  # IFCT import template
├── scripts/
│   ├── ingest_usda.py            # USDA FoodData Central ingestion
│   └── import_ifct_csv.py        # Structured IFCT import
├── DATA_LAYER.md                 # Data architecture notes
└── UI_DESIGN.md                  # UI design system
```

## Setup

### Prerequisites

-   Python 3.10+ is recommended.
-   Internet access.
-   OpenAI API key for AI features.

Open-Meteo does not require an API key in the current application.

### Install

``` bash
git clone <YOUR_REPOSITORY_URL>
cd NutriPilot

python -m venv .venv
```

Activate the environment:

**macOS/Linux**

``` bash
source .venv/bin/activate
```

**Windows PowerShell**

``` powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

``` bash
pip install -r requirements.txt
```

### Configure OpenAI

Create `.streamlit/secrets.toml`:

``` toml
OPENAI_API_KEY = "your-openai-api-key"
```

Do not commit this file.

### Run

``` bash
streamlit run streamlit_app.py
```

## Usage

1.  Select your country, region, and city.
2.  Choose diet, goal, meals, and foods to avoid.
3.  Load local context to resolve location and weather.
4.  Choose either:
    -   **Just one meal** for a single recommendation.
    -   **Multi-day schedule** for a 3/5/7-day plan.
5.  Review nutrition, ingredients, and preparation details.
6.  For multi-day plans, optionally refine the plan conversationally or
    download the shopping list.

Example refinements:

``` text
Make Day 1 dinner higher protein
No rice in the plan
Keep every meal under 20 minutes
Replace Day 2 lunch with something quicker
```

## Configuration

  ------------------------------------------------------------------------
  Secret / Variable                         Required Purpose
  --------------------- ---------------------------- ---------------------
  `OPENAI_API_KEY`                        Yes for AI OpenAI API
                                                     authentication

  `USDA_FDC_API_KEY`         Only for USDA ingestion USDA FoodData Central
                                                     API authentication
  ------------------------------------------------------------------------

`OPENAI_API_KEY` is configured through Streamlit secrets.
`USDA_FDC_API_KEY` is used only by `scripts/ingest_usda.py`.

## Data Layer

The runtime food catalogue is CSV-based and includes nutrition plus
provenance fields.

Current bundled prototype data includes approximately:

-   83 food records
-   45 recipes
-   43 cities
-   8 countries

The bundled food values are **prototype seed data**, not clinical-grade
nutrition data.

The project also provides:

-   USDA FoodData Central ingestion for selected foods.
-   Structured IFCT 2017 import support.
-   Source IDs, versions, data basis, and license metadata.

The IFCT import utility intentionally does not scrape the IFCT
publication PDF.

## Limitations

-   Prototype recipe catalogue limits recommendation diversity.
-   Location coverage is limited to the bundled city catalogue.
-   No persistent accounts or cross-session plan history.
-   No external database.
-   AI features require an OpenAI API key.
-   Weather features require internet access.
-   Food restrictions are currently handled through text-based
    ingredient matching, not a full allergen ontology.
-   Seasonal filtering can fall back to a broader candidate pool when
    too few seasonal recipes are available.
-   Nutrition quality depends on the underlying food data.

**NutriPilot is a meal-planning prototype, not medical advice. Nutrition
targets are user-selected planning preferences, not medical or dietary
prescriptions.**

## Roadmap

Potential next steps include:

-   Expand and improve the recipe catalogue.
-   Add canonical food identity resolution across USDA and IFCT.
-   Introduce structured allergen metadata.
-   Add persistent user profiles and saved plans.
-   Move production food data to a governed database.
-   Improve budget, ingredient-reuse, batching, and meal-diversity
    optimization.
-   Add automated evaluation and monitoring for AI recommendations.

## License & Credits

### License

No explicit open-source license is currently declared.

**License: To be determined.**

### Credits

-   **Streamlit** --- application UI: https://streamlit.io/
-   **OpenAI** --- AI-assisted recipe selection/refinement:
    https://platform.openai.com/docs/
-   **Open-Meteo** --- geocoding and weather:
    https://open-meteo.com/en/docs
-   **USDA FoodData Central** --- food-composition data source:
    https://fdc.nal.usda.gov/
-   **ICMR-NIN IFCT 2017** --- Indian food-composition reference:
    https://www.nin.res.in/
