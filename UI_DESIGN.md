# NutriPilot Premium UI Refactor

## Fixes

1. **High-contrast CTAs** — all Streamlit action buttons use Crisp Carrot (`#f96015`) with Cream (`#f3e8cc`) foreground text. Disabled controls fall back to the active theme surface/text variables.
2. **Native icons** — action buttons use Streamlit's native `icon=` API with Material Symbols; no raw `_icon_name_` strings are rendered.
3. **Theme compatibility** — the app keeps Streamlit's Light/Dark/System theme switcher. CSS reads Streamlit theme variables for background, surface, text and border values. Light mode uses the requested Cream canvas; Dark mode uses a dark neutral base while preserving the Forest Green and Crisp Carrot brand accents.
4. **Widgets** — selectboxes, text inputs, multiselects, radio buttons and sliders use theme-aware surfaces and Crisp Carrot for focus/active states.
5. **Metrics** — subtle accent-tinted cards, rounded corners and clear label/value hierarchy.
6. **Alerts** — success/info/warning/error components share one flat branded treatment rather than Streamlit's default red/green/yellow palette.
7. **Tables** — dataframe containers use theme-aware surfaces and Forest Green borders; native Streamlit dataframe header/border theme settings are configured in `.streamlit/config.toml`.
8. **Flat layout** — no gradients and no heavy shadows; spacing and radii are consistent and responsive.

## Palette

- Cream: `#f3e8cc`
- Forest Green: `#18542a`
- Crisp Carrot: `#f96015`
- Dark-mode neutral: `#111713` (theme-adaptation exception requested for dark mode)

## Functionality

Only the presentation layer and button icon declarations were changed. Existing profile, weather, recipe catalogue, nutrition calculation, multi-day generation, portion optimization, shopping list and conversational refinement logic remain in the source.
