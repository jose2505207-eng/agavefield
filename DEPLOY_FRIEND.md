# Run your own copy (own Telegram bot + hosted dashboard)

This guide lets a second person run **their own isolated instance** of Agave Field
Copilot: their **own Telegram bot**, their **own Supabase** (database + photos), their
**own API** (Vercel), and their **own dashboard** (Streamlit Community Cloud).

Nothing is shared with anyone else — each instance has its own database, so each
dashboard only shows that person's data. There is **no shared login / multi-tenancy**;
isolation comes from each person having their own deployment + secrets.

```
 Telegram bot (yours)
        │ webhook
        ▼
 API on Vercel ──► your Supabase Postgres (data)
        │          your Supabase Storage  (photos)
        │          OpenRouter (vision, your key)
        ▼
 Dashboard on Streamlit Cloud ──HTTP(API_BASE_URL)──► your API
```

> ⏱️ ~20–30 minutes. You need: a GitHub account, a Supabase account, a Vercel account,
> a Streamlit Community Cloud account, and an OpenRouter account (free).

---

## 1. Get the code
Use the existing repo `jose2505207-eng/agavefield` directly (Vercel + Streamlit read it
from GitHub), or **Fork** it to your own GitHub so you control it. Either works.

## 2. Supabase — your own project (database + photos)
1. https://supabase.com/dashboard → **New project** (save the DB password, note the region).
2. **SQL Editor → New query** → open `supabase_schema.sql` from the repo → paste all → **Run**.
   Creates all 13 tables (+ optional demo lots). Idempotent.
3. **Storage → New bucket** → name `agave` → mark **Public**.
4. **Storage → Settings → S3 access keys → New access key** → copy the **access key id**,
   **secret**, **endpoint** (`https://<ref>.supabase.co/storage/v1/s3`), and **region**.
5. **Settings → Database → Connection string → Session pooler** (port 5432):
   `postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres`
   (append `?sslmode=require`).

## 3. Telegram — your own bot
Message **@BotFather** → `/newbot` → choose a name + username → copy the **token**.

## 4. OpenRouter — your own vision key
https://openrouter.ai → create an API key (`sk-or-v1-...`). Use a vision model id like
`openai/gpt-4o-mini` (cheap, supports JSON output).

## 5. Deploy the API on Vercel
1. Vercel → **New Project** → import your GitHub repo.
2. **Framework Preset = Other**. Root `./`. Leave Build/Output empty.
   (`vercel.json` + `api/index.py` in the repo handle the FastAPI routing.)
3. **Environment Variables** (see `DEPLOY_VERCEL.md` for the full table) — use **your** values:
   ```
   DATABASE_URL=postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
   STORAGE_PROVIDER=s3
   STORAGE_BUCKET=agave
   STORAGE_ACCESS_KEY=<your s3 key id>
   STORAGE_SECRET_KEY=<your s3 secret>
   STORAGE_ENDPOINT=https://<ref>.supabase.co/storage/v1/s3
   STORAGE_REGION=<region>
   STORAGE_PUBLIC_BASE=https://<ref>.supabase.co/storage/v1/object/public
   TELEGRAM_BOT_TOKEN=<your bot token>
   TELEGRAM_WEBHOOK_SECRET=<any random string>
   TELEGRAM_WEBHOOK_SYNC=true        # IMPORTANT on Vercel (serverless)
   VISION_PROVIDER=openai_compatible
   VISION_API_KEY=<your openrouter key>
   VISION_BASE_URL=https://openrouter.ai/api/v1
   VISION_MODEL=openai/gpt-4o-mini
   WEATHER_PROVIDER=auto
   APP_ENV=production
   ```
4. **Deploy.** Then copy your URL, set `PUBLIC_BASE_URL=https://<you>.vercel.app`, and
   **redeploy**.
5. Check: `https://<you>.vercel.app/health` → `telegram_enabled:true, storage_provider:s3`.

> `TELEGRAM_WEBHOOK_SYNC=true` makes the bot finish analyzing each photo **inside** the
> request, so serverless doesn't cut it off. The repo's `vercel.json` raises the function
> `maxDuration` to 60s to allow for the vision call.

## 6. Point your bot at your API
```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
  --data-urlencode "url=https://<you>.vercel.app/webhooks/telegram" \
  --data-urlencode "secret_token=<YOUR_TELEGRAM_WEBHOOK_SECRET>"
```

## 7. Deploy the dashboard on Streamlit Community Cloud
1. https://share.streamlit.io → **Create app** → pick your repo + branch `main`.
2. **Main file path:** `dashboard/app.py`
   (uses `dashboard/requirements.txt` — slim: streamlit/pandas/requests).
3. **Advanced settings → Secrets:**
   ```
   API_BASE_URL="https://<you>.vercel.app"
   ```
4. **Deploy.** You get a public dashboard URL (e.g. `https://<app>.streamlit.app`) to open
   in any browser.

> The dashboard calls your API server-side over HTTP, so there are no CORS issues, and it
> never needs your database/storage secrets — only the `API_BASE_URL`.

## 8. Verify end-to-end
1. Send a **photo** to your bot in Telegram → it replies with a diagnosis + buttons.
2. Supabase **Table Editor** → a new row in `field_observations`; **Storage** → image in
   `agave`.
3. Open your Streamlit dashboard → the photo + observation appear.

---

## Security
- Every person uses **their own** secrets (bot token, Supabase, OpenRouter key) in **their
  own** Vercel + Streamlit settings. Do **not** reuse someone else's keys.
- Never commit secrets. `.env` and `.env.vercel` are git-ignored; put secrets only in the
  hosting platforms' env/secret settings.

## Notes & limits
- **Dashboard host:** Streamlit Community Cloud (the dashboard is a long-running Streamlit
  server and cannot run on Vercel). Render/Railway also work if preferred.
- **Free-tier sleeps:** Streamlit Cloud apps sleep when idle and wake on visit; Vercel cold
  starts add a second to the first request. Fine for field/demo use.
- **Reliability:** with `TELEGRAM_WEBHOOK_SYNC=true`, photo processing completes within the
  Vercel function. For very heavy models, prefer a long-running host (Render/Railway).
