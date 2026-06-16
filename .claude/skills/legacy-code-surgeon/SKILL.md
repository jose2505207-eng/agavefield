---
name: legacy-code-surgeon
description: Modify the existing Agave Field codebase safely — preserve the stack, avoid rewrites, make small reversible changes. Use whenever touching existing files.
---

# legacy-code-surgeon

## When to use
Any time you edit existing code, especially shared modules (`db.py`, `main.py`,
`models/*`, `dashboard/app.py`, `conftest.py`).

## Instructions
- **Inspect before editing:** read the file and its callers; run a quick `grep` for usages.
- **Additive over destructive:** add new modules/columns/routes; don't rewrite working ones.
- Preserve the stack: Python · FastAPI · SQLAlchemy · Pydantic · Streamlit · Supabase.
  No TS/Next/Node/ORM swaps.
- Migrations are additive (`ADD COLUMN IF NOT EXISTS`); never drop/rename columns that
  hold live data.
- When extending a shared file, make the minimal localized edit and keep existing behavior
  intact (e.g., gate new behavior behind a flag like `ENABLE_AI_IMAGE_ANALYSIS`).
- After any change, run `pytest -q` and a compile/import check before declaring done.

## Constraints
- No whole-app rewrites. No deleting important files. No `git push` unless asked.
- If a change is risky, propose it first and explain the blast radius.

## Output
Small, reversible diffs that keep the suite green and the app importable.
