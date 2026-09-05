import json
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from openai import OpenAI

st.set_page_config(
    page_title="NutriPilot",
    page_icon="🥗",
    layout="centered",
)

FOOD_DATA_PATH = "data/foods.csv"
LOCATION_DATA_PATH = "data/locations.csv"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


@st.cache_data
def load_food_data():
    return pd.read_csv(FOOD_DATA_PATH)


@st.cache_data
def load_location_data():
    return pd.read_csv(LOCATION_DATA_PATH)


@st.cache_data(ttl=1800)
def validate_location(country, region, city):
    """Validate a catalog location against Open-Meteo geocoding."""
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
        result
        for result in results
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


def diet_allows(food_row, diet):
    food_diet = str(food_row["diet"]).lower()
    diet = diet.lower()

    if diet == "vegan":
        return food_diet == "vegan"

    if diet == "vegetarian":
        return food_diet in {"vegan", "vegetarian"}

    if diet == "eggetarian":
        return food_diet in {"vegan", "vegetarian", "eggetarian"}

    return True


def build_candidates(foods, profile, season):
    candidates = foods.copy()

    candidates = candidates[
        candidates.apply(
            lambda row: diet_allows(row, profile["diet"]),
            axis=1,
        )
    ]

    season_mask = (
        candidates["season"].str.contains(
            season,
            case=False,
            na=False,
        )
        | candidates["season"].str.contains("All", case=False, na=False)
    )

    seasonal = candidates[season_mask]
    if len(seasonal) >= 8:
        candidates = seasonal

    restrictions = [
        item.strip().lower()
        for item in profile["restrictions"].split(",")
        if item.strip()
    ]

    if restrictions:
        candidates = candidates[
            ~candidates["food"].str.lower().apply(
                lambda food: any(item in food for item in restrictions)
            )
        ]

    return candidates


def generate_meal_plan(profile, location_context, candidates):
    if "OPENAI_API_KEY" not in st.secrets:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Add it to Streamlit secrets."
        )

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    candidate_records = candidates[
        [
            "food",
            "category",
            "calories_kcal",
            "protein_g",
            "carbs_g",
            "fat_g",
            "fiber_g",
            "meal_types",
        ]
    ].to_dict(orient="records")

    meals = profile["meals"]

    system_prompt = """
You are NutriPilot, a nutrition meal-planning assistant.

Your job is to create practical meal ideas using ONLY foods from the
provided candidate catalogue.

Important rules:
1. Never invent nutrition values.
2. Never invent foods outside the candidate catalogue.
3. Respect the user's diet and explicitly listed foods to avoid.
4. Prefer seasonal foods when candidates are seasonal.
5. Consider weather context as a meal-style preference, not a medical rule.
6. Do not make medical claims.
7. Return valid JSON only.
8. Quantities must be in grams.
9. Use 2-5 ingredients per meal.
10. Keep recommendations realistic for a normal home kitchen.

For each requested meal return:
- meal
- name
- ingredients: [{food, grams}]
- why
- tags

The "why" should explain the recommendation using the user's goal,
season, weather and available candidate foods without making unsupported
health claims.
"""

    user_prompt = {
        "user_profile": profile,
        "location_context": location_context,
        "requested_meals": meals,
        "candidate_foods": candidate_records,
        "output_schema": {
            "meals": [
                {
                    "meal": "Breakfast",
                    "name": "Meal name",
                    "ingredients": [
                        {"food": "Oats", "grams": 50}
                    ],
                    "why": "Short explanation.",
                    "tags": ["seasonal", "high-protein"],
                }
            ]
        },
    }

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(user_prompt),
            },
        ],
    )

    content = response.choices[0].message.content
    return json.loads(content)


def calculate_meal_nutrition(meal, foods):
    lookup = foods.set_index("food")
    totals = {
        "calories_kcal": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
    }

    verified_ingredients = []

    for ingredient in meal["ingredients"]:
        food = ingredient["food"]
        grams = float(ingredient["grams"])

        if food not in lookup.index:
            raise ValueError(
                f"AI returned an unsupported food: {food}"
            )

        row = lookup.loc[food]
        factor = grams / 100

        for field in totals:
            totals[field] += float(row[field]) * factor

        verified_ingredients.append(
            {"food": food, "grams": grams}
        )

    meal["ingredients"] = verified_ingredients
    meal["nutrition"] = {
        key: round(value, 1)
        for key, value in totals.items()
    }

    return meal


foods = load_food_data()
locations = load_location_data()

if "user_profile" not in st.session_state:
    st.session_state.user_profile = None

if "location_context" not in st.session_state:
    st.session_state.location_context = None

if "meal_plan" not in st.session_state:
    st.session_state.meal_plan = None


st.title("🥗 NutriPilot")
st.subheader("Your local, seasonal nutrition copilot.")

st.write(
    "Get meal recommendations shaped by your goals, diet, location, "
    "season and current weather."
)

st.divider()

st.header("👤 Your Profile")

countries = sorted(locations["country"].unique().tolist())
country = st.selectbox("Country", countries)

region_options = sorted(
    locations.loc[
        locations["country"] == country,
        "region",
    ].unique().tolist()
)
region = st.selectbox("State / Region", region_options)

city_options = sorted(
    locations.loc[
        (locations["country"] == country)
        & (locations["region"] == region),
        "city",
    ].unique().tolist()
)
city = st.selectbox("City", city_options)

goal = st.selectbox(
    "Primary goal",
    [
        "General wellness",
        "Weight management",
        "Muscle gain",
        "High protein",
        "Better energy",
    ],
)

diet = st.selectbox(
    "Diet",
    [
        "Vegetarian",
        "Vegan",
        "Eggetarian",
        "Non-vegetarian",
    ],
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

if st.button(
    "Set Profile & Load Local Context",
    type="primary",
    use_container_width=True,
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
                st.error(
                    "This location could not be resolved by Open-Meteo."
                )
                st.stop()

            weather = get_current_weather(
                location["latitude"],
                location["longitude"],
                location.get("timezone", "auto"),
            )

            current = weather["current"]
            local_time = datetime.fromisoformat(current["time"])

            season = get_season(
                local_time.month,
                location["latitude"],
                country,
            )

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
                    "apparent_temperature_c": current.get(
                        "apparent_temperature"
                    ),
                    "humidity_pct": current.get(
                        "relative_humidity_2m"
                    ),
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
        st.metric(
            "Feels like",
            f"{weather['apparent_temperature_c']} °C",
        )

    with cols[2]:
        st.metric("Humidity", f"{weather['humidity_pct']}%")

    with cols[3]:
        st.metric("Wind", f"{weather['wind_kmh']} km/h")

    st.success(
        f"**{weather['condition']} · {context['season']}**"
    )

    st.write(
        f"**Location:** {location['name']}, "
        f"{location['region']}, {location['country']}"
    )

    candidates = build_candidates(
        foods,
        profile,
        context["season"],
    )

    st.caption(
        f"{len(candidates)} food candidates match the current "
        "diet, restrictions and seasonal context."
    )

    st.divider()
    st.header("🤖 AI Meal Planner")

    st.write(
        "NutriPilot will use the structured food catalogue as its "
        "candidate set, then calculate nutrition from the database."
    )

    if st.button(
        "Generate My Meal Plan",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner("Building your personalized meal plan..."):
                raw_plan = generate_meal_plan(
                    profile,
                    context,
                    candidates,
                )

                verified_plan = []

                for meal in raw_plan.get("meals", []):
                    verified_plan.append(
                        calculate_meal_nutrition(
                            meal,
                            foods,
                        )
                    )

                st.session_state.meal_plan = verified_plan

        except Exception as exc:
            st.error(f"Could not generate the meal plan: {exc}")

    if st.session_state.meal_plan:
        st.divider()
        st.header("🍽️ Your NutriPilot Plan")

        for meal in st.session_state.meal_plan:
            st.subheader(
                f"{meal.get('meal', 'Meal')} — {meal.get('name', '')}"
            )

            ingredient_text = " · ".join(
                f"{item['food']} ({item['grams']} g)"
                for item in meal["ingredients"]
            )

            st.write(f"**Ingredients:** {ingredient_text}")

            nutrition = meal["nutrition"]

            metric_cols = st.columns(4)

            with metric_cols[0]:
                st.metric(
                    "Calories",
                    f"{nutrition['calories_kcal']:.0f} kcal",
                )

            with metric_cols[1]:
                st.metric(
                    "Protein",
                    f"{nutrition['protein_g']:.1f} g",
                )

            with metric_cols[2]:
                st.metric(
                    "Carbs",
                    f"{nutrition['carbs_g']:.1f} g",
                )

            with metric_cols[3]:
                st.metric(
                    "Fiber",
                    f"{nutrition['fiber_g']:.1f} g",
                )

            st.write(f"**Why this meal?** {meal.get('why', '')}")

            if meal.get("tags"):
                st.caption(" · ".join(meal["tags"]))

            st.divider()

st.caption(
    "NutriPilot is a meal-planning prototype, not medical or dietary advice."
)
