---
name: qa-ship
description: Final pre-ship quality gate for Agave Field — run tests/compile/import checks, verify edge cases and env docs, scan for secrets, and summarize risks. Use before declaring work done.
---

# qa-ship

## When to use
At the end of any change, before reporting completion.

## Instructions
- **Run checks (Python stack):**
  - `python -m pytest -q -W ignore::DeprecationWarning` (suite must stay green)
  - `python -m py_compile <changed files>` and `python -c "import app.main"` (import OK)
  - There is no TS/eslint step — this is Python; skip JS lint/build.
- **Edge cases:** empty data, missing GPS/weather (must not break submission), missing
  carbon inputs (`missing_data`), expired/invalid token, deactivate-when-referenced.
- **Secrets scan before any commit:** `git diff --cached | grep -E 'sk-|password|token
  patterns'` must be empty; confirm `.env`/`.env.vercel` are git-ignored and only
  `.env.example` (placeholders) is tracked.
- **Env docs:** every new variable is in `.env.example` with a placeholder.
- **Prod parity:** real Supabase DB + S3 storage configured; no local-FS storage in prod;
  weather failure degrades gracefully.

## Constraints
- Do not `git push` unless explicitly asked. Do not mark done if tests fail — report the
  failure with output instead.

## Output
A concise report: checks run, what passed/failed, edge cases verified, risks/assumptions,
and the exact next command + next Claude prompt.
