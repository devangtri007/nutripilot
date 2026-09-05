
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


def generate_meal_plan(profile, location_context, recipe_candidates):
    candidate_records = [
        recipe_record_for_prompt(row)
        for row in recipe_candidates.to_dict(orient="records")
    ]

    system_prompt = """
You are NutriPilot, a local, seasonal meal-planning copilot.

The recipe catalogue is the source of truth.

Rules:
1. Recommend ONLY recipe_id values from the provided catalogue.
2. Never invent recipes, ingredients, quantities, nutrition values, or cooking steps.
3. Respect diet and foods to avoid.
4. Prefer recipes whose season, region and weather tags fit the current context.
5. Use the user's goal to rank suitable recipes.
6. Return exactly one recipe for each requested meal type when possible.
7. Return valid JSON only.

Output:
{
  "meals": [
    {
      "meal": "Breakfast",
      "recipe_id": "R001",
      "why": "Short explanation tied to the user's context.",
      "tags": ["seasonal", "goal-fit"]
    }
  ]
}
"""

    return call_json_model(
        system_prompt,
        {
            "user_profile": profile,
            "location_context": location_context,
            "requested_meals": profile["meals"],
            "candidate_recipes": candidate_records,
        },
    )


def refine_meal_plan(profile, location_context, recipe_candidates, current_plan, user_request):
    candidate_records = [
        recipe_record_for_prompt(row)
        for row in recipe_candidates.to_dict(orient="records")
    ]

    current_records = []
    for meal in current_plan:
        current_records.append({
            "meal": meal["meal_type"],
            "recipe_id": meal["recipe_id"],
            "name": meal["name"],
            "ingredients": meal["ingredients"],
            "nutrition": meal["nutrition"],
            "total_time_min": int(meal["total_time_min"]),
            "difficulty": meal["difficulty"],
        })

    system_prompt = """
You are NutriPilot's conversational meal-plan refinement engine.

The user already has a meal plan. Interpret their latest request and modify
ONLY what is necessary.

The recipe catalogue is the source of truth.

Rules:
1. You may ONLY select recipe_id values from candidate_recipes.
2. Never invent a recipe, ingredient, quantity, nutrition value, or cooking step.
3. Respect the user's diet and foods to avoid at all times.
4. Keep meals unchanged unless the user's request requires a change.
5. If the user asks to replace/change a particular meal, replace only that meal.
6. If the user gives a constraint such as "under 20 minutes", select recipes whose
   total_time_min is actually <= 20.
7. For "higher protein", prefer recipes with high-protein goal tags and higher
   verified protein where useful.
8. For "no rice", do not select recipes containing rice.
9. Use season, location and weather context as secondary ranking signals.
10. If the request cannot be satisfied from the candidate catalogue, do not invent
    anything. Return an empty changes list and explain why.
11. Return valid JSON only.

Output:
{
  "assistant_message": "Short natural-language response.",
  "changes": [
    {
      "meal": "Dinner",
      "recipe_id": "R031",
      "reason": "Why this replacement satisfies the request."
    }
  ]
}
"""

    return call_json_model(
        system_prompt,
        {
            "user_profile": profile,
            "location_context": location_context,
            "user_request": user_request,
            "current_meal_plan": current_records,
            "candidate_recipes": candidate_records,
        },
    )


def verify_and_apply_changes(raw_result, profile, recipes, foods, current_plan):
    lookup = recipes.set_index("recipe_id")
    current_by_meal = {meal["meal_type"]: meal for meal in current_plan}
    updated = list(current_plan)

    changes = raw_result.get("changes", [])
    for change in changes:
        meal_type = change.get("meal")
        recipe_id = change.get("recipe_id")

        if meal_type not in profile["meals"]:
            raise ValueError(f"AI tried to modify an unrequested meal: {meal_type}")

        if recipe_id not in lookup.index:
            raise ValueError(f"AI returned unsupported recipe_id: {recipe_id}")

        recipe = lookup.loc[recipe_id].to_dict()

        if recipe["meal_type"] != meal_type:
            raise ValueError(
                f"Recipe {recipe_id} is a {recipe['meal_type']} recipe, "
                f"not a {meal_type} recipe."
            )

        verified = calculate_recipe_nutrition(recipe, foods)
        verified["why"] = change.get("reason", "")
        verified["tags"] = ["refined"]
        current_by_meal[meal_type] = verified

    # Preserve the user's requested meal order.
    for i, meal_type in enumerate(profile["meals"]):
        if meal_type in current_by_meal:
            updated[i:i+1] = [current_by_meal[meal_type]]

    # Remove accidental duplicates while preserving requested order.
    final = []
    seen = set()
    for meal_type in profile["meals"]:
        if meal_type in current_by_meal and meal_type not in seen:
            final.append(current_by_meal[meal_type])
            seen.add(meal_type)

    return final


foods = load_food_data()
recipes = load_recipe_data()
locations = load_location_data()

# Detect mismatched/stale CSV files before the user reaches the AI step.
catalogue_errors = validate_catalogue_integrity(foods, recipes)

if "user_profile" not in st.session_state:
    st.session_state.user_profile = None
if "location_context" not in st.session_state:
    st.session_state.location_context = None
if "meal_plan" not in st.session_state:
    st.session_state.meal_plan = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

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
            st.session_state.chat_messages = []

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
            recipe_candidates[["recipe_id", "name", "meal_type", "cuisine", "regions", "season", "goal_tags", "total_time_min", "difficulty"]],
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
            st.caption(
                f"{meal['total_time_min']:.0f} min total · "
                f"{meal['difficulty']} · {meal['cuisine']}"
            )
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


        st.divider()
        st.header("💬 Refine Your Plan")
        st.write(
            "Tell NutriPilot what you want to change. It will select another "
            "catalogue recipe and re-check the result before updating your plan."
        )

        quick_actions = st.columns(3)
        quick_requests = [
            "Make dinner higher protein",
            "No rice in the plan",
            "Keep meals under 20 minutes",
        ]

        selected_quick = None
        for idx, label in enumerate(quick_requests):
            with quick_actions[idx]:
                if st.button(label, use_container_width=True):
                    selected_quick = label

        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        user_request = st.chat_input(
            "e.g. Make dinner higher protein, or replace lunch with something quicker"
        )

        request_to_process = selected_quick or user_request

        if request_to_process:
            st.session_state.chat_messages.append(
                {"role": "user", "content": request_to_process}
            )

            try:
                with st.spinner("Refining your meal plan..."):
                    raw_result = refine_meal_plan(
                        profile,
                        context,
                        recipe_candidates,
                        st.session_state.meal_plan,
                        request_to_process,
                    )
                    updated_plan = verify_and_apply_changes(
                        raw_result,
                        profile,
                        recipes,
                        foods,
                        st.session_state.meal_plan,
                    )
                    st.session_state.meal_plan = updated_plan

                    assistant_message = raw_result.get(
                        "assistant_message",
                        "I updated the plan where possible.",
                    )
                    if not raw_result.get("changes"):
                        assistant_message += (
                            " I couldn't make that change using the current recipe catalogue."
                        )

                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": assistant_message}
                    )
                    st.rerun()

            except Exception as exc:
                error_message = f"I couldn't apply that change safely: {exc}"
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": error_message}
                )
                st.error(error_message)

if catalogue_errors:
    with st.expander("⚠️ Data catalogue mismatch detected", expanded=True):
        st.error(
            "Some recipes reference ingredients that are missing from the deployed "
            "`data/foods.csv`. Replace the entire `data` folder with the one from the "
            "NutriPilot Phase 4 Fixed ZIP and redeploy."
        )
        for recipe_id, missing_foods in catalogue_errors.items():
            st.write(f"**{recipe_id}:** {', '.join(missing_foods)}")

st.caption("NutriPilot is a meal-planning prototype, not medical or dietary advice.")
