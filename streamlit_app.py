# NUTRIPILOT PHASE 8 FINAL — single-meal opt-out + multi-day planning
# Source invariant: exactly one schedule-length widget in this source file.

import json
import os
import re
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="NutriPilot", page_icon="🥗", layout="centered")

# FIXED UI: premium theme layer; product/data/AI logic below is unchanged.
st.markdown(
    """
<style>
/* ======================================================================
   NUTRIPILOT ZOMATO UI SYSTEM
   FIX A — Replace the previous Cream/Forest Green/Carrot palette.
   Light mode uses White / Light Grey / Near-black with Zomato Red as the
   single interactive accent. Dark mode swaps only the neutral surfaces.
   ====================================================================== */
:root {
    --np-accent: #E23744;
    --np-light-bg: #FFFFFF;
    --np-light-surface: #F5F5F5;
    --np-light-text: #1C1C1C;

    /* Theme-aware tokens: Streamlit remains the source of truth for mode. */
    --np-bg: var(--background-color, var(--np-light-bg));
    --np-surface: var(--secondary-background-color, var(--np-light-surface));
    --np-text: var(--text-color, var(--np-light-text));
    --np-border: var(--border-color, rgba(28, 28, 28, .14));
    --np-muted: color-mix(in srgb, var(--np-text) 66%, transparent);
    --np-border-soft: color-mix(in srgb, var(--np-text) 14%, transparent);
    --np-accent-soft: color-mix(in srgb, var(--np-accent) 10%, transparent);
}

/* FIX B — Theme-safe canvas and typography. */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
[data-testid="stMainBlockContainer"] {
    background: var(--np-bg) !important;
    color: var(--np-text) !important;
}
[data-testid="stHeader"] { background: var(--np-bg) !important; box-shadow: none !important; }
[data-testid="stToolbar"] { background: transparent !important; }
.main .block-container { max-width: 1120px; padding: 3.75rem 2rem 5rem; }

/* FIX C — Do NOT apply a custom font globally. A global font-family can
   override Streamlit's Material Symbols font and turn native icons into
   literal icon-name text. */
[data-testid="stAppViewContainer"] h1,
[data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3,
[data-testid="stAppViewContainer"] h4,
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] label,
[data-testid="stAppViewContainer"] li,
[data-testid="stAppViewContainer"] .stMarkdown,
[data-testid="stAppViewContainer"] .stCaption,
[data-testid="stCaptionContainer"],
[data-testid="stButton"] button,
[data-testid="stDownloadButton"] button,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stChatInput"] textarea {
    font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* FIX D — Explicitly preserve Streamlit Material Symbols glyphs.
   Native icon=":material/...:" remains the only button-icon mechanism. */
.material-symbols-rounded,
.material-symbols-outlined,
[class*="material-symbols"],
[data-testid="stButton"] button [class*="material"],
[data-testid="stDownloadButton"] button [class*="material"] {
    font-family: "Material Symbols Rounded", "Material Symbols Outlined" !important;
    font-weight: normal !important;
    font-style: normal !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-feature-settings: "liga" !important;
    font-feature-settings: "liga" !important;
    -webkit-font-smoothing: antialiased !important;
}

[data-testid="stAppViewContainer"] h1,
[data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3,
[data-testid="stAppViewContainer"] h4 {
    color: var(--np-text) !important;
    font-weight: 750 !important;
    letter-spacing: -0.035em;
}
[data-testid="stAppViewContainer"] h1 { font-size: clamp(2.45rem, 5vw, 4rem) !important; line-height: 1.02 !important; }
[data-testid="stAppViewContainer"] h2 { font-size: clamp(1.7rem, 3vw, 2.35rem) !important; line-height: 1.08 !important; }
[data-testid="stAppViewContainer"] h3 { font-size: 1.35rem !important; line-height: 1.15 !important; }
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] label,
[data-testid="stAppViewContainer"] li,
[data-testid="stAppViewContainer"] .stMarkdown,
[data-testid="stAppViewContainer"] .stCaption,
[data-testid="stCaptionContainer"] { color: var(--np-muted) !important; }
[data-testid="stAppViewContainer"] strong { color: var(--np-text) !important; }
hr { border: 0 !important; border-top: 1px solid var(--np-border-soft) !important; margin: 2.1rem 0 !important; }

/* FIX E — Neutral cards/containers. */
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stExpander"],
[data-testid="stChatMessage"] {
    border: 1px solid var(--np-border-soft) !important;
    border-radius: 16px !important;
    background: var(--np-surface) !important;
    box-shadow: none !important;
}
[data-testid="stExpander"] summary { color: var(--np-text) !important; font-weight: 700 !important; }

/* FIX F — Inputs use theme-aware surfaces; red is the only focus state. */
[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
[data-baseweb="textarea"] > div,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
textarea {
    background: var(--np-surface) !important;
    color: var(--np-text) !important;
    border: 1px solid var(--np-border-soft) !important;
    border-radius: 11px !important;
    box-shadow: none !important;
}
[data-baseweb="select"] > div:focus-within,
[data-baseweb="input"] > div:focus-within,
[data-baseweb="textarea"] > div:focus-within,
input:focus, textarea:focus {
    border-color: var(--np-accent) !important;
    box-shadow: 0 0 0 1px var(--np-accent) !important;
}
[data-baseweb="select"] span,
[data-baseweb="select"] input,
[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea { color: var(--np-text) !important; }
[data-baseweb="select"] svg { fill: var(--np-text) !important; }
[data-baseweb="popover"], [data-baseweb="menu"] {
    background: var(--np-surface) !important;
    border: 1px solid var(--np-border-soft) !important;
    border-radius: 12px !important;
    box-shadow: none !important;
}
[role="option"] { background: var(--np-surface) !important; color: var(--np-text) !important; }
[role="option"]:hover, [role="option"][aria-selected="true"] { background: var(--np-accent-soft) !important; color: var(--np-text) !important; }

/* FIX G — Selected controls use ONLY Zomato Red. */
[data-testid="stMultiSelect"] [data-baseweb="tag"] { background: var(--np-accent) !important; border: 1px solid var(--np-accent) !important; color: #FFFFFF !important; border-radius: 999px !important; }
[data-testid="stMultiSelect"] [data-baseweb="tag"] span,
[data-testid="stMultiSelect"] [data-baseweb="tag"] svg { color: #FFFFFF !important; fill: #FFFFFF !important; }
[data-testid="stRadio"] label,
[data-testid="stCheckbox"] label,
[data-testid="stMultiSelect"] label { color: var(--np-text) !important; }
[data-testid="stRadio"] [role="radio"] > div:first-child { border-color: var(--np-border-soft) !important; background: transparent !important; }
[data-testid="stRadio"] [role="radio"][aria-checked="true"] > div:first-child { border-color: var(--np-accent) !important; background: var(--np-accent) !important; }
[data-testid="stRadio"] [role="radio"][aria-checked="true"] > div:first-child > div { background: #FFFFFF !important; }
[data-testid="stSlider"] [role="slider"] { background: var(--np-accent) !important; border-color: var(--np-accent) !important; }

/* FIX H — Buttons always have guaranteed high contrast. */
div.stButton > button,
div.stDownloadButton > button,
[data-testid="stFormSubmitButton"] button {
    min-height: 2.7rem;
    border-radius: 11px !important;
    border: 1px solid var(--np-accent) !important;
    background: var(--np-accent) !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    box-shadow: none !important;
}
div.stButton > button:hover,
div.stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] button:hover { background: var(--np-accent) !important; color: #FFFFFF !important; border-color: var(--np-accent) !important; transform: translateY(-1px); }
div.stButton > button:focus-visible,
div.stDownloadButton > button:focus-visible,
[data-testid="stFormSubmitButton"] button:focus-visible { outline: 2px solid var(--np-accent) !important; outline-offset: 2px !important; box-shadow: none !important; }
div.stButton > button:disabled,
div.stDownloadButton > button:disabled,
[data-testid="stFormSubmitButton"] button:disabled { opacity: .5 !important; background: var(--np-surface) !important; color: var(--np-muted) !important; border-color: var(--np-border-soft) !important; }

/* FIX I — Native icon glyphs inherit the button foreground, not the text font. */
div.stButton > button [class*="material"],
div.stDownloadButton > button [class*="material"],
[data-testid="stFormSubmitButton"] button [class*="material"] { color: currentColor !important; fill: currentColor !important; }

/* FIX J — Metric cards. */
[data-testid="stMetric"] { background: var(--np-surface) !important; border: 1px solid var(--np-border-soft) !important; border-radius: 15px !important; padding: 1rem 1.1rem !important; }
[data-testid="stMetricLabel"] { color: var(--np-muted) !important; font-size: .72rem !important; font-weight: 700 !important; text-transform: uppercase; letter-spacing: .09em; }
[data-testid="stMetricValue"] { color: var(--np-text) !important; font-weight: 800 !important; letter-spacing: -.035em; }
[data-testid="stMetricDelta"] { color: var(--np-accent) !important; }

/* FIX K — Info/success/error/warning share one neutral branded treatment. */
[data-testid="stAlert"] { background: var(--np-surface) !important; border: 1px solid var(--np-border-soft) !important; border-left: 3px solid var(--np-accent) !important; border-radius: 13px !important; color: var(--np-text) !important; box-shadow: none !important; }
[data-testid="stAlert"] * { color: var(--np-text) !important; }
[data-testid="stAlert"] svg { color: var(--np-accent) !important; fill: var(--np-accent) !important; }

/* FIX L — Active tabs/links use only the red accent. */
[data-baseweb="tab-list"] { gap: .35rem; border-bottom: 1px solid var(--np-border-soft) !important; }
[data-baseweb="tab"] { color: var(--np-muted) !important; background: transparent !important; }
[data-baseweb="tab"][aria-selected="true"] { color: var(--np-accent) !important; border-bottom: 2px solid var(--np-accent) !important; }
a { color: var(--np-accent) !important; }

/* FIX M — Chat/dataframes remain theme-aware. */
[data-testid="stChatInput"] { background: var(--np-surface) !important; border: 1px solid var(--np-border-soft) !important; border-radius: 14px !important; }
[data-testid="stChatInput"] textarea { background: transparent !important; border: 0 !important; box-shadow: none !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--np-border-soft) !important; border-radius: 12px !important; overflow: hidden !important; background: var(--np-surface) !important; }
[data-testid="stDataFrame"] { --dataframe-border-color: var(--np-border-soft) !important; --dataframe-header-background-color: var(--np-surface) !important; }

/* FIX N — Sidebar follows the active Streamlit theme. */
section[data-testid="stSidebar"] { background: var(--np-bg) !important; border-right: 1px solid var(--np-border-soft) !important; }
section[data-testid="stSidebar"] * { color: var(--np-text) !important; }
section[data-testid="stSidebar"] [data-baseweb="select"] > div,
section[data-testid="stSidebar"] [data-baseweb="input"] > div { background: var(--np-surface) !important; border-color: var(--np-border-soft) !important; }

@media (max-width: 760px) { .main .block-container { padding: 2.25rem 1rem 3rem; } [data-testid="stAppViewContainer"] h1 { font-size: 2.5rem !important; } [data-testid="stMetric"] { padding: .8rem !important; } }
</style>
    """,
    unsafe_allow_html=True,
)


FOOD_DATA_PATH = "data/foods.csv"
RECIPE_DATA_PATH = "data/recipes.csv"
LOCATION_DATA_PATH = "data/locations.csv"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# Phase 9 — governed food-composition data layer
FOOD_SOURCE_REGISTRY_PATH = "data/source_registry.csv"
FOOD_SOURCE_REQUIRED_COLUMNS = {
    "food", "category", "calories_kcal", "protein_g", "carbs_g",
    "fat_g", "fiber_g", "meal_types", "season", "regions", "diet",
    "source_system", "source_id", "source_version", "data_basis", "license",
}


def _data_file_version(path):
    """Return a cache key that changes whenever a CSV is replaced/updated."""
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return None


@st.cache_data
def load_food_data(file_version=None):
    foods = pd.read_csv(FOOD_DATA_PATH)
    missing = FOOD_SOURCE_REQUIRED_COLUMNS.difference(foods.columns)
    if missing:
        raise ValueError(
            "Food catalogue is missing Phase 9 provenance columns: "
            + ", ".join(sorted(missing))
        )
    return foods


@st.cache_data
def load_recipe_data(file_version=None):
    return pd.read_csv(RECIPE_DATA_PATH)


@st.cache_data
def load_location_data(file_version=None):
    return pd.read_csv(LOCATION_DATA_PATH)


@st.cache_data
def load_source_registry():
    return pd.read_csv(FOOD_SOURCE_REGISTRY_PATH)


def food_source_summary(foods):
    columns = ["source_system", "source_version", "data_basis", "license"]
    return (
        foods[columns]
        .fillna("")
        .drop_duplicates()
        .sort_values(columns)
        .reset_index(drop=True)
    )


@st.cache_data(ttl=1800)
def validate_location(country, region, city):
    response = requests.get(
        GEOCODING_URL,
        params={
            "name": f"{city}, {region}, {country}",
            "count": 10,
            "language": "en",
            "format": "json",
        },
        timeout=10,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        return None

    city_lower = city.lower()
    region_lower = region.lower()
    matching = [
        result for result in results
        if result.get("name", "").lower() == city_lower
        and result.get("admin1", "").lower() == region_lower
    ]
    return (matching or results)[0]


@st.cache_data(ttl=900)
def get_current_weather(latitude, longitude, timezone_name):
    response = requests.get(
        WEATHER_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,"
                "apparent_temperature,precipitation,"
                "rain,weather_code,wind_speed_10m"
            ),
            "timezone": timezone_name or "auto",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_season(month, latitude, country):
    if country.lower() == "india":
        if month in {3, 4, 5}:
            return "Summer"
        if month in {6, 7, 8, 9}:
            return "Monsoon"
        if month in {10, 11}:
            return "Post-monsoon"
        return "Winter"

    if latitude >= 0:
        return {
            12: "Winter", 1: "Winter", 2: "Winter",
            3: "Spring", 4: "Spring", 5: "Spring",
            6: "Summer", 7: "Summer", 8: "Summer",
            9: "Autumn", 10: "Autumn", 11: "Autumn",
        }[month]

    return {
        12: "Summer", 1: "Summer", 2: "Summer",
        3: "Autumn", 4: "Autumn", 5: "Autumn",
        6: "Winter", 7: "Winter", 8: "Winter",
        9: "Spring", 10: "Spring", 11: "Spring",
    }[month]


def weather_label(code, temperature, precipitation):
    if code in {95, 96, 99}:
        return "Thunderstorm"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "Rainy"
    if code in {71, 73, 75, 77, 85, 86}:
        return "Snowy"
    if code in {45, 48}:
        return "Foggy"
    if precipitation and precipitation > 0:
        return "Wet"
    if temperature >= 32:
        return "Hot"
    if temperature <= 12:
        return "Cold"
    return "Mild"


def diet_allows(diet_value, diet):
    value = str(diet_value).lower()
    diet = diet.lower()
    if diet == "vegan":
        return value == "vegan"
    if diet == "vegetarian":
        return value in {"vegan", "vegetarian"}
    if diet == "eggetarian":
        return value in {"vegan", "vegetarian", "eggetarian"}
    return True


def parse_ingredients(text):
    items = []
    for token in str(text).split(";"):
        food, grams = token.rsplit(":", 1)
        items.append({"food": food.strip(), "grams": float(grams)})
    return items


def recipe_matches_region(recipe_regions, country, region):
    value = str(recipe_regions).lower()
    country = country.lower()
    region = region.lower()

    if "global" in value:
        return True
    if country == "india" and "india" in value:
        return True
    if region and region in value:
        return True
    return False


def build_recipe_candidates(recipes, foods, profile, context):
    season = context["season"]
    condition = context["weather"]["condition"].lower()
    country = profile["country"]
    region = profile["region"]

    food_lookup = foods.set_index("food")
    restrictions = [
        item.strip().lower()
        for item in profile["restrictions"].split(",")
        if item.strip()
    ]

    rows = []
    for _, recipe in recipes.iterrows():
        if recipe["meal_type"] not in profile["meals"]:
            continue
        if not diet_allows(recipe["diet"], profile["diet"]):
            continue
        if not recipe_matches_region(recipe["regions"], country, region):
            continue

        season_value = str(recipe["season"]).lower()
        seasonal = season_value == "all" or season.lower() in season_value
        if not seasonal:
            # Keep a fallback pool rather than making the catalogue too narrow.
            continue

        ingredients = parse_ingredients(recipe["ingredients"])
        ingredient_names = [x["food"].lower() for x in ingredients]

        if any(
            any(restriction in ingredient for ingredient in ingredient_names)
            for restriction in restrictions
        ):
            continue

        missing = [x["food"] for x in ingredients if x["food"] not in food_lookup.index]
        if missing:
            continue

        rows.append(recipe.to_dict())

    # If seasonal filtering leaves too few recipes, use non-seasonal recipes.
    if len(rows) < max(6, len(profile["meals"]) * 2):
        rows = []
        for _, recipe in recipes.iterrows():
            if recipe["meal_type"] not in profile["meals"]:
                continue
            if not diet_allows(recipe["diet"], profile["diet"]):
                continue
            if not recipe_matches_region(recipe["regions"], country, region):
                continue
            ingredients = parse_ingredients(recipe["ingredients"])
            ingredient_names = [x["food"].lower() for x in ingredients]
            if any(
                any(restriction in ingredient for ingredient in ingredient_names)
                for restriction in restrictions
            ):
                continue
            rows.append(recipe.to_dict())

    return pd.DataFrame(rows)


def validate_catalogue_integrity(foods, recipes):
    """Fail early if recipes reference foods missing from the deployed catalogue."""
    food_names = set(foods["food"].astype(str).str.strip())
    missing = {}

    for _, recipe in recipes.iterrows():
        for item in parse_ingredients(recipe["ingredients"]):
            food = item["food"]
            if food not in food_names:
                missing.setdefault(recipe["recipe_id"], []).append(food)

    return missing


def calculate_recipe_nutrition(recipe, foods):
    lookup = foods.set_index("food")
    totals = {
        "calories_kcal": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
    }

    ingredients = parse_ingredients(recipe["ingredients"])
    verified = []

    for item in ingredients:
        food = item["food"]
        grams = float(item["grams"])

        if food not in lookup.index:
            raise ValueError(
                f"Recipe '{recipe.get('name', recipe.get('recipe_id', 'unknown'))}' "
                f"contains '{food}', but that ingredient is missing from "
                f"data/foods.csv. Make sure both data/foods.csv and data/recipes.csv "
                f"come from the same NutriPilot Phase 4 package."
            )

        row = lookup.loc[food]
        factor = grams / 100
        for field in totals:
            totals[field] += float(row[field]) * factor

        verified.append({"food": food, "grams": grams})

    result = recipe.copy()
    result["parsed_ingredients"] = verified
    result["nutrition"] = {key: round(value, 1) for key, value in totals.items()}
    return result





def recipe_record_for_prompt(recipe):
    return {
        "recipe_id": recipe["recipe_id"],
        "name": recipe["name"],
        "meal_type": recipe["meal_type"],
        "cuisine": recipe["cuisine"],
        "regions": recipe["regions"],
        "season": recipe["season"],
        "diet": recipe["diet"],
        "goal_tags": recipe["goal_tags"],
        "weather_tags": recipe["weather_tags"],
        "ingredients": recipe["ingredients"],
        "prep_time_min": int(recipe["prep_time_min"]),
        "cook_time_min": int(recipe["cook_time_min"]),
        "total_time_min": int(recipe["total_time_min"]),
        "difficulty": recipe["difficulty"],
    }


def call_json_model(system_prompt, user_payload):
    if "OPENAI_API_KEY" not in st.secrets:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to Streamlit secrets.")

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
    )
    return json.loads(response.choices[0].message.content)


def nutrition_totals(meals):
    totals = {
        "calories_kcal": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
    }
    for meal in meals:
        for key in totals:
            totals[key] += float(meal["nutrition"][key])
    return {key: round(value, 1) for key, value in totals.items()}


def plan_days(plan):
    return sorted(
        plan,
        key=lambda day: int(str(day.get("day", 1)).replace("Day ", "")),
    )


def all_plan_meals(plan):
    meals = []
    for day in plan_days(plan):
        meals.extend(day.get("meals", []))
    return meals


def calculate_scaled_recipe_nutrition(recipe, foods, serving_multiplier=1.0):
    """Phase 7: scale a complete validated recipe and calculate nutrition."""
    multiplier = float(serving_multiplier)
    if multiplier <= 0:
        raise ValueError("Serving multiplier must be positive.")

    lookup = foods.set_index("food")
    totals = {
        "calories_kcal": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
    }
    verified = []

    for item in parse_ingredients(recipe["ingredients"]):
        food = item["food"]
        grams = float(item["grams"]) * multiplier

        if food not in lookup.index:
            raise ValueError(
                f"Recipe '{recipe.get('name', recipe.get('recipe_id', 'unknown'))}' "
                f"contains '{food}', but that ingredient is missing from data/foods.csv."
            )

        row = lookup.loc[food]
        factor = grams / 100
        for field in totals:
            totals[field] += float(row[field]) * factor

        verified.append({"food": food, "grams": round(grams, 1)})

    result = recipe.copy()
    result["parsed_ingredients"] = verified
    result["serving_multiplier"] = round(multiplier, 2)
    result["nutrition"] = {key: round(value, 1) for key, value in totals.items()}
    return result


def portion_objective(nutrition, calorie_target, protein_target, multiplier):
    score = 0.0

    if calorie_target:
        score += (
            abs(nutrition["calories_kcal"] - float(calorie_target))
            / max(float(calorie_target), 1.0)
        ) ** 2

    if protein_target:
        score += (
            abs(nutrition["protein_g"] - float(protein_target))
            / max(float(protein_target), 1.0)
        ) ** 2

    # Keep the solution near the standard recipe serving unless adjustment helps.
    score += 0.10 * (float(multiplier) - 1.0) ** 2
    return score


def optimize_day_portions(
    day,
    foods,
    calorie_target,
    protein_target,
    max_adjustment=0.25,
):
    """Phase 7: deterministic, bounded portion optimization."""
    if not calorie_target and not protein_target:
        meals = []
        for meal in day["meals"]:
            candidate = meal.copy()
            candidate["serving_multiplier"] = 1.0
            meals.append(candidate)
        return {
            "day": day["day"],
            "meals": meals,
            "totals": nutrition_totals(meals),
        }

    lower = max(0.50, 1.0 - float(max_adjustment))
    upper = 1.0 + float(max_adjustment)
    grid = [
        round(lower + i * 0.05, 2)
        for i in range(int(round((upper - lower) / 0.05)) + 1)
    ]

    meals = []
    for meal in day["meals"]:
        best = None
        best_score = float("inf")
        for multiplier in grid:
            candidate = calculate_scaled_recipe_nutrition(
                meal, foods, multiplier
            )
            score = portion_objective(
                candidate["nutrition"],
                calorie_target,
                protein_target,
                multiplier,
            )
            if score < best_score:
                best_score = score
                best = candidate
        meals.append(best)

    # A few coordinate-descent passes optimize each meal in the context of the day.
    for _ in range(3):
        changed = False
        for meal_index, meal in enumerate(meals):
            other = meals[:meal_index] + meals[meal_index + 1:]
            other_totals = nutrition_totals(other)
            best = meal
            best_score = float("inf")

            for multiplier in grid:
                candidate = calculate_scaled_recipe_nutrition(
                    meal, foods, multiplier
                )
                combined = dict(other_totals)
                for key in combined:
                    combined[key] += candidate["nutrition"][key]

                score = portion_objective(
                    combined,
                    calorie_target,
                    protein_target,
                    multiplier,
                )
                if score < best_score:
                    best_score = score
                    best = candidate

            if best["serving_multiplier"] != meal["serving_multiplier"]:
                changed = True
            meals[meal_index] = best

        if not changed:
            break

    return {
        "day": day["day"],
        "meals": meals,
        "totals": nutrition_totals(meals),
    }


def optimize_plan_portions(
    plan,
    foods,
    calorie_target,
    protein_target,
    max_adjustment=0.25,
):
    return [
        optimize_day_portions(
            day,
            foods,
            calorie_target,
            protein_target,
            max_adjustment,
        )
        for day in plan_days(plan)
    ]


def validate_plan_response(raw_plan, profile, recipes, foods):
    lookup = recipes.set_index("recipe_id")
    if not isinstance(raw_plan.get("days"), list):
        raise ValueError("AI did not return a valid multi-day plan.")

    verified_days = []

    for day_index, day in enumerate(raw_plan["days"], start=1):
        verified_meals = []
        seen_meals = set()

        for item in day.get("meals", []):
            meal_type = item.get("meal")
            recipe_id = item.get("recipe_id")

            if meal_type not in profile["meals"]:
                raise ValueError(f"AI returned an unrequested meal: {meal_type}")
            if meal_type in seen_meals:
                raise ValueError(
                    f"Duplicate meal type on Day {day_index}: {meal_type}"
                )
            if recipe_id not in lookup.index:
                raise ValueError(f"AI returned unsupported recipe_id: {recipe_id}")

            recipe = lookup.loc[recipe_id].to_dict()
            if recipe["meal_type"] != meal_type:
                raise ValueError(
                    f"Recipe {recipe_id} is {recipe['meal_type']}, not {meal_type}."
                )

            verified = calculate_recipe_nutrition(recipe, foods)
            verified["why"] = item.get("why", "")
            verified["tags"] = item.get("tags", [])
            verified["serving_multiplier"] = 1.0
            verified_meals.append(verified)
            seen_meals.add(meal_type)

        if set(profile["meals"]) != seen_meals:
            missing = [m for m in profile["meals"] if m not in seen_meals]
            raise ValueError(
                f"Day {day_index} is missing meals: {', '.join(missing)}"
            )

        verified_days.append({
            "day": day_index,
            "meals": verified_meals,
            "totals": nutrition_totals(verified_meals),
        })

    return verified_days


def generate_single_meal(
    profile,
    location_context,
    recipe_candidates,
    foods,
    recipes,
    meal_type,
):
    """Select exactly one validated catalogue recipe for on-demand mode."""
    candidates = recipe_candidates[
        recipe_candidates["meal_type"].eq(meal_type)
    ].copy()

    if candidates.empty:
        raise ValueError(
            f"No validated catalogue recipes are available for {meal_type} "
            "under the selected diet, restrictions and local context."
        )

    candidate_records = [
        recipe_record_for_prompt(row)
        for row in candidates.to_dict(orient="records")
    ]

    system_prompt = """
You are NutriPilot's on-demand meal recommendation engine.

The recipe catalogue is the source of truth.

Choose exactly ONE recipe_id from candidate_recipes.

Rules:
1. Never invent recipes, ingredients, quantities, nutrition values, or cooking steps.
2. Select only a recipe_id present in candidate_recipes.
3. The recipe must match the requested meal type.
4. Respect the user's diet and foods to avoid.
5. Prefer seasonal, location-relevant and weather-compatible recipes.
6. Use the user's goal only as a ranking signal, not as medical advice.
7. Return valid JSON only.

Output:
{
  "recipe_id": "R001",
  "why": "Short practical reason.",
  "tags": ["seasonal", "goal-fit"]
}
"""
    raw = call_json_model(
        system_prompt,
        {
            "user_profile": profile,
            "location_context": location_context,
            "requested_meal": meal_type,
            "candidate_recipes": candidate_records,
        },
    )

    if not isinstance(raw, dict):
        raise ValueError("AI did not return a valid single-meal response.")

    recipe_id = raw.get("recipe_id")
    lookup = recipes.set_index("recipe_id")

    if recipe_id not in lookup.index:
        raise ValueError(f"AI returned unsupported recipe_id: {recipe_id}")

    recipe = lookup.loc[recipe_id].to_dict()
    if recipe["meal_type"] != meal_type:
        raise ValueError(
            f"Recipe {recipe_id} is {recipe['meal_type']}, not {meal_type}."
        )

    verified = calculate_recipe_nutrition(recipe, foods)
    verified["why"] = str(raw.get("why", ""))
    verified["tags"] = raw.get("tags", [])
    verified["serving_multiplier"] = 1.0
    return verified


def generate_multi_day_plan(
    profile,
    location_context,
    recipe_candidates,
    foods,
    recipes,
    plan_days_count,
    calorie_target,
    protein_target,
):
    candidate_records = [
        recipe_record_for_prompt(row)
        for row in recipe_candidates.to_dict(orient="records")
    ]

    system_prompt = """
You are NutriPilot, a multi-day meal-planning copilot.

The recipe catalogue is the source of truth.

Create a multi-day plan using ONLY recipe_id values from candidate_recipes.

Rules:
1. Never invent recipes, ingredients, quantities, nutrition values, or cooking steps.
2. Respect the user's diet and foods to avoid.
3. Include exactly one recipe for every requested meal type on every day.
4. Avoid repeating the same recipe across days unless variety is impossible.
5. Prefer seasonal, location-relevant and weather-compatible recipes.
6. Use the user's goal and explicitly supplied nutrition targets as ranking signals.
7. Nutrition targets are user-selected planning preferences, not medical prescriptions.
8. Return valid JSON only.

Output:
{
  "days": [
    {
      "day": 1,
      "meals": [
        {
          "meal": "Breakfast",
          "recipe_id": "R001",
          "why": "Short reason.",
          "tags": ["seasonal", "goal-fit"]
        }
      ]
    }
  ]
}
"""
    raw = call_json_model(
        system_prompt,
        {
            "user_profile": profile,
            "location_context": location_context,
            "plan_days": plan_days_count,
            "daily_calorie_target_kcal": calorie_target,
            "daily_protein_target_g": protein_target,
            "candidate_recipes": candidate_records,
        },
    )

    # The model is a selector, not the source of truth.  It can occasionally
    # pair a valid recipe_id with the wrong meal label (for example, return a
    # Dinner recipe under Breakfast).  Repair that deterministic mismatch
    # before validation instead of making the entire plan fail.
    if isinstance(raw, dict) and isinstance(raw.get("days"), list):
        candidate_by_meal = {}
        for row in recipe_candidates.to_dict(orient="records"):
            candidate_by_meal.setdefault(row["meal_type"], []).append(row)

        used_ids = set()
        repaired_days = []
        for day_index, day in enumerate(raw["days"], start=1):
            incoming = day.get("meals", []) if isinstance(day, dict) else []
            incoming_by_meal = {}
            for item in incoming:
                if not isinstance(item, dict):
                    continue
                meal_label = item.get("meal")
                if meal_label in profile["meals"] and meal_label not in incoming_by_meal:
                    incoming_by_meal[meal_label] = item

            repaired_meals = []
            for meal_type in profile["meals"]:
                item = incoming_by_meal.get(meal_type)
                recipe_id = item.get("recipe_id") if item else None
                lookup = recipes.set_index("recipe_id")
                valid_for_meal = (
                    recipe_id in lookup.index
                    and str(lookup.loc[recipe_id, "meal_type"]) == meal_type
                )

                if not valid_for_meal or recipe_id in used_ids:
                    pool = [
                        row for row in candidate_by_meal.get(meal_type, [])
                        if row["recipe_id"] not in used_ids
                    ]
                    if not pool:
                        # Repetition is preferable to emitting an invalid
                        # recipe/meal pairing when the catalogue is exhausted.
                        pool = candidate_by_meal.get(meal_type, [])
                    if not pool:
                        raise ValueError(
                            f"No validated catalogue recipe is available for {meal_type}."
                        )
                    replacement = pool[0]
                    recipe_id = replacement["recipe_id"]

                repaired_meals.append({
                    "meal": meal_type,
                    "recipe_id": recipe_id,
                    "why": item.get("why", "") if item else "",
                    "tags": item.get("tags", []) if item else [],
                })
                used_ids.add(recipe_id)

            repaired_days.append({"day": day_index, "meals": repaired_meals})

        raw["days"] = repaired_days

    return validate_plan_response(raw, profile, recipes, foods)


def build_shopping_list(plan):
    shopping = {}
    for meal in all_plan_meals(plan):
        for item in meal["parsed_ingredients"]:
            shopping[item["food"]] = (
                shopping.get(item["food"], 0) + float(item["grams"])
            )

    return pd.DataFrame([
        {"Ingredient": name, "Total quantity (g)": round(grams)}
        for name, grams in sorted(shopping.items())
    ])



def _normalize_recipe_text(value):
    """Normalize recipe names so session-state/display variants still resolve."""
    text = str(value or "").strip().casefold()
    # Treat common display variations as equivalent.
    text = text.replace("&", " and ")
    text = re.sub(r"[’‘`´]", "'", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _resolve_recipe_id(meal, recipes):
    """Resolve a recipe from current catalogue by ID first, then exact normalized name.

    This intentionally does not depend on the shape of an older session-state
    object. Values such as pandas NaN are treated as missing.
    """
    if recipes is None or recipes.empty or "recipe_id" not in recipes.columns:
        return None

    lookup = recipes.set_index("recipe_id", drop=False)

    def clean(value):
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass
        return str(value).strip()

    raw_id = clean(meal.get("recipe_id"))
    if raw_id and raw_id in lookup.index:
        return raw_id

    names = [
        clean(meal.get("name")),
        clean(meal.get("recipe_name")),
    ]
    nested = meal.get("recipe")
    if isinstance(nested, dict):
        names.append(clean(nested.get("name")))

    name_to_ids = {}
    for _, row in recipes.iterrows():
        recipe_id = clean(row.get("recipe_id"))
        recipe_name = _normalize_recipe_text(row.get("name"))
        if recipe_id and recipe_name:
            name_to_ids.setdefault(recipe_name, []).append(recipe_id)

    # Exact normalized name match is deterministic and handles punctuation,
    # ampersands, apostrophes and whitespace differences.
    for name in names:
        key = _normalize_recipe_text(name)
        matches = name_to_ids.get(key, [])
        if len(matches) == 1:
            return matches[0]

    # Safe last resort: only accept containment when it identifies one recipe.
    for name in names:
        key = _normalize_recipe_text(name)
        if not key:
            continue
        matches = []
        for _, row in recipes.iterrows():
            recipe_key = _normalize_recipe_text(row.get("name"))
            recipe_id = clean(row.get("recipe_id"))
            if recipe_id and (key in recipe_key or recipe_key in key):
                matches.append(recipe_id)
        if len(matches) == 1:
            return matches[0]

    return None


def normalize_plan_recipe_ids(plan, recipes, foods, strict=True):
    """Normalize recipe IDs while supporting older/partially persisted plans.

    Refinement should not fail merely because an unchanged meal came from an
    older session-state shape. When strict=False, unresolved unchanged meals
    are preserved and only meals that actually need a catalogue lookup are
    required to resolve.
    """
    lookup = recipes.set_index("recipe_id")
    normalized_days = []

    for day in plan_days(plan):
        normalized_meals = []
        for meal in day.get("meals", []):
            meal_copy = dict(meal)
            recipe_id = _resolve_recipe_id(meal_copy, recipes)

            if recipe_id is None:
                display_name = (
                    meal_copy.get("name")
                    or meal_copy.get("recipe_name")
                    or "unknown meal"
                )
                if strict:
                    raise ValueError(
                        f"Could not identify recipe for '{display_name}'. "
                        "The recipe is not present in the current catalogue."
                    )
                # Keep legacy meal data intact. Refinement can still modify a
                # different meal, and this unchanged meal does not need a
                # catalogue lookup unless a global constraint targets it.
                normalized_meals.append(meal_copy)
                continue

            recipe = lookup.loc[recipe_id].to_dict()
            verified = calculate_recipe_nutrition(recipe, foods)
            verified["why"] = meal_copy.get("why", "")
            verified["tags"] = meal_copy.get("tags", [])
            verified["serving_multiplier"] = float(
                meal_copy.get("serving_multiplier", 1.0)
            )
            normalized_meals.append(verified)

        normalized_days.append({
            "day": day["day"],
            "meals": normalized_meals,
            "totals": nutrition_totals(normalized_meals),
        })

    return normalized_days


def _meal_display_name(meal):
    """Return the best available display name from current/legacy meal data."""
    return str(
        meal.get("name")
        or meal.get("recipe_name")
        or (meal.get("recipe", {}).get("name") if isinstance(meal.get("recipe"), dict) else "")
        or "unknown meal"
    ).strip()


def _meal_contains_forbidden(meal, forbidden):
    """Check a meal using either parsed ingredients or its catalogue recipe."""
    if not forbidden:
        return False
    parsed = meal.get("parsed_ingredients", [])
    ingredient_names = [
        str(item.get("food", "")).strip().lower()
        for item in parsed
        if isinstance(item, dict)
    ]
    return any(
        forbidden_item in ingredient
        for forbidden_item in forbidden
        for ingredient in ingredient_names
    )

def refinement_forbidden_ingredients(user_request):
    """Extract simple global 'no/without X' ingredient constraints."""
    request = str(user_request).lower()
    found = []
    patterns = [
        r"\bno\s+([a-z][a-z &'-]{1,40}?)(?:\s+in\s+(?:the\s+)?plan|\s+please|$)",
        r"\bwithout\s+([a-z][a-z &'-]{1,40}?)(?:\s+in\s+(?:the\s+)?plan|\s+please|$)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, request):
            value = re.sub(r"\s+", " ", match.group(1)).strip(" .,!?")
            if value and value not in found:
                found.append(value)
    return found


def recipe_contains_any(recipe, forbidden):
    ingredient_names = [
        str(item["food"]).strip().lower()
        for item in parse_ingredients(recipe["ingredients"])
    ]
    return any(
        forbidden_item in ingredient
        for forbidden_item in forbidden
        for ingredient in ingredient_names
    )


def filter_refinement_candidates(recipe_candidates, user_request):
    """Apply deterministic global ingredient exclusions before the LLM sees candidates."""
    forbidden = refinement_forbidden_ingredients(user_request)
    if not forbidden:
        return recipe_candidates.copy(), forbidden

    mask = ~recipe_candidates.apply(
        lambda row: recipe_contains_any(row, forbidden), axis=1
    )
    return recipe_candidates.loc[mask].copy(), forbidden


def choose_safe_replacement(recipe_candidates, meal_type, forbidden, current_recipe_ids):
    """Deterministically choose a valid replacement when an LLM proposal is unsafe."""
    pool = recipe_candidates[
        recipe_candidates["meal_type"].eq(meal_type)
    ].copy()

    if forbidden:
        pool = pool.loc[
            ~pool.apply(lambda row: recipe_contains_any(row, forbidden), axis=1)
        ].copy()

    pool = pool.loc[~pool["recipe_id"].isin(set(current_recipe_ids))]
    if pool.empty:
        return None

    # Prefer faster recipes, then higher protein, then catalogue order.
    pool["_time"] = pd.to_numeric(pool["total_time_min"], errors="coerce").fillna(9999)
    if "protein_g" in pool.columns:
        pool["_protein"] = pd.to_numeric(pool["protein_g"], errors="coerce").fillna(0)
    else:
        pool["_protein"] = 0.0
    return pool.sort_values(["_time", "_protein"], ascending=[True, False]).iloc[0]["recipe_id"]


def refine_multi_day_plan(
    profile,
    location_context,
    recipe_candidates,
    current_plan,
    user_request,
):
    safe_candidates, forbidden = filter_refinement_candidates(
        recipe_candidates, user_request
    )
    if safe_candidates.empty:
        raise ValueError(
            "No catalogue recipes can satisfy this refinement for the selected "
            "diet, location, season and restrictions."
        )

    candidate_records = [
        recipe_record_for_prompt(row)
        for row in safe_candidates.to_dict(orient="records")
    ]

    # Compatibility layer: plans created before recipe_id was persisted may
    # still be in Streamlit session_state after a deployment/reboot.
    current_plan = normalize_plan_recipe_ids(current_plan, recipes, foods, strict=False)

    # Build the LLM-facing current plan defensively.  Do not index
    # meal["recipe_id"] directly here: older/session-restored plans can have
    # a recipe name without a persisted ID. normalize_plan_recipe_ids()
    # above has already repaired those records, but .get() makes this boundary
    # robust against malformed session-state objects as well.
    current_records = []
    for day in plan_days(current_plan):
        normalized_meals = []
        for meal in day.get("meals", []):
            recipe_id = meal.get("recipe_id")
            recipe_name = _meal_display_name(meal)

            # A legacy unchanged meal may not have a resolvable catalogue ID.
            # Keep its name so the model can preserve it; replacement meals
            # still require a valid catalogue recipe_id at apply time.

            normalized_meals.append(
                {
                    "meal": meal.get("meal_type") or meal.get("meal", ""),
                    "recipe_id": recipe_id,
                    "name": recipe_name,
                    "nutrition": dict(meal.get("nutrition", {})),
                    "total_time_min": int(meal.get("total_time_min", 0)),
                }
            )

        current_records.append(
            {
                "day": day.get("day"),
                "meals": normalized_meals,
                "totals": dict(day.get("totals", nutrition_totals(day.get("meals", [])))),
            }
        )

    system_prompt = """
You are NutriPilot's multi-day conversational refinement engine.

The user already has a multi-day plan.

Rules:
1. Select ONLY recipe_id values from candidate_recipes.
2. Never invent recipes, ingredients, quantities, nutrition values, or cooking steps.
3. Respect diet and foods to avoid.
4. Keep meals unchanged unless the request requires a change.
5. If a day/meal is mentioned, change only that meal.
6. Use total_time_min for time constraints.
7. For higher protein, prefer stronger protein-fit recipes.
8. For no rice, never select a recipe containing rice.
9. Avoid unnecessary repetition.
10. If the request cannot be satisfied, return no changes.
11. Return valid JSON only.

Output:
{
  "assistant_message": "Short response.",
  "changes": [
    {
      "day": 2,
      "meal": "Dinner",
      "recipe_id": "R031",
      "reason": "Why this replacement works."
    }
  ]
}
"""
    result = call_json_model(
        system_prompt,
        {
            "user_profile": profile,
            "location_context": location_context,
            "user_request": user_request,
            "deterministic_forbidden_ingredients": forbidden,
            "current_plan": current_records,
            "candidate_recipes": candidate_records,
        },
    )

    # Preserve the original request for deterministic post-validation.
    if isinstance(result, dict):
        result["_user_request"] = user_request

    return result



def _refinement_intent(user_request):
    """Detect deterministic intents that should never depend solely on the LLM."""
    text = str(user_request or "").casefold()
    return {
        "higher_protein": bool(re.search(r"\b(higher|more|increase|boost)\b.*\bprotein\b|\bprotein\b.*\b(higher|more|increase|boost)\b", text)),
        "time_limit": re.search(r"(?:under|less than|within|below)\s*(\d+)\s*(?:minutes?|mins?)", text),
    }


def _deterministic_refinement_changes(user_request, profile, recipes, foods, recipe_candidates, current_plan):
    """Build catalogue-verified changes for measurable refinement requests.

    The LLM may interpret intent, but it is never the source of truth for
    measurable constraints such as protein or preparation time.
    """
    intent = _refinement_intent(user_request)
    changes = []
    lookup = recipes.set_index("recipe_id")
    forbidden = refinement_forbidden_ingredients(user_request)
    text = str(user_request or "")

    def meal_targets():
        day_match = re.search(r"\bday\s*(\d+)\b", text, re.I)
        meal_match = re.search(r"\b(breakfast|lunch|dinner|snacks?)\b", text, re.I)
        target_day = int(day_match.group(1)) if day_match else None
        target_meal = meal_match.group(1).title() if meal_match else None
        if target_meal == "Snack":
            target_meal = "Snacks"
        out = []
        for day in plan_days(current_plan):
            if target_day is not None and int(day.get("day")) != target_day:
                continue
            for meal in day.get("meals", []):
                mt = meal.get("meal_type") or meal.get("meal", "")
                if target_meal and mt.casefold() != target_meal.casefold():
                    continue
                out.append((day, meal))
        return out

    # Higher protein: first look for a genuinely higher-protein replacement.
    # If the catalogue has no stronger recipe for that meal type, use the
    # existing Phase-7 portion mechanism as a deterministic fallback.
    if intent["higher_protein"]:
        for day, meal in meal_targets():
            mt = meal.get("meal_type") or meal.get("meal")
            current_id = meal.get("recipe_id")
            if current_id in lookup.index:
                current_recipe = lookup.loc[current_id].to_dict()
                current_verified = calculate_recipe_nutrition(current_recipe, foods)
                current_protein = float(current_verified["nutrition"].get("protein_g", 0))
            else:
                current_recipe = None
                current_protein = float(meal.get("nutrition", {}).get("protein_g", 0))

            pool = recipe_candidates[recipe_candidates["meal_type"].eq(mt)].copy()
            if forbidden:
                pool = pool.loc[~pool.apply(lambda row: recipe_contains_any(row, forbidden), axis=1)]
            scored = []
            for _, row in pool.iterrows():
                verified = calculate_recipe_nutrition(row.to_dict(), foods)
                protein = float(verified["nutrition"].get("protein_g", 0))
                scored.append((protein, str(row["recipe_id"])))
            scored.sort(reverse=True)

            if scored and scored[0][0] > current_protein + 0.1:
                changes.append({
                    "day": int(day["day"]), "meal": mt,
                    "recipe_id": scored[0][1],
                    "reason": f"Higher verified protein: {scored[0][0]:.1f} g vs {current_protein:.1f} g."
                })
            elif current_recipe is not None:
                # Increase the whole recipe, never individual ingredients.
                # This is bounded by the existing portion-flexibility range.
                best_multiplier = None
                for multiplier in [round(x, 2) for x in [1.05, 1.10, 1.15, 1.20, 1.25]]:
                    scaled = calculate_scaled_recipe_nutrition(current_recipe, foods, multiplier)
                    if float(scaled["nutrition"]["protein_g"]) > current_protein + 0.1:
                        best_multiplier = multiplier
                        break
                if best_multiplier:
                    changes.append({
                        "day": int(day["day"]), "meal": mt,
                        "recipe_id": str(current_recipe["recipe_id"]),
                        "serving_multiplier": best_multiplier,
                        "reason": f"Increased the complete recipe to {best_multiplier:.2f}× for higher verified protein."
                    })

    # Time constraint: inspect every meal. Only claim a change when the
    # replacement actually satisfies the requested limit. If no recipe exists
    # for a meal type under the limit, report that limitation rather than
    # silently selecting an invalid recipe.
    if intent["time_limit"]:
        limit = int(intent["time_limit"].group(1))
        for day in plan_days(current_plan):
            for meal in day.get("meals", []):
                mt = meal.get("meal_type") or meal.get("meal")
                current_id = meal.get("recipe_id")
                if current_id in lookup.index:
                    current_time = int(float(lookup.loc[current_id].get("total_time_min", 9999)))
                else:
                    current_time = int(float(meal.get("total_time_min", 9999)))
                if current_time <= limit:
                    continue

                pool = recipe_candidates[recipe_candidates["meal_type"].eq(mt)].copy()
                pool = pool[pd.to_numeric(pool["total_time_min"], errors="coerce") <= limit]
                if forbidden:
                    pool = pool.loc[~pool.apply(lambda row: recipe_contains_any(row, forbidden), axis=1)]
                existing_ids = {str(c.get("recipe_id")) for c in changes}
                pool = pool[~pool["recipe_id"].astype(str).isin(existing_ids)]
                if not pool.empty:
                    pool = pool.copy()
                    pool["_time"] = pd.to_numeric(pool["total_time_min"], errors="coerce")
                    rid = str(pool.sort_values("_time").iloc[0]["recipe_id"])
                    if not any(c["day"] == int(day["day"]) and c["meal"] == mt for c in changes):
                        changes.append({
                            "day": int(day["day"]), "meal": mt, "recipe_id": rid,
                            "reason": f"Meets the {limit}-minute time limit."
                        })
    return changes


def apply_plan_changes(raw_result, profile, recipes, foods, recipe_candidates, current_plan):
    lookup = recipes.set_index("recipe_id")
    current_plan = normalize_plan_recipe_ids(current_plan, recipes, foods, strict=False)
    result = [
        {
            "day": day["day"],
            "meals": list(day["meals"]),
            "totals": dict(day["totals"]),
        }
        for day in plan_days(current_plan)
    ]

    if not isinstance(raw_result, dict):
        raise ValueError("AI returned an invalid refinement response.")

    changes = raw_result.get("changes", [])
    if not isinstance(changes, list):
        raise ValueError("AI returned an invalid changes list.")

    # For deterministic intents, discard LLM changes for the same target and
    # let the verified catalogue decision below be authoritative. This prevents
    # an AI-proposed but invalid time/protein change from being applied.
    deterministic_intent = _refinement_intent(raw_result.get("_user_request", ""))
    if deterministic_intent["higher_protein"] or deterministic_intent["time_limit"]:
        # These requests are measurable. Do not apply any model-proposed
        # replacement first; generate the authoritative catalogue-verified
        # changes below. This also prevents an invalid AI response from being
        # reported as a successful refinement.
        changes = []

    # The LLM is an interpreter, not the final decision-maker for deterministic
    # constraints. If it returned no changes (or missed a simple constraint),
    # supplement its output with catalogue-verified replacements.
    deterministic = _deterministic_refinement_changes(
        raw_result.get("_user_request", ""), profile, recipes, foods, recipe_candidates, current_plan
    )
    existing_keys = {(int(c.get("day")), str(c.get("meal", "")).casefold()) for c in changes if isinstance(c, dict) and c.get("day") is not None}
    for change in deterministic:
        key = (int(change["day"]), str(change["meal"]).casefold())
        if key not in existing_keys:
            changes.append(change)
            existing_keys.add(key)

    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("AI returned a malformed plan change.")
        if change.get("day") is None:
            raise ValueError("A refinement change is missing its day.")

        day_number = int(change["day"])
        meal_type = change.get("meal")
        recipe_id = change.get("recipe_id")

        if not meal_type:
            raise ValueError("A refinement change is missing its meal type.")
        if not recipe_id:
            raise ValueError(
                "The AI did not provide a recipe_id for the requested replacement."
            )

        day = next((d for d in result if d["day"] == day_number), None)
        if day is None:
            raise ValueError(f"Unknown day: {day_number}")
        if meal_type not in profile["meals"]:
            raise ValueError(f"Unrequested meal: {meal_type}")
        if recipe_id not in lookup.index:
            raise ValueError(f"Unsupported recipe_id: {recipe_id}")

        recipe = lookup.loc[recipe_id].to_dict()
        if recipe["meal_type"] != meal_type:
            raise ValueError(
                f"Recipe {recipe_id} is {recipe['meal_type']}, not {meal_type}."
            )

        # Deterministic refinement constraint handling. If the model ignored a
        # global exclusion, repair the proposal with a safe catalogue recipe
        # instead of failing the entire refinement.
        request_text = str(raw_result.get("_user_request", ""))
        forbidden = refinement_forbidden_ingredients(request_text)
        if forbidden and recipe_contains_any(recipe, forbidden):
            current_recipe_ids = [
                m.get("recipe_id")
                for d in result
                for m in d.get("meals", [])
                if m.get("recipe_id")
            ]
            fallback_id = choose_safe_replacement(
                recipe_candidates, meal_type, forbidden, current_recipe_ids
            )
            if fallback_id is None:
                raise ValueError(
                    f"No safe catalogue replacement is available for {meal_type} "
                    f"under the requested constraint(s): {', '.join(forbidden)}."
                )
            recipe_id = fallback_id
            recipe = lookup.loc[recipe_id].to_dict()

        multiplier = float(change.get("serving_multiplier", 1.0) or 1.0)
        verified = calculate_scaled_recipe_nutrition(recipe, foods, multiplier)
        verified["why"] = change.get("reason", "")
        verified["tags"] = ["refined", "constraint-validated"] if multiplier != 1.0 else ["refined"]
        verified["serving_multiplier"] = multiplier

        for i, old_meal in enumerate(day["meals"]):
            if old_meal["meal_type"] == meal_type:
                day["meals"][i] = verified
                break

        day["totals"] = nutrition_totals(day["meals"])

    # Global constraint repair: phrases such as "No rice in the plan" apply
    # to the whole plan, not just one meal. Ensure every remaining violating
    # meal is replaced deterministically.
    request_text = str(raw_result.get("_user_request", ""))
    forbidden = refinement_forbidden_ingredients(request_text)
    if forbidden:
        for day in result:
            for idx, meal in enumerate(day.get("meals", [])):
                # Check the persisted ingredient list first so an older
                # unchanged meal can still participate in a global exclusion.
                if meal.get("parsed_ingredients"):
                    violates = _meal_contains_forbidden(meal, forbidden)
                elif meal.get("recipe_id") in lookup.index:
                    recipe = lookup.loc[meal["recipe_id"]].to_dict()
                    violates = recipe_contains_any(recipe, forbidden)
                else:
                    # Unknown legacy recipe: do not invent a replacement.
                    # The deterministic candidate filter already prevents new
                    # unsafe recipes from entering the plan.
                    violates = False

                if not violates:
                    continue

                current_recipe_ids = [
                    m.get("recipe_id")
                    for d in result
                    for m in d.get("meals", [])
                    if m.get("recipe_id")
                ]
                fallback_id = choose_safe_replacement(
                    recipe_candidates,
                    meal["meal_type"],
                    forbidden,
                    current_recipe_ids,
                )
                if fallback_id is None:
                    raise ValueError(
                        f"No safe catalogue replacement is available for "
                        f"{meal['meal_type']} under: {', '.join(forbidden)}."
                    )

                fallback_recipe = lookup.loc[fallback_id].to_dict()
                verified = calculate_recipe_nutrition(fallback_recipe, foods)
                verified["why"] = (
                    f"Replaced to satisfy: no {', '.join(forbidden)}."
                )
                verified["tags"] = ["refined", "constraint-validated"]
                verified["serving_multiplier"] = 1.0
                day["meals"][idx] = verified

            day["totals"] = nutrition_totals(day["meals"])

    raw_result["_applied_changes"] = list(changes)
    return result


# Include each CSV's modification time in the cache key. Streamlit's cache
# otherwise keys only on the function/arguments, so replacing data/recipes.csv
# during a deployment can leave an old recipe catalogue in memory. That stale
# catalogue is what caused valid recipes such as R007 to appear "missing"
# during refinement.
foods = load_food_data(_data_file_version(FOOD_DATA_PATH))
recipes = load_recipe_data(_data_file_version(RECIPE_DATA_PATH))
locations = load_location_data(_data_file_version(LOCATION_DATA_PATH))
source_registry = load_source_registry()

# Detect mismatched/stale CSV files before the user reaches the AI step.
catalogue_errors = validate_catalogue_integrity(foods, recipes)

# Fail early on a structurally broken recipe catalogue rather than allowing
# refinement to fail later with a misleading recipe-resolution error.
if "recipe_id" not in recipes.columns or "name" not in recipes.columns:
    catalogue_errors.append("Recipe catalogue must contain recipe_id and name columns.")

if "user_profile" not in st.session_state:
    st.session_state.user_profile = None
if "location_context" not in st.session_state:
    st.session_state.location_context = None
if "meal_plan" not in st.session_state:
    st.session_state.meal_plan = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "plan_settings" not in st.session_state:
    st.session_state.plan_settings = None
if "single_meal" not in st.session_state:
    st.session_state.single_meal = None

st.title("NutriPilot")
st.caption("Local · seasonal · AI-assisted meal planning")
st.caption("Build: Refinement V5")
st.subheader("Your local, seasonal nutrition copilot.")
st.write("Meal recommendations shaped by your goals, diet, location, season and current weather.")

st.divider()
st.header("Your Profile")

countries = sorted(locations["country"].unique().tolist())
country = st.selectbox("Country", countries, key="country_select")

region_options = sorted(
    locations.loc[locations["country"] == country, "region"].unique().tolist()
)
region = st.selectbox("State / Region", region_options, key="region_select")

city_options = sorted(
    locations.loc[
        (locations["country"] == country) & (locations["region"] == region),
        "city",
    ].unique().tolist()
)
city = st.selectbox("City", city_options, key="city_select")

goal = st.selectbox(
    "Primary goal",
    ["General wellness", "Weight management", "Muscle gain", "High protein", "Better energy"],
    key="goal_select",
)

diet = st.selectbox(
    "Diet",
    ["Vegetarian", "Vegan", "Eggetarian", "Non-vegetarian"],
    key="diet_select",
)

restrictions = st.text_input(
    "Allergies or foods to avoid",
    placeholder="e.g., peanuts, mushrooms, lactose",
    key="restrictions_input",
)

meals = st.multiselect(
    "Meals to plan",
    ["Breakfast", "Lunch", "Dinner", "Snacks"],
    default=["Breakfast", "Lunch", "Dinner"],
    key="meals_select",
)

st.subheader("How do you want to use NutriPilot?")

planning_mode = st.radio(
    "Choose a planning mode",
    ["Just one meal", "Multi-day schedule"],
    horizontal=True,
    key="planning_mode",
    help="Choose one meal for an on-demand recommendation, or build a 3–7 day schedule.",
)

if planning_mode == "Multi-day schedule":
    st.subheader("Schedule Settings")

    plan_days_count = st.selectbox(
        "Plan length",
        [3, 5, 7],
        index=0,
        format_func=lambda x: f"{x} days",
        key="plan_days_count",
    )

    target_mode = st.selectbox(
        "Daily calorie target",
        ["No target", "1,600 kcal", "2,000 kcal", "2,400 kcal", "Custom"],
        key="daily_calorie_mode",
    )

    if target_mode == "Custom":
        calorie_target = st.number_input(
            "Custom daily calories",
            min_value=800, max_value=5000, value=2000, step=50,
            key="custom_daily_calories",
        )
    elif target_mode == "1,600 kcal":
        calorie_target = 1600
    elif target_mode == "2,000 kcal":
        calorie_target = 2000
    elif target_mode == "2,400 kcal":
        calorie_target = 2400
    else:
        calorie_target = None

    protein_mode = st.selectbox(
        "Daily protein target",
        ["No target", "60 g", "90 g", "120 g", "Custom"],
        key="daily_protein_mode",
    )

    if protein_mode == "Custom":
        protein_target = st.number_input(
            "Custom daily protein (g)",
            min_value=20, max_value=300, value=90, step=5,
            key="custom_daily_protein",
        )
    elif protein_mode == "60 g":
        protein_target = 60
    elif protein_mode == "90 g":
        protein_target = 90
    elif protein_mode == "120 g":
        protein_target = 120
    else:
        protein_target = None

    portion_flexibility = st.selectbox(
        "Portion flexibility",
        ["Standard (±25%)", "Tighter (±15%)"],
        help="Adjusts the complete recipe serving size without changing ingredient ratios.",
        key="portion_flexibility",
    )
    portion_adjustment = (
        0.25 if portion_flexibility.startswith("Standard") else 0.15
    )

    st.caption(
        "Targets are planning preferences you choose; NutriPilot does not prescribe "
        "medical or therapeutic nutrition targets."
    )
else:
    # On-demand mode intentionally has no planning horizon or daily targets.
    plan_days_count = 1
    calorie_target = None
    protein_target = None
    portion_adjustment = 0.25

if st.button(
    "Load Local Context",
    type="primary",
    icon=":material/location_on:",
    use_container_width=True,
    key="load_local_context",
):
    if not meals:
        st.error("Select at least one meal.")
        st.stop()

    st.session_state.user_profile = {
        "country": country,
        "region": region,
        "city": city,
        "goal": goal,
        "diet": diet,
        "restrictions": restrictions.strip(),
        "meals": meals,
    }

    try:
        with st.spinner("Resolving your location and weather..."):
            location = validate_location(country, region, city)
            if not location:
                st.error("This location could not be resolved by Open-Meteo.")
                st.stop()

            weather = get_current_weather(
                location["latitude"],
                location["longitude"],
                location.get("timezone", "auto"),
            )
            current = weather["current"]
            local_time = datetime.fromisoformat(current["time"])

            season = get_season(local_time.month, location["latitude"], country)

            context = {
                "resolved_location": {
                    "name": location.get("name"),
                    "region": location.get("admin1"),
                    "country": location.get("country"),
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "timezone": location.get("timezone"),
                },
                "season": season,
                "weather": {
                    "temperature_c": current.get("temperature_2m"),
                    "apparent_temperature_c": current.get("apparent_temperature"),
                    "humidity_pct": current.get("relative_humidity_2m"),
                    "precipitation_mm": current.get("precipitation"),
                    "wind_kmh": current.get("wind_speed_10m"),
                    "condition": weather_label(
                        current.get("weather_code"),
                        current.get("temperature_2m"),
                        current.get("precipitation") or 0,
                    ),
                    "local_time": current.get("time"),
                },
            }

            st.session_state.location_context = context
            st.session_state.meal_plan = None
            st.session_state.single_meal = None
            st.session_state.chat_messages = []
            st.session_state.plan_settings = {
                "mode": planning_mode,
                "days": plan_days_count,
                "calorie_target": calorie_target,
                "protein_target": protein_target,
                "portion_adjustment": portion_adjustment,
            }

    except requests.RequestException as exc:
        st.error(f"Location/weather service error: {exc}")
    except (TypeError, ValueError) as exc:
        st.error(f"Could not process location/weather data: {exc}")

profile = st.session_state.user_profile
context = st.session_state.location_context

if profile and context:
    st.divider()
    st.header("Your Local Context")

    weather = context["weather"]
    location = context["resolved_location"]
    cols = st.columns(4)

    with cols[0]:
        st.metric("Temperature", f"{weather['temperature_c']} °C")
    with cols[1]:
        st.metric("Feels like", f"{weather['apparent_temperature_c']} °C")
    with cols[2]:
        st.metric("Humidity", f"{weather['humidity_pct']}%")
    with cols[3]:
        st.metric("Wind", f"{weather['wind_kmh']} km/h")

    st.success(f"**{weather['condition']} · {context['season']}**")
    st.write(f"**Location:** {location['name']}, {location['region']}, {location['country']}")

    recipe_candidates = build_recipe_candidates(recipes, foods, profile, context)

    st.caption(
        f"{len(recipe_candidates)} recipe candidates match the current "
        "diet, restrictions, season and location context."
    )

    with st.expander("View candidate recipe catalogue"):
        st.dataframe(
            recipe_candidates[["recipe_id", "name", "meal_type", "cuisine", "regions", "season", "goal_tags", "total_time_min", "difficulty"]],
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Food data provenance"):
        st.caption(
            "Food composition is kept separate from recipe and AI logic. "
            "Each food record carries its source, source version, data basis and "
            "licensing metadata so production ingestion can be audited."
        )
        st.dataframe(
            food_source_summary(foods),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "USDA FoodData Central is the primary scalable CC0 source. "
            "ICMR-NIN IFCT 2017 is the Indian reference; production import should "
            "use an approved structured dataset/export rather than scraping the PDF."
        )

    st.divider()

    settings = st.session_state.plan_settings or {
        "mode": planning_mode,
        "days": plan_days_count,
        "calorie_target": calorie_target,
        "protein_target": protein_target,
        "portion_adjustment": portion_adjustment,
    }

    if settings.get("mode") == "Just one meal":
        st.header("On-Demand Meal")
        st.write(
            "Get one practical recommendation without creating a multi-day schedule."
        )

        meal_choice = st.selectbox(
            "Which meal do you want help with?",
            profile["meals"],
            key="single_meal_choice",
        )

        if st.button(
            "Recommend My Meal",
            type="primary",
            icon=":material/restaurant:",
            use_container_width=True,
            key="recommend_single_meal",
        ):
            try:
                with st.spinner("Finding the best catalogue recipe for you..."):
                    st.session_state.single_meal = generate_single_meal(
                        profile,
                        context,
                        recipe_candidates,
                        foods,
                        recipes,
                        meal_choice,
                    )
            except (ValueError, KeyError) as exc:
                st.error(f"Could not safely generate the meal: {exc}")
            except Exception as exc:
                st.error(f"Meal recommendation failed: {exc}")

        meal = st.session_state.single_meal
        if meal:
            st.success(f"**{meal['meal_type']} · {meal['name']}**")
            if meal.get("why"):
                st.write(meal["why"])

            nutrition = meal["nutrition"]
            cols = st.columns(4)
            with cols[0]:
                st.metric("Calories", f"{nutrition['calories_kcal']:.0f} kcal")
            with cols[1]:
                st.metric("Protein", f"{nutrition['protein_g']:.1f} g")
            with cols[2]:
                st.metric("Carbs", f"{nutrition['carbs_g']:.1f} g")
            with cols[3]:
                st.metric("Time", f"{meal['total_time_min']} min")

            st.write("**Ingredients**")
            st.dataframe(
                pd.DataFrame(meal["parsed_ingredients"]),
                use_container_width=True,
                hide_index=True,
            )

    else:
        st.header("AI Meal Planner")
        st.write(
            "Build a multi-day plan from the validated recipe catalogue and optimize "
            "serving sizes against your selected targets."
        )

        if st.button(
            "Generate My Multi-Day Plan",
            type="primary",
            icon=":material/auto_awesome:",
            use_container_width=True,
            key="generate_multi_day_plan",
        ):
            try:
                with st.spinner("Building your multi-day plan..."):
                    generated = generate_multi_day_plan(
                        profile,
                        context,
                        recipe_candidates,
                        foods,
                        recipes,
                        settings["days"],
                        settings["calorie_target"],
                        settings["protein_target"],
                    )
                    generated = optimize_plan_portions(
                        generated,
                        foods,
                        settings["calorie_target"],
                        settings["protein_target"],
                        settings["portion_adjustment"],
                    )
                st.session_state.meal_plan = generated
                st.session_state.chat_messages = []
            except (ValueError, KeyError) as exc:
                st.error(f"Could not safely generate the plan: {exc}")
            except Exception as exc:
                st.error(f"Plan generation failed: {exc}")

        plan = st.session_state.meal_plan

        if plan:
            st.subheader("Your Plan")

            for day in plan_days(plan):
                st.markdown(f"### Day {day['day']}")
                for meal in day["meals"]:
                    nutrition = meal["nutrition"]
                    st.markdown(
                        f"**{meal['meal_type']}: {meal['name']}** · "
                        f"{nutrition['calories_kcal']:.0f} kcal · "
                        f"{nutrition['protein_g']:.1f} g protein · "
                        f"{meal.get('total_time_min', 0)} min · "
                        f"{meal.get('serving_multiplier', 1.0):.2f}× serving"
                    )
                    ingredient_text = ", ".join(
                        f"{item['food']} ({item['grams']:.0f} g)"
                        for item in meal["parsed_ingredients"]
                    )
                    st.caption(f"Ingredients: {ingredient_text}")
                    if meal.get("why"):
                        st.caption(meal["why"])

                st.info(
                    f"Day {day['day']} total: "
                    f"{day['totals']['calories_kcal']:.0f} kcal · "
                    f"{day['totals']['protein_g']:.1f} g protein"
                )

            st.divider()
            st.header("Shopping List")
            shopping = build_shopping_list(plan)
            st.dataframe(shopping, use_container_width=True, hide_index=True)
            st.download_button(
                "Download Shopping List (CSV)",
                icon=":material/download:",
                data=shopping.to_csv(index=False).encode("utf-8"),
                file_name="nutripilot_shopping_list.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_shopping_list",
            )

            st.divider()
            st.header("Refine Your Plan")
            st.write(
                "Ask NutriPilot to change part of the multi-day plan while keeping "
                "the remaining meals intact."
            )

            quick_actions = st.columns(3)
            quick_requests = [
                "Make Day 1 dinner higher protein",
                "No rice in the plan",
                "Keep every meal under 20 minutes",
            ]

            selected_quick = None
            for idx, label in enumerate(quick_requests):
                with quick_actions[idx]:
                    if st.button(
                        label,
                        icon=":material/arrow_forward:",
                        use_container_width=True,
                        key=f"quick_refinement_{idx}",
                    ):
                        selected_quick = label

            for message in st.session_state.chat_messages:
                with st.chat_message(message["role"]):
                    st.write(message["content"])

            user_request = st.chat_input(
                "e.g. Replace Day 2 lunch with something quicker",
                key="plan_refinement_input",
            )
            request_to_process = selected_quick or user_request

            if request_to_process:
                st.session_state.chat_messages.append(
                    {"role": "user", "content": request_to_process}
                )

                try:
                    with st.spinner("Refining your plan..."):
                        raw_result = refine_multi_day_plan(
                            profile,
                            context,
                            recipe_candidates,
                            st.session_state.meal_plan,
                            request_to_process,
                        )
                        raw_result["_user_request"] = request_to_process

                        updated = apply_plan_changes(
                            raw_result,
                            profile,
                            recipes,
                            foods,
                            recipe_candidates,
                            st.session_state.meal_plan,
                        )

                        updated = optimize_plan_portions(
                            updated,
                            foods,
                            settings["calorie_target"],
                            settings["protein_target"],
                            settings["portion_adjustment"],
                        )

                        st.session_state.meal_plan = updated
                        applied_changes = raw_result.get("_applied_changes", [])
                        if applied_changes:
                            assistant_message = f"Changes made to satisfy your request ({len(applied_changes)} meal{'s' if len(applied_changes) != 1 else ''} updated)."
                        else:
                            assistant_message = raw_result.get(
                                "assistant_message",
                                "I couldn't make that change using the current recipe catalogue.",
                            )
                            deterministic_intent = _refinement_intent(request_to_process)
                            if deterministic_intent["time_limit"]:
                                limit = int(deterministic_intent["time_limit"].group(1))
                                assistant_message = (
                                    f"I couldn't fully satisfy the {limit}-minute limit with the current recipe catalogue. "
                                    "Some meal types do not have a recipe within that limit."
                                )
                            elif deterministic_intent["higher_protein"]:
                                assistant_message = (
                                    "I couldn't increase protein for the requested meal within the current "
                                    "catalogue and portion-flexibility limits."
                                )

                        st.session_state.chat_messages.append(
                            {"role": "assistant", "content": assistant_message}
                        )
                        st.rerun()

                except (ValueError, KeyError) as exc:
                    error_message = f"I couldn't apply that change safely: {exc}"
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": error_message}
                    )
                    st.error(error_message)
                except Exception as exc:
                    st.error(f"Refinement failed: {exc}")


if catalogue_errors:
    with st.expander("Data catalogue mismatch detected", expanded=True):
        st.error(
            "Some recipes reference ingredients that are missing from the deployed "
            "`data/foods.csv`. Replace the entire `data` folder with the one from the "
            "NutriPilot Phase 4 Fixed ZIP and redeploy."
        )
        for recipe_id, missing_foods in catalogue_errors.items():
            st.write(f"**{recipe_id}:** {', '.join(missing_foods)}")

st.caption(
    "NutriPilot is a meal-planning prototype. Nutrition targets are user-selected "
    "planning preferences, not medical or dietary prescriptions."
)
