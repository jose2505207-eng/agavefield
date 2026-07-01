# Agave Field — Production Readiness Audit

**Date:** 2026-06-30
**Branch/commit:** `main` @ `daabfab` · tag `v0.2.0`
**Verdict:** Code is production-ready. Remaining work is **configuration + deploy steps** on your accounts (Vercel / Supabase / email). Nothing below requires new code.

---

## ✅ Verified green

| Check | Result |
|---|---|
| Test suite (`pytest -q`) | **103 passed** |
| Frontend build (`web/`, `next build`) | **Clean** — 13 routes compiled |
| DB schema migrations | **Single clean Alembic head** `b2c3d4e5f6a7` |
| Secrets management | `.env.vercel` git-ignored; `.env.example` placeholders only |
| Prod auth signing key (`SECRET_KEY`) | Set (strong random) |
| RBAC API keys | Set → admin endpoints enforce `X-API-Key` |
| Storage (Supabase S3) | Configured |
| Session revocation / login throttle / auth audit log | Implemented + tested |
| Demo account read-only (server-enforced) | Implemented + tested |
| Work-order → execution → review → carbon → audit flow | Implemented + tested end-to-end |

---

## 🔴 Blocking gaps — fix before real production use

These are all **environment variables / deploy actions**, not code changes.

### 1. No real admin login exists in production
`AUTH_ADMIN_USERNAME` / `AUTH_ADMIN_PASSWORD` are **not set** in `.env.vercel`, so the only
account seeded in prod is the **read-only DEMO** account. You cannot create or send work
orders from the web admin UI until a real admin exists.

**Fix (Vercel → API project → Settings → Environment Variables → Production):**
```
AUTH_ADMIN_USERNAME = <your admin username>
AUTH_ADMIN_PASSWORD = <a strong password>
```
Then **Redeploy**. On the next cold start `seed_users()` creates the real admin.
Verify by logging in at the web app with those credentials (not DEMO/DEMO).

- Docs: https://vercel.com/docs/projects/environment-variables

### 2. Confirm DB migrations are applied to the production Supabase database
Login session revocation relies on the `app_sessions` table from migration
`b2c3d4e5f6a7`. The app's best-effort `create_all()` at startup is **not** the source of
truth (Alembic is). If the table is missing, login can fail with a 500.

**Fix — run once against the production DB** (use the Supabase **session pooler** URL from
`.env.vercel`):
```bash
source .venv/bin/activate
DATABASE_URL="<supabase-session-pooler-url-from-.env.vercel>" python -m alembic upgrade head
```
Verify: `python -m alembic current` prints `b2c3d4e5f6a7 (head)`.

- Alembic upgrade: https://alembic.sqlalchemy.org/en/latest/tutorial.html#running-our-first-migration
- Supabase connection strings (use the pooler): https://supabase.com/docs/guides/database/connecting-to-postgres

### 3. Work-order link email is console-only (links are logged, not delivered)
`EMAIL_PROVIDER` is unset → defaults to `console`, so "Send work order" **logs** the link
instead of emailing the worker. The whole link-delivery flow is inert in prod.

**Fix (Vercel → API project env) — pick one provider:**
```
# Option A — Resend (simplest)
EMAIL_PROVIDER = resend
RESEND_API_KEY = <key>

# Option B — SendGrid
EMAIL_PROVIDER = sendgrid
SENDGRID_API_KEY = <key>

# Option C — SMTP
EMAIL_PROVIDER = smtp
SMTP_HOST = ...
SMTP_PORT = 587
SMTP_USERNAME = ...
SMTP_PASSWORD = ...
SMTP_FROM_EMAIL = ...
```
Verify: `GET /api/system/status` → `email.live == true`.

- Resend: https://resend.com/docs/introduction · SMTP: https://resend.com/docs/send-with-smtp
- SendGrid: https://www.twilio.com/docs/sendgrid/for-developers/sending-email/api-getting-started

### 4. Load your real carbon catalog (no invented data)
`go_live_ready` requires ≥1 product and ≥1 activity. Carbon factors **must be your own
values** — the app never fabricates them.

**Fix — CSV import against prod** (templates in `scripts/`):
```bash
DATABASE_URL="<supabase-pooler-url>" python -m scripts.seed_catalog \
  --products my_products.csv --activities my_activities.csv
```
Or via API: `POST /api/products` and `POST /api/activities` with `X-API-Key`.

---

## 🟡 Hardening — strongly recommended, not strictly blocking

### 5. Lock down CORS
`CORS_ALLOW_ORIGINS` is unset → defaults to `*` in production. It functions today (worker
uploads use no credentials), but should be restricted.

**Fix (Vercel → API project env):**
```
CORS_ALLOW_ORIGINS = https://<your-web-frontend-domain>,https://<dashboard-domain>
```
⚠️ **Critical:** the worker completion page calls the API **cross-origin**, so the web
frontend's domain **must** be in this list or worker photo upload + submit will break.

- FastAPI CORS: https://fastapi.tiangolo.com/tutorial/cors/

### 6. Pin the API base URL on the web frontend project
The worker page falls back to a hard-coded `https://agavefield-nu.vercel.app`. Set it
explicitly so it stays correct if the API domain ever changes.

**Fix (Vercel → web/frontend project env):**
```
NEXT_PUBLIC_API_BASE_URL = https://<your-api-domain>
```

### 7. `go_live_ready` over-reports email readiness
The status check treats `console` email as "configured", so `go_live_ready` can be `true`
while emails are not actually delivered. Always also check `email.live == true` before you
trust the link-delivery flow. (Behavioral note — no fix required.)

---

## 🔐 Security — rotate exposed credentials before go-live

During this audit the contents of `.env.vercel` were read into the assistant session
(DB password, Supabase S3 access/secret keys, Telegram bot token, `SECRET_KEY`, and the
three RBAC API keys). Per your own `GO_LIVE.md` ("rotate anything ever shared in chat"),
rotate these before launch and update Vercel + Streamlit secrets:

- **Supabase DB password:** Project → Settings → Database → Reset database password
- **Supabase S3 / storage keys:** Project → Settings → Storage → S3 access keys → regenerate
- **Telegram bot token:** BotFather → `/revoke` → set new token
- **`SECRET_KEY`:** generate `python -c "import secrets; print(secrets.token_urlsafe(32))"`
  (note: rotating this logs out all current admin sessions — expected)
- **RBAC keys** (`ADMIN_API_KEY` etc.): regenerate and update Vercel + the Streamlit `API_KEY` secret

---

## Final go-live checklist

- [ ] 1. Set `AUTH_ADMIN_USERNAME` / `AUTH_ADMIN_PASSWORD` (Vercel API project) + redeploy
- [ ] 2. `alembic upgrade head` against prod Supabase → confirm head `b2c3d4e5f6a7`
- [ ] 3. Set `EMAIL_PROVIDER` + provider key → confirm `email.live == true`
- [ ] 4. Import your real product + activity carbon catalog
- [ ] 5. Set `CORS_ALLOW_ORIGINS` (must include the web frontend domain)
- [ ] 6. Set `NEXT_PUBLIC_API_BASE_URL` on the web frontend project
- [ ] 7. Rotate all credentials that appeared in chat; update Vercel + Streamlit
- [ ] 8. Run one real end-to-end test (create WO → email link → complete on phone → approve)
- [ ] 9. `GET /api/system/status` → `go_live_ready: true`
