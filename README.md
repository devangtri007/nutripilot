# 🥗 NutriPilot

**AI-powered local nutrition copilot**

NutriPilot is a personalized meal-planning application designed to recommend practical food choices based on:

- User nutrition goals
- Dietary preferences
- Allergies and foods to avoid
- Location
- Local and seasonal produce
- Current weather conditions

The project started as a simple Streamlit fruit/nutrition demo and is being upgraded incrementally into a product-oriented AI application.

---

## Current Status

### Phase 1 — User Profile ✅

The current version establishes the user's nutrition profile.

It collects:

- **Country**
- **State / Region**
- **City**
- **Primary nutrition goal**
- **Dietary preference**
- **Allergies / foods to avoid**
- **Meals to plan**

The profile is stored temporarily in **Streamlit session state**.

No external API or database is required for Phase 1.

---

## Planned Product Flow

```text
User Profile
     ↓
Location
     ↓
Season + Weather
     ↓
Local & Seasonal Produce
     ↓
Nutrition Constraints
     ↓
AI Meal Planner
     ↓
Breakfast / Lunch / Dinner / Snacks
     ↓
Personalized Explanation
     ↓
Conversational Refinement
```

### Planned phases

#### Phase 1 — Personalized Profile
Collect and store user preferences and location.

#### Phase 2 — Nutrition & Local Food Data
Build the food/nutrition data layer and identify local/seasonal ingredients.

#### Phase 3 — Season & Weather Context
Automatically derive season from location/date and integrate live weather information.

#### Phase 4 — AI Meal Recommendation
Use an LLM to generate personalized meal plans from structured food and nutrition data.

#### Phase 5 — Conversational Refinement
Allow users to modify recommendations naturally:

> "Make dinner higher in protein."

> "I don't have paneer."

> "Give me a cheaper breakfast."

#### Phase 6 — Evaluation & Product Analytics
Evaluate recommendation quality, constraint handling, hallucinations, personalization and consistency.

---

## Tech Stack

### Current
- Python
- Streamlit
- Streamlit Session State

### Planned
- OpenAI API / LLMs
- Nutrition and food datasets
- Weather API
- Snowflake
- Pandas
- REST APIs

---

## Running Locally

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd <your-repository-folder>
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the application

```bash
streamlit run streamlit_app.py
```

The application will open in your browser.

---

## Phase 1 Product Decisions

### Why session state instead of Snowflake?

The user profile is currently only needed during an active session. Persisting it in a database at this stage would add infrastructure before there is a clear product requirement for accounts, history or saved meal plans.

Snowflake can be reintroduced when NutriPilot needs persistent data such as:

- Saved meals
- User history
- Food catalogue
- Recommendation logs
- Evaluation data

### Why not ask for season manually?

Season can eventually be inferred from:

```text
Location + Current Date
```

This creates a cleaner experience and reduces unnecessary user input.

### Why not use AI yet?

Phase 1 deliberately focuses on getting the **user context and product flow** right before introducing an LLM.

The AI layer will later operate on structured context rather than trying to infer everything from a free-form prompt.

---

## Safety & Scope

NutriPilot is intended as a **meal discovery and planning tool**, not a medical diagnosis or treatment system.

Recommendations should be based on available nutrition data and user-provided preferences. Future versions should clearly distinguish estimated nutritional information from medical or professional dietary advice.

---

## Project Evolution

### Original application

The original project was a Streamlit-based healthy diner application featuring:

- Fruit selection
- Fruit nutrition data
- Fruityvice API integration
- Snowflake data retrieval
- Snowflake fruit insertion

### NutriPilot

The upgraded product evolves this into a personalized nutrition experience:

> **From "What fruit do you want?" to "What should you eat today, given who you are and where you live?"**
