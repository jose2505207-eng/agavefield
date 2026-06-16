# Deploying the API to Vercel

Vercel hosts the **FastAPI API** as a Python serverless function. This repo
already contains the two files Vercel needs:

- **`api/index.py`** — re-exports the ASGI `app` (Vercel serves `app` from `/api/*`).
- **`vercel.json`** — rewrites every path to `/api/index`.

> ⚠️ **Read "Limitations" at the bottom before relying on this in production.**
> The Streamlit **dashboard cannot run on Vercel** (it's a long-running server),
> and serverless **background photo processing can be cut off**. For the full
> always-on system, a long-running host (Render / Railway / Fly.io) is a better fit.

---

## 1. Import settings (the screen you're on)

| Field | Value |
|---|---|
| **Framework Preset** | **Other** (recommended). `vercel.json` controls routing, so the FastAPI preset isn't required and "Other" avoids preset overrides. |
| **Root Directory** | `./` |
| **Build Command** | leave **empty** (Vercel installs `requirements.txt` automatically) |
| **Output Directory** | leave **empty** (N/A for Python serverless functions) |
| **Install Command** | leave default (`pip install -r requirements.txt`) |

Then expand **Environment Variables** and add the ones below before clicking **Deploy**.

## 2. Environment variables (add in Vercel → Project → Settings → Environment Variables)

| Key | Value |
|---|---|
| `DATABASE_URL` | `postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require` |
| `STORAGE_PROVIDER` | `s3` |
| `STORAGE_BUCKET` | `agave` |
| `STORAGE_ACCESS_KEY` | *(your Supabase S3 access key — in `.env.vercel`)* |
| `STORAGE_SECRET_KEY` | *(your Supabase S3 secret — in `.env.vercel`)* |
| `STORAGE_ENDPOINT` | `https://<ref>.supabase.co/storage/v1/s3` |
| `STORAGE_REGION` | *(your project region, e.g. `us-east-1`)* |
| `STORAGE_PUBLIC_BASE` | `https://<ref>.supabase.co/storage/v1/object/public` |
| `TELEGRAM_BOT_TOKEN` | *(your BotFather token — in `.env.vercel`)* |
| `TELEGRAM_WEBHOOK_SECRET` | *(any random string)* |
| `PUBLIC_BASE_URL` | `https://<your-deployment>.vercel.app` *(https://agavefield-nu.vercel.app/)* |
| `WEATHER_PROVIDER` | `auto` |
| `VISION_API_KEY` | *(optional — blank keeps the offline stub)* |
| `VISION_BASE_URL` | `https://api.openai.com/v1` *(only if using a real model)* |
| `VISION_MODEL` | `gpt-4o-mini` *(only if using a real model)* |

> `STORAGE_PROVIDER=s3` is **required** on Vercel — the local-disk option doesn't
> persist on serverless. That's why Supabase Storage is part of this setup.

## 3. After the first deploy
1. Copy your deployment URL (`https://<deployment>.vercel.app`).
2. Set `PUBLIC_BASE_URL` to it (Env Vars) and **redeploy** so image links resolve.
3. Point Telegram at the permanent URL (no more tunnel):
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     --data-urlencode "url=https://<deployment>.vercel.app/webhooks/telegram" \
     --data-urlencode "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
   ```
4. Test: `curl https://<deployment>.vercel.app/health` → `telegram_enabled: true`,
   `storage_provider: s3`.

## 4. Hosting the dashboard (not on Vercel)
- **Locally:** `API_BASE_URL=https://<deployment>.vercel.app streamlit run dashboard/app.py`
- **Streamlit Community Cloud:** point it at this repo, `dashboard/app.py`, and set
  `API_BASE_URL` to your Vercel URL in its secrets.

---

## Limitations (please read)
1. **Dashboard is not deployable to Vercel** — it's a persistent server. Use local
   or Streamlit Cloud (above).
2. **Background photo processing.** The Telegram webhook returns `200` immediately
   and processes the photo in a FastAPI `BackgroundTask`
   (`app/api/telegram_routes.py`). On serverless the instance can be frozen/killed
   right after the response, so that work may not finish reliably. Options:
   - For a smooth demo, keep using the **cloudflared tunnel** to your local server
     (already working), **or**
   - Deploy to a **long-running host** (Render/Railway/Fly.io) where background
     tasks complete, **or**
   - Ask me to make the webhook process **synchronously** (small code change) so it
     finishes inside the request — acceptable for low volume.
3. **Bundle size.** `requirements.txt` includes `streamlit`/`pandas` (only needed by
   the dashboard). If the Vercel build hits the serverless size limit, tell me and
   I'll split out a slim API-only requirements set for the deploy.
4. **Cold starts** run the app's `init_db()` (a no-op once the SQL has created the
   tables) — first request after idle is a bit slower. Normal for serverless.

> TL;DR: Vercel is great for a **stable webhook URL + the dashboard's data API**.
> If you want the *whole* magical flow (photo → analysis → tasks → alerts) rock-solid,
> Render/Railway is the lower-friction target — say the word and I'll add a config.
