---
name: frontend-builder
description: Build dashboard pages, forms, the mobile task view, photo upload flows, review screens, catalog editors, and timeline views for Agave Field. Use when implementing user-facing screens.
---

# frontend-builder

## When to use
Implementing any screen: Streamlit dashboard sections or the standalone mobile
completion page served by FastAPI.

## Instructions
- **Dashboard = Streamlit** (`dashboard/app.py`). Add a page by extending the sidebar
  radio + an `elif page == "..."` block. It is decoupled — it ONLY calls the API over
  HTTP via `API_BASE_URL` (`api_get/api_post/api_patch` helpers). Never import `app.*`
  into the dashboard.
- **Mobile task page = server-rendered HTML** returned by a FastAPI route
  (`HTMLResponse`), self-contained (inline CSS + vanilla JS). It must: validate the
  token via the API, render the checklist, use `navigator.geolocation.getCurrentPosition`,
  capture photos with `<input type=file capture=environment>`, POST multipart to the
  submit endpoint, and show success/error.
- Forms: validate on the client for UX, but the server (Pydantic) is the source of truth.
- Reuse existing helpers and SEVERITY/event iconography already in `dashboard/app.py`.

## Constraints
- No React/Vue/Next. Streamlit + vanilla HTML/JS only.
- Always add loading/empty/error/success states.

## Output
Working screens wired to real API endpoints, with all four UI states handled.
