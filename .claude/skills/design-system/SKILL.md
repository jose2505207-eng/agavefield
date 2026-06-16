---
name: design-system
description: Make the Agave Field UI feel premium, clean, field-oriented, enterprise-ready, and mobile-friendly. Use when creating or improving the Streamlit dashboard or the mobile task page.
---

# design-system

## When to use
Building or improving any UI: dashboard sections, catalog screens, review queue,
timeline, carbon charts, evidence gallery, or the mobile worker task page.

## Instructions
- Target an **agricultural operations command center** feel, not a generic admin panel:
  clear KPIs first, then drill-downs; consistent iconography (🌱 activity, 🧪 product,
  📍 GPS, 🌧️ rain, ♻️/CO₂ carbon, 🧾 audit).
- Streamlit dashboard: use `st.metric` rows for KPIs, `st.columns` for layout, tables for
  detail, and charts (`st.bar_chart`/`st.line_chart`) for carbon/weather trends.
- Always implement the four states: **loading** (spinner/caption), **empty**
  ("No records yet / data not available"), **error** (clear message, never a stack trace),
  **success** (toast/confirmation).
- Mobile task page (`/work-orders/complete/{token}`): single-column, large tap targets,
  camera capture (`<input type=file accept=image/* capture=environment>`), geolocation
  prompt, minimal text, no admin nav.

## Constraints
- Never fabricate data to fill a chart. Show "data not available".
- Keep within Streamlit + plain HTML/JS for the mobile page; no new JS framework.

## Output
UI that is responsive, state-complete, and consistent with existing dashboard patterns.
