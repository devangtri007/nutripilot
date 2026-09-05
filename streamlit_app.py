import streamlit as st

st.set_page_config(
    page_title="NutriPilot",
    page_icon="🥗",
    layout="centered",
)

# -----------------------------
# Session state
# -----------------------------
if "user_profile" not in st.session_state:
    st.session_state.user_profile = None

# -----------------------------
# Header
# -----------------------------
st.title("🥗 NutriPilot")
st.subheader("Your local, seasonal nutrition copilot.")

st.write(
    "Tell us a little about yourself and where you live. "
    "NutriPilot will use this profile in later phases to create "
    "personalized meal recommendations."
)

st.divider()

# -----------------------------
# Profile form
# -----------------------------
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

# -----------------------------
# Validation + save
# -----------------------------
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
        st.error(
            "Please provide: " + ", ".join(missing) + "."
        )
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

# -----------------------------
# Profile summary
# -----------------------------
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
        st.write(
            f"**Meals:** {', '.join(profile['meals'])}"
        )
        st.write(
            f"**Avoid:** {profile['restrictions'] or 'Nothing specified'}"
        )

    st.info(
        "Coming next: NutriPilot will use your location, "
        "season, local produce and weather to personalize "
        "your meal recommendations."
    )

    if st.button("Reset Profile", use_container_width=True):
        st.session_state.user_profile = None
        st.rerun()

# -----------------------------
# Phase indicator
# -----------------------------
st.divider()
st.caption("NutriPilot · Phase 1 — Personalized Profile")
