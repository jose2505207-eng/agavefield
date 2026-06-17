# Go-Live Runbook — Agave Field

Increments ①–⑦ are built, tested, and deployed. This is the checklist to make the
system **secure and actually usable** in production. Steps marked �, 🖥️, 📦 require
your accounts (Vercel / Streamlit / your data) — the code is ready for all of them.

Check readiness anytime: `GET /api/system/status` (or the dashboard **Settings / Status**
page) → `go_live_ready: true` when all green.

## 1. 🔒 Enforce RBAC (close the open admin endpoints)
RBAC is currently **open** in production (no keys set), so anyone with the URL can call
admin endpoints. To lock it down:
1. Open **`.env.vercel`** (git-ignored, in the project root). It now contains generated
   `ADMIN_API_KEY`, `AGRONOMIST_API_KEY`, `REVIEWER_API_KEY`, and `API_KEY` (= admin key).
2. **Vercel → project → Settings → Environment Variables:** add those four keys
   (Production), then **Redeploy**.
3. **Streamlit Cloud → app → Settings → Secrets:** set `API_KEY="<the admin key>"` so the
   dashboard keeps full access.
4. Verify: `GET /api/system/status` → `"rbac_enforced": true`; calling an admin endpoint
   without `X-API-Key` now returns 401.

> Field workers are unaffected — the mobile completion page + photo upload stay public via
> the per-work-order token.

## 2. 🖥️ Deploy the dashboard (Streamlit Community Cloud)
1. **share.streamlit.io → Create app** → repo `jose2505207-eng/agavefield`, branch `main`,
   main file **`dashboard/app.py`**.
2. **Advanced → Secrets:**
   ```
   API_BASE_URL = "https://agavefield-nu.vercel.app"
   API_KEY = "<your admin key from .env.vercel>"
   ```
3. Deploy → you get the dashboard URL (Work Orders, Review Queue, Carbon, Timeline,
   Evidence, Audit, Settings/Status).

## 3. 📦 Load your real catalogs (no invented data)
Carbon factors must be **your** values. Two options:
- **CSV import:** fill `scripts/catalog_products.template.csv` and
  `scripts/catalog_activities.template.csv`, then run against the production DB:
  ```bash
  DATABASE_URL="<supabase session-pooler url>" \
    python -m scripts.seed_catalog --products my_products.csv --activities my_activities.csv
  ```
- **API:** `POST /api/products` and `POST /api/activities` (with `X-API-Key`).

## 4. ✉️ Configure email for real work-order links
Default is `console` (dev — logs only). For real delivery set in Vercel:
`EMAIL_PROVIDER=smtp` (+ `SMTP_*`) — or `sendgrid`/`resend` (+ key). Confirm
`status.email.live == true`.

## 5. 🧪 Run one real end-to-end test
1. Add an **assignee** (`POST /api/assignees`, your email).
2. **Create a work order** (Dashboard → Work Orders → Generate, or `POST /api/work-orders`).
3. **Send** it → check the email link arrives.
4. Open the link **on a phone** → capture a photo, allow location, add a note, submit.
5. **Review Queue** → approve. Confirm it appears in **Timeline** and **Carbon Dashboard**,
   with the photo in **Evidence Gallery** and entries in the **Audit Log**.

## 6. ✅ Confirm go-live
`GET /api/system/status` → `go_live_ready: true` (DB connected, storage + email configured,
≥1 product, ≥1 activity). The Settings/Status dashboard page shows the same checklist.

---

### Security reminders
- Secrets live only in `.env` / `.env.vercel` (git-ignored) and platform env settings —
  never in tracked files or code.
- Rotate the bot token / DB password / S3 + API keys if they were ever shared in chat.
- `ENABLE_AI_IMAGE_ANALYSIS` stays `false` (no LLM image analysis in the MVP).
