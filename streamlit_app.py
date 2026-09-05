import calendar
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="NutriPilot",
    page_icon="🥗",
    layout="centered",
)

FOOD_DATA_PATH = "data/foods.csv"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


@st.cache_data
def load_food_data():
    return pd.read_csv(FOOD_DATA_PATH)


@st.cache_data(ttl=1800)
def geocode_location(city, region, country):
    """Resolve a user-entered city to coordinates using Open-Meteo."""
    query_parts = [city.strip()]
    if region.strip():
        query_parts.append(region.strip())
    if country.strip():
        query_parts.append(country.strip())

    response = requests.get(
        GEOCODING_URL,
        params={
            "name": ", ".join(query_parts),
            "count": 5,
            "language": "en",
            "format": "json",
        },
        timeout=10,
    )
    response.raise_for_status()

    results = response.json().get("results", [])
    if not results:
        return None

    # Prefer an exact city-name match where possible.
    city_lower = city.strip().lower()
    exact = [
        result
        for result in results
        if result.get("name", "").lower() == city_lower
    ]

    return (exact or results)[0]


@st.cache_data(ttl=900)
def get_current_weather(latitude, longitude, timezone_name="auto"):
    """Fetch current weather conditions for the resolved coordinates."""
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
            "timezone": timezone_name,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_season(month, latitude, country):
    """
    Return a practical season label for food recommendations.

    India uses a simplified culinary season model because monsoon is
    especially relevant to local food availability. Other locations
    use hemisphere-based meteorological-style seasons.
    """
    country_lower = country.strip().lower()

    if country_lower in {"india", "in"}:
        if month in {3, 4, 5}:
            return "Summer"
        if month in {6, 7, 8, 9}:
            return "Monsoon"
        if month in {10, 11}:
            return "Post-monsoon"
        return "Winter"

    if latitude >= 0:
        if month in {3, 4, 5}:
            return "Spring"
        if month in {6, 7, 8}:
            return "Summer"
        if month in {9, 10, 11}:
            return "Autumn"
        return "Winter"

    if month in {3, 4, 5}:
        return "Autumn"
    if month in {6, 7, 8}:
        return "Winter"
    if month in {9, 10, 11}:
        return "Spring"
    return "Summer"


def weather_label(weather_code, temperature, precipitation):
    """Convert weather observations into a simple product context."""
    if weather_code in {95, 96, 99}:
        return "Thunderstorm"
    if weather_code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "Rainy"
    if weather_code in {71, 73, 75, 77, 85, 86}:
        return "Snowy"
    if weather_code in {45, 48}:
        return "Foggy"
    if precipitation and precipitation > 0:
        return "Wet"
    if temperature >= 32:
        return "Hot"
    if temperature <= 12:
        return "Cold"
    return "Mild"


foods = load_food_data()

if "user_profile" not in st.session_state:
    st.session_state.user_profile = None

if "location_context" not in st.session_state:
    st.session_state.location_context = None


st.title("🥗 NutriPilot")
st.subheader("Your local, seasonal nutrition copilot.")

st.write(
    "Build your profile, connect your location to live weather, "
    "and prepare the context NutriPilot will use for personalized meals."
)

st.divider()

st.header("Let's personalize your recommendations")

with st.form("profile_form"):
    st.markdown("### 📍 Where are you based?")

    country = st.text_input(
        "Country",
        placeholder="e.g., India",
    )

    region = st.text_input(
        "State / Region",
        placeholder="e.g., Uttar Pradesh",
    )

    city = st.text_input(
        "City",
        placeholder="e.g., Kanpur",
    )

    st.markdown("### 🎯 What's your primary goal?")

    goal = st.selectbox(
        "Choose one",
        [
            "General wellness",
            "Weight management",
            "Muscle gain",
            "High protein",
            "Better energy",
        ],
    )

    st.markdown("### 🥗 What's your diet?")

    diet = st.selectbox(
        "Choose your diet",
        [
            "Vegetarian",
            "Vegan",
            "Eggetarian",
            "Non-vegetarian",
        ],
    )

    st.markdown("### 🚫 Anything you'd like to avoid?")

    restrictions = st.text_input(
        "Allergies or foods you avoid",
        placeholder="e.g., peanuts, mushrooms, lactose",
    )

    st.markdown("### 🍽️ Which meals should NutriPilot help with?")

    meals = st.multiselect(
        "Select one or more",
        ["Breakfast", "Lunch", "Dinner", "Snacks"],
        default=["Breakfast", "Lunch", "Dinner"],
    )

    submitted = st.form_submit_button(
        "Create My Profile",
        type="primary",
        use_container_width=True,
    )

if submitted:
    missing = []

    if not country.strip():
        missing.append("Country")
    if not region.strip():
        missing.append("State / Region")
    if not city.strip():
        missing.append("City")
    if not meals:
        missing.append("at least one meal")

    if missing:
        st.error("Please provide: " + ", ".join(missing) + ".")
    else:
        st.session_state.user_profile = {
            "country": country.strip(),
            "region": region.strip(),
            "city": city.strip(),
            "goal": goal,
            "diet": diet,
            "restrictions": restrictions.strip(),
            "meals": meals,
        }
        st.session_state.location_context = None
        st.success("Your NutriPilot profile is ready!")

profile = st.session_state.user_profile

if profile:
    st.divider()
    st.header("Your Profile")

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Location",
            f"{profile['city']}, {profile['region']}",
        )
        st.write(f"**Country:** {profile['country']}")
        st.write(f"**Diet:** {profile['diet']}")

    with col2:
        st.write(f"**Goal:** {profile['goal']}")
        st.write(f"**Meals:** {', '.join(profile['meals'])}")
        st.write(
            f"**Avoid:** {profile['restrictions'] or 'Nothing specified'}"
        )

    st.divider()
    st.header("🌦️ Local Context")

    if st.button(
        "Get My Season & Weather",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner("Finding your location and current conditions..."):
                location = geocode_location(
                    profile["city"],
                    profile["region"],
                    profile["country"],
                )

                if not location:
                    st.session_state.location_context = {
                        "error": "Location could not be found."
                    }
                else:
                    weather = get_current_weather(
                        location["latitude"],
                        location["longitude"],
                        location.get("timezone", "auto"),
                    )

                    current = weather.get("current", {})
                    temperature = current.get("temperature_2m")
                    precipitation = current.get("precipitation") or 0
                    weather_code = current.get("weather_code")
                    local_time = current.get("time")

                    local_datetime = (
                        datetime.fromisoformat(local_time)
                        if local_time
                        else datetime.now(timezone.utc)
                    )

                    season = get_season(
                        local_datetime.month,
                        location["latitude"],
                        profile["country"],
                    )

                    st.session_state.location_context = {
                        "location": location,
                        "weather": current,
                        "season": season,
                        "weather_label": weather_label(
                            weather_code,
                            temperature,
                            precipitation,
                        ),
                    }

        except requests.RequestException as exc:
            st.session_state.location_context = {
                "error": (
                    "Weather/location service could not be reached. "
                    f"Details: {exc}"
                )
            }
        except (TypeError, ValueError) as exc:
            st.session_state.location_context = {
                "error": f"Could not process the weather response: {exc}"
            }

    context = st.session_state.location_context

    if context:
        if "error" in context:
            st.error(context["error"])
        else:
            location = context["location"]
            current = context["weather"]

            weather_cols = st.columns(4)

            with weather_cols[0]:
                st.metric(
                    "Temperature",
                    f"{current.get('temperature_2m', '—')} °C",
                )

            with weather_cols[1]:
                st.metric(
                    "Feels like",
                    f"{current.get('apparent_temperature', '—')} °C",
                )

            with weather_cols[2]:
                st.metric(
                    "Humidity",
                    f"{current.get('relative_humidity_2m', '—')}%",
                )

            with weather_cols[3]:
                st.metric(
                    "Wind",
                    f"{current.get('wind_speed_10m', '—')} km/h",
                )

            st.success(
                f"**{context['weather_label']} · {context['season']}**"
            )

            st.write(
                f"**Resolved location:** {location.get('name')}, "
                f"{location.get('admin1', profile['region'])}, "
                f"{location.get('country', profile['country'])}"
            )

            st.caption(
                f"Local time: {current.get('time', 'Unavailable')} · "
                "Weather and season context will feed the recommendation "
                "engine in Phase 4."
            )

st.divider()

st.header("🥕 Explore the Food Database")
st.caption("Nutrition values are shown per 100 g.")

filter_col1, filter_col2 = st.columns(2)

with filter_col1:
    selected_category = st.selectbox(
        "Food category",
        ["All"] + sorted(foods["category"].unique().tolist()),
    )

with filter_col2:
    selected_meal = st.selectbox(
        "Meal suitability",
        ["All", "Breakfast", "Lunch", "Dinner", "Snack"],
    )

filtered = foods.copy()

if selected_category != "All":
    filtered = filtered[filtered["category"] == selected_category]

if selected_meal != "All":
    filtered = filtered[
        filtered["meal_types"].str.contains(
            selected_meal,
            case=False,
            na=False,
        )
    ]

st.dataframe(
    filtered[
        [
            "food",
            "category",
            "calories_kcal",
            "protein_g",
            "carbs_g",
            "fat_g",
            "fiber_g",
            "season",
            "regions",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.caption(f"Showing {len(filtered)} of {len(foods)} foods.")

st.divider()

st.header("🔎 Nutrition Snapshot")

food_name = st.selectbox(
    "Choose a food",
    foods["food"].tolist(),
)

selected_food = foods[foods["food"] == food_name].iloc[0]

metric_cols = st.columns(4)

with metric_cols[0]:
    st.metric("Calories", f"{selected_food['calories_kcal']:.0f} kcal")

with metric_cols[1]:
    st.metric("Protein", f"{selected_food['protein_g']:.1f} g")

with metric_cols[2]:
    st.metric("Carbs", f"{selected_food['carbs_g']:.1f} g")

with metric_cols[3]:
    st.metric("Fiber", f"{selected_food['fiber_g']:.1f} g")

st.write(
    f"**Best suited for:** {selected_food['meal_types']}  \n"
    f"**Season:** {selected_food['season']}  \n"
    f"**Regions:** {selected_food['regions']}"
)

st.caption(
    "NutriPilot is a meal-planning prototype, not medical or dietary advice."
)
