
import json
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="NutriPilot", page_icon="🥗", layout="centered")

FOOD_DATA_PATH = "data/foods.csv"
RECIPE_DATA_PATH = "data/recipes.csv"
LOCATION_DATA_PATH = "data/locations.csv"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


@st.cache_data
def load_food_data():
    return pd.read_csv(FOOD_DATA_PATH)


@st.cache_data
def load_recipe_data():
    return pd.read_csv(RECIPE_DATA_PATH)


@st.cache_data
def load_location_data():
    return pd.read_csv(LOCATION_DATA_PATH)


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
            raise ValueError(f"Recipe contains unsupported food: {food}")

        row = lookup.loc[food]
        factor = grams / 100
        for field in totals:
            totals[field] += float(row[field]) * factor

        verified.append({"food": food, "grams": grams})

    result = recipe.copy()
    result["parsed_ingredients"] = verified
    result["nutrition"] = {key: round(value, 1) for key, value in totals.items()}
    return result


def generate_meal_plan(profile, location_context, recipe_candidates):
    if "OPENAI_API_KEY" not in st.secrets:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to Streamlit secrets.")

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    candidate_records = recipe_candidates[
        [
            "recipe_id", "name", "meal_type", "cuisine", "regions",
            "season", "diet", "goal_tags", "weather_tags", "ingredients"
        ]
    ].to_dict(orient="records")

    system_prompt = """
You are NutriPilot, a local, seasonal meal-planning copilot.

The recipe catalogue is the source of truth.

Rules:
1. Recommend ONLY recipe_id values from the provided catalogue.
2. Do not invent recipes, ingredients, quantities, nutrition values, or cooking steps.
3. Respect diet and foods to avoid.
4. Prefer recipes whose season and weather tags fit the current context.
5. Consider weather as a meal-style preference, not a medical rule.
6. Use the user's goal to rank suitable recipes.
7. Return exactly one recipe for each requested meal type when possible.
8. Return valid JSON only.

Output:
{
  "meals": [
    {
      "meal": "Breakfast",
      "recipe_id": "R001",
      "why": "Short explanation tied to goal, location, season and weather.",
      "tags": ["seasonal", "local"]
    }
  ]
}
"""

    user_prompt = {
        "user_profile": profile,
        "location_context": location_context,
        "requested_meals": profile["meals"],
        "candidate_recipes": candidate_records,
    }

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt)},
        ],
    )

    return json.loads(response.choices[0].message.content)


foods = load_food_data()
recipes = load_recipe_data()
locations = load_location_data()

if "user_profile" not in st.session_state:
    st.session_state.user_profile = None
if "location_context" not in st.session_state:
    st.session_state.location_context = None
if "meal_plan" not in st.session_state:
    st.session_state.meal_plan = None

st.title("🥗 NutriPilot")
st.subheader("Your local, seasonal nutrition copilot.")
st.write("Meal recommendations shaped by your goals, diet, location, season and current weather.")

st.divider()
st.header("👤 Your Profile")

countries = sorted(locations["country"].unique().tolist())
country = st.selectbox("Country", countries)

region_options = sorted(
    locations.loc[locations["country"] == country, "region"].unique().tolist()
)
region = st.selectbox("State / Region", region_options)

city_options = sorted(
    locations.loc[
        (locations["country"] == country) & (locations["region"] == region),
        "city",
    ].unique().tolist()
)
city = st.selectbox("City", city_options)

goal = st.selectbox(
    "Primary goal",
    ["General wellness", "Weight management", "Muscle gain", "High protein", "Better energy"],
)

diet = st.selectbox(
    "Diet",
    ["Vegetarian", "Vegan", "Eggetarian", "Non-vegetarian"],
)

restrictions = st.text_input(
    "Allergies or foods to avoid",
    placeholder="e.g., peanuts, mushrooms, lactose",
)

meals = st.multiselect(
    "Meals to plan",
    ["Breakfast", "Lunch", "Dinner", "Snacks"],
    default=["Breakfast", "Lunch", "Dinner"],
)

if st.button("Set Profile & Load Local Context", type="primary", use_container_width=True):
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

    except requests.RequestException as exc:
        st.error(f"Location/weather service error: {exc}")
    except (TypeError, ValueError) as exc:
        st.error(f"Could not process location/weather data: {exc}")

profile = st.session_state.user_profile
context = st.session_state.location_context

if profile and context:
    st.divider()
    st.header("🌦️ Your Local Context")

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
            recipe_candidates[["recipe_id", "name", "meal_type", "cuisine", "regions", "season", "goal_tags"]],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.header("🤖 AI Meal Planner")
    st.write(
        "The AI now ranks real recipes from the catalogue instead of inventing "
        "ingredient combinations. Nutrition is calculated deterministically from the food database."
    )

    if st.button("Generate My Meal Plan", type="primary", use_container_width=True):
        try:
            with st.spinner("Selecting the best recipes for your context..."):
                raw_plan = generate_meal_plan(profile, context, recipe_candidates)
                lookup = recipes.set_index("recipe_id")
                verified_plan = []

                for item in raw_plan.get("meals", []):
                    recipe_id = item.get("recipe_id")
                    if recipe_id not in lookup.index:
                        raise ValueError(f"AI returned unsupported recipe_id: {recipe_id}")

                    recipe = lookup.loc[recipe_id].to_dict()

                    if recipe["meal_type"] not in profile["meals"]:
                        raise ValueError(f"AI selected a recipe outside requested meals: {recipe_id}")

                    verified = calculate_recipe_nutrition(recipe, foods)
                    verified["why"] = item.get("why", "")
                    verified["tags"] = item.get("tags", [])
                    verified_plan.append(verified)

                st.session_state.meal_plan = verified_plan

        except Exception as exc:
            st.error(f"Could not generate the meal plan: {exc}")

    if st.session_state.meal_plan:
        st.divider()
        st.header("🍽️ Your NutriPilot Plan")

        for meal in st.session_state.meal_plan:
            st.subheader(f"{meal['meal_type']} — {meal['name']}")
            ingredient_text = " · ".join(
                f"{item['food']} ({item['grams']:.0f} g)"
                for item in meal["parsed_ingredients"]
            )
            st.write(f"**Ingredients:** {ingredient_text}")

            nutrition = meal["nutrition"]
            metric_cols = st.columns(4)
            with metric_cols[0]:
                st.metric("Calories", f"{nutrition['calories_kcal']:.0f} kcal")
            with metric_cols[1]:
                st.metric("Protein", f"{nutrition['protein_g']:.1f} g")
            with metric_cols[2]:
                st.metric("Carbs", f"{nutrition['carbs_g']:.1f} g")
            with metric_cols[3]:
                st.metric("Fiber", f"{nutrition['fiber_g']:.1f} g")

            st.write(f"**Why this meal?** {meal.get('why', '')}")
            if meal.get("tags"):
                st.caption(" · ".join(meal["tags"]))
            st.divider()

st.caption("NutriPilot is a meal-planning prototype, not medical or dietary advice.")
