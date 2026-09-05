import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="NutriPilot",
    page_icon="🥗",
    layout="centered",
)

FOOD_DATA_PATH = "data/foods.csv"

@st.cache_data
def load_food_data():
    return pd.read_csv(FOOD_DATA_PATH)

foods = load_food_data()

if "user_profile" not in st.session_state:
    st.session_state.user_profile = None

st.title("🥗 NutriPilot")
st.subheader("Your local, seasonal nutrition copilot.")

st.write(
    "Build your nutrition profile and explore foods that match your "
    "diet, goals, location and future seasonal recommendations."
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
        st.success("Your NutriPilot profile is ready!")

if st.session_state.user_profile:
    profile = st.session_state.user_profile

    st.divider()
    st.header("Your Profile")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Location", f"{profile['city']}, {profile['region']}")
        st.write(f"**Country:** {profile['country']}")
        st.write(f"**Diet:** {profile['diet']}")

    with col2:
        st.write(f"**Goal:** {profile['goal']}")
        st.write(f"**Meals:** {', '.join(profile['meals'])}")
        st.write(
            f"**Avoid:** {profile['restrictions'] or 'Nothing specified'}"
        )

    st.info(
        "Phase 2 adds the structured food layer. "
        "Recommendations are not generated yet."
    )

st.divider()

st.header("🥕 Explore the Food Database")
st.caption(
    "Starter dataset for product development. "
    "Nutrition values are shown per 100 g."
)

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

st.caption(
    f"Showing {len(filtered)} of {len(foods)} foods."
)

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
