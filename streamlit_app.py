
import json
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from openai import OpenAI

APP_VERSION = "7.1"
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


@st.cache_data
def food_name_set(foods):
    return frozenset(foods["food"].astype(str).str.strip())


@st.cache_data
def recipe_name_to_id(recipes):
    return {
        str(row["name"]).strip().lower(): str(row["recipe_id"])
        for _, row in recipes.iterrows()
    }


def recipe_contains(recipe, ingredient_terms):
    ingredients = str(recipe.get("ingredients", "")).lower()
    return any(term.lower() in ingredients for term in ingredient_terms)


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
            if any(x["food"] not in food_lookup.index for x in ingredients):
                continue
            rows.append(recipe.to_dict())

    return pd.DataFrame(rows)


def validate_catalogue_integrity(foods, recipes):
    """Fail early if recipes reference foods missing from the deployed catalogue."""
    food_names = set(food_name_set(foods))
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
    # Keep the catalogue identity explicitly on every verified meal. This is
    # important because the conversational refinement layer uses recipe_id to
    # reconstruct and safely validate the current plan.
    result["recipe_id"] = str(recipe.get("recipe_id", ""))
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
    # Preserve recipe_id while scaling portions so later refinement can always
    # identify the catalogue recipe.
    result["recipe_id"] = str(recipe.get("recipe_id", ""))
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


def refine_multi_day_plan(
    profile,
    location_context,
    recipe_candidates,
    recipes,
    current_plan,
    user_request,
):
    candidate_records = [
        recipe_record_for_prompt(row)
        for row in recipe_candidates.to_dict(orient="records")
    ]

    # Normalize the current plan before sending it to the refinement model.
    # This also makes refinement compatible with a plan created by an older
    # app version that may not have persisted recipe_id on each meal.
    recipe_lookup_by_name = recipe_name_to_id(recipes)

    current_records = []
    for day in plan_days(current_plan):
        normalized_meals = []
        for meal in day.get("meals", []):
            recipe_id = meal.get("recipe_id")
            if not recipe_id:
                recipe_id = recipe_lookup_by_name.get(
                    str(meal.get("name", "")).strip().lower()
                )
            if not recipe_id:
                raise ValueError(
                    f"Current plan meal '{meal.get('name', 'unknown')}' is missing a valid recipe_id. "
                    "Generate the plan again before refining it."
                )

            normalized_meals.append({
                "meal": meal.get("meal_type"),
                "recipe_id": str(recipe_id),
                "name": meal.get("name", ""),
                "nutrition": meal.get("nutrition", {}),
                "total_time_min": int(meal.get("total_time_min", 0)),
            })

        current_records.append({
            "day": day.get("day"),
            "meals": normalized_meals,
            "totals": day.get("totals", nutrition_totals(day.get("meals", []))),
        })

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
    return call_json_model(
        system_prompt,
        {
            "user_profile": profile,
            "location_context": location_context,
            "user_request": user_request,
            "current_plan": current_records,
            "candidate_recipes": candidate_records,
        },
    )


def apply_plan_changes(raw_result, profile, recipes, foods, current_plan):
    """Validate and apply AI recipe replacements without trusting model output."""
    if not isinstance(raw_result, dict):
        raise ValueError("The refinement response was not valid JSON.")

    lookup = recipes.set_index("recipe_id", drop=False)
    result = []
    for day in plan_days(current_plan):
        result.append({
            "day": int(day["day"]),
            "meals": list(day.get("meals", [])),
            "totals": dict(day.get("totals", nutrition_totals(day.get("meals", [])))),
        })

    changes = raw_result.get("changes", [])
    if changes is None:
        changes = []
    if not isinstance(changes, list):
        raise ValueError("The refinement response contained invalid changes.")

    seen_changes = set()
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("The refinement response contained an invalid change.")

        day_number = change.get("day")
        meal_type = change.get("meal")
        recipe_id = change.get("recipe_id")
        if day_number is None or meal_type is None or recipe_id is None:
            raise ValueError("A proposed change is missing day, meal, or recipe_id.")

        try:
            day_number = int(day_number)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid day in refinement: {day_number}")

        recipe_id = str(recipe_id).strip()
        change_key = (day_number, meal_type)
        if change_key in seen_changes:
            raise ValueError(f"Duplicate refinement for Day {day_number} {meal_type}.")
        seen_changes.add(change_key)

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

        verified = calculate_recipe_nutrition(recipe, foods)
        verified["why"] = str(change.get("reason", "Updated to match your request."))
        verified["tags"] = ["refined"]
        verified["serving_multiplier"] = 1.0

        replaced = False
        for i, old_meal in enumerate(day["meals"]):
            if old_meal.get("meal_type") == meal_type:
                day["meals"][i] = verified
                replaced = True
                break
        if not replaced:
            raise ValueError(f"Could not find {meal_type} on Day {day_number}.")

        day["totals"] = nutrition_totals(day["meals"])

    return result


def validate_refinement_request(result, user_request, recipes, profile):
    """Deterministic post-checks for common refinement constraints."""
    request = user_request.lower()
    lookup = recipes.set_index("recipe_id", drop=False)

    if "no rice" in request or "without rice" in request:
        for meal in all_plan_meals(result):
            recipe = lookup.loc[str(meal["recipe_id"])].to_dict()
            if recipe_contains(recipe, ["rice"]):
                raise ValueError("The refined plan still contains rice. Please try again.")

    import re
    time_match = re.search(r"(?:under|below|less than)\s*(\d+)\s*minutes?", request)
    if time_match:
        limit = int(time_match.group(1))
        for meal in all_plan_meals(result):
            if float(meal.get("total_time_min", 0)) >= limit:
                raise ValueError(
                    f"The refined plan contains a meal taking {meal.get('total_time_min')} minutes; "
                    f"the requested limit is under {limit} minutes."
                )

    return result


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
if "plan_settings" not in st.session_state:
    st.session_state.plan_settings = None

st.title("🥗 NutriPilot")
st.caption(f"v{APP_VERSION} · AI meal planning with catalogue validation")
st.subheader("Your local, seasonal nutrition copilot.")
st.write("Meal recommendations shaped by your goals, diet, location, season and current weather.")

st.divider()
st.header("👤 Your Profile")

countries = sorted(locations["country"].unique().tolist())
country = st.selectbox("Country", countries, key="profile_country")

region_options = sorted(
    locations.loc[locations["country"] == country, "region"].unique().tolist()
)
region = st.selectbox("State / Region", region_options, key="profile_region")

city_options = sorted(
    locations.loc[
        (locations["country"] == country) & (locations["region"] == region),
        "city",
    ].unique().tolist()
)
city = st.selectbox("City", city_options, key="profile_city")

goal = st.selectbox(
    "Primary goal",
    ["General wellness", "Weight management", "Muscle gain", "High protein", "Better energy"],
    key="profile_goal",
)

diet = st.selectbox(
    "Diet",
    ["Vegetarian", "Vegan", "Eggetarian", "Non-vegetarian"],
    key="profile_diet",
)

restrictions = st.text_input(
    "Allergies or foods to avoid",
    placeholder="e.g., peanuts, mushrooms, lactose",
    key="profile_restrictions",
)

meals = st.multiselect(
    "Meals to plan",
    ["Breakfast", "Lunch", "Dinner", "Snacks"],
    default=["Breakfast", "Lunch", "Dinner"],
    key="profile_meals",
)

st.subheader("📅 Planning Horizon & Targets")

plan_days_count = st.selectbox(
    "Plan length",
    [3, 5, 7],
    index=0,
    format_func=lambda x: f"{x} days",
    key="plan_days_count",
)

target_mode = st.selectbox(
    "Daily nutrition target",
    [
        "No target — prioritize variety",
        "1,600 kcal",
        "2,000 kcal",
        "2,400 kcal",
        "Custom",
    ],
    key="daily_calorie_mode",
)

if target_mode == "Custom":
    calorie_target = st.number_input(
        "Daily calories (your chosen target)",
        min_value=800,
        max_value=5000,
        value=2000,
        step=50,
        key="custom_calorie_target",
    )
elif target_mode.startswith("1,600"):
    calorie_target = 1600
elif target_mode.startswith("2,000"):
    calorie_target = 2000
elif target_mode.startswith("2,400"):
    calorie_target = 2400
else:
    calorie_target = None

protein_mode = st.selectbox(
    "Daily protein target",
    [
        "No target",
        "60 g",
        "90 g",
        "120 g",
        "Custom",
    ],
    key="daily_protein_mode",
)

if protein_mode == "Custom":
    protein_target = st.number_input(
        "Daily protein (your chosen target, g)",
        min_value=20,
        max_value=300,
        value=90,
        step=5,
        key="custom_protein_target",
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
portion_adjustment = 0.25 if portion_flexibility.startswith("Standard") else 0.15

st.caption(
    "Targets are planning preferences you choose; NutriPilot does not prescribe "
    "medical or therapeutic nutrition targets."
)

if st.button("Set Profile & Load Local Context", type="primary", use_container_width=True, key="set_profile_button"):

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
            st.session_state.plan_settings = {
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
        "Build a multi-day plan from the validated recipe catalogue and optimize "
        "serving sizes against your selected targets."
    )

    settings = st.session_state.plan_settings or {
        "days": plan_days_count,
        "calorie_target": calorie_target,
        "protein_target": protein_target,
        "portion_adjustment": portion_adjustment,
    }

    if st.button(
        "Generate My Multi-Day Plan",
        type="primary",
        use_container_width=True,
        key="generate_plan_button",
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

        except Exception as exc:
            st.error(f"Could not generate the meal plan: {exc}")

    if st.session_state.meal_plan:
        plan = st.session_state.meal_plan

        st.divider()
        st.header("📊 Plan Overview")

        daily_rows = [
            {
                "Day": f"Day {day['day']}",
                "Calories (kcal)": day["totals"]["calories_kcal"],
                "Protein (g)": day["totals"]["protein_g"],
                "Carbs (g)": day["totals"]["carbs_g"],
                "Fiber (g)": day["totals"]["fiber_g"],
            }
            for day in plan_days(plan)
        ]

        st.dataframe(
            pd.DataFrame(daily_rows),
            use_container_width=True,
            hide_index=True,
        )

        target_bits = []
        if settings["calorie_target"]:
            target_bits.append(f"{settings['calorie_target']} kcal/day")
        if settings["protein_target"]:
            target_bits.append(f"{settings['protein_target']} g protein/day")
        if target_bits:
            st.caption("Targets: " + " · ".join(target_bits))

        st.info(
            "Portion optimization changes the complete recipe serving size within "
            "your selected range. Ingredient ratios remain unchanged."
        )

        for day in plan_days(plan):
            with st.expander(
                f"Day {day['day']} · "
                f"{day['totals']['calories_kcal']:.0f} kcal · "
                f"{day['totals']['protein_g']:.1f} g protein",
                expanded=True,
            ):
                for meal in day["meals"]:
                    st.subheader(
                        f"{meal['meal_type']} — {meal['name']}"
                    )
                    st.caption(
                        f"{meal['total_time_min']:.0f} min · "
                        f"{meal['difficulty']} · {meal['cuisine']} · "
                        f"{meal.get('serving_multiplier', 1.0):.2f}× serving"
                    )

                    ingredient_text = " · ".join(
                        f"{item['food']} ({item['grams']:.0f} g)"
                        for item in meal["parsed_ingredients"]
                    )
                    st.write(f"**Ingredients:** {ingredient_text}")

                    nutrition = meal["nutrition"]
                    cols = st.columns(4)
                    with cols[0]:
                        st.metric("Calories", f"{nutrition['calories_kcal']:.0f} kcal")
                    with cols[1]:
                        st.metric("Protein", f"{nutrition['protein_g']:.1f} g")
                    with cols[2]:
                        st.metric("Carbs", f"{nutrition['carbs_g']:.1f} g")
                    with cols[3]:
                        st.metric("Fiber", f"{nutrition['fiber_g']:.1f} g")

                    st.write(f"**Why this meal?** {meal.get('why', '')}")

        st.divider()
        st.header("🛒 Shopping List")

        shopping = build_shopping_list(plan)
        st.dataframe(shopping, use_container_width=True, hide_index=True)

        st.download_button(
            "Download Shopping List (CSV)",
            data=shopping.to_csv(index=False).encode("utf-8"),
            file_name="nutripilot_shopping_list.csv",
            mime="text/csv",
            use_container_width=True,
        )

        st.divider()
        st.header("💬 Refine Your Plan")
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
                if st.button(label, use_container_width=True, key=f"quick_refine_{idx}"):
                    selected_quick = label

        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        user_request = st.chat_input(
            "e.g. Replace Day 2 lunch with something quicker",
            key="refinement_chat_input",
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
                        recipes,
                        st.session_state.meal_plan,
                        request_to_process,
                    )

                    updated = apply_plan_changes(
                        raw_result,
                        profile,
                        recipes,
                        foods,
                        st.session_state.meal_plan,
                    )
                    updated = validate_refinement_request(
                        updated, request_to_process, recipes, profile
                    )

                    # Phase 7: re-optimize after conversational recipe replacement.
                    updated = optimize_plan_portions(
                        updated,
                        foods,
                        settings["calorie_target"],
                        settings["protein_target"],
                        settings["portion_adjustment"],
                    )

                    st.session_state.meal_plan = updated

                    assistant_message = raw_result.get(
                        "assistant_message",
                        "I updated the plan where possible.",
                    )
                    if not raw_result.get("changes"):
                        assistant_message += (
                            " I couldn't make that change using the current recipe catalogue."
                        )

                    st.session_state.chat_messages.append(
                        {
                            "role": "assistant",
                            "content": assistant_message,
                        }
                    )
                    st.rerun()

            except Exception as exc:
                error_message = f"I couldn't apply that change safely: {exc}"
                st.session_state.chat_messages.append(
                    {
                        "role": "assistant",
                        "content": error_message,
                    }
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

st.caption(
    f"NutriPilot v{APP_VERSION} · Meal-planning prototype. Nutrition targets are user-selected "
    "planning preferences, not medical or dietary prescriptions."
)
