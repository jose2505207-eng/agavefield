# Agave Field Copilot — Setup & Handoff

This is the checklist to take the app from the local demo to **Supabase (DB +
photo storage) + Telegram**, and (optionally) a **Vercel** deployment of the API.

- The **API** (FastAPI) is the part that can be deployed (Vercel / Render / Railway).
- The **Streamlit dashboard** is a long-running app — run it locally or on
  Streamlit Community Cloud (it does **not** run on Vercel). See `DEPLOY_VERCEL.md`.
- With Supabase Storage configured, photo links work from anywhere (no tunnel needed).

---

## ✅ What I need you to send back

Copy the template below, fill it in, and paste it back to me. I'll wire `.env`
(local) and the Vercel env vars, then set the Telegram webhook to your deployment.

```
# --- Supabase database ---
SUPABASE_DB_URL = postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres
# (use the "Session pooler" string from Project Settings → Database; include the password)
RAN_SCHEMA_SQL = yes / no        # did you paste supabase_schema.sql into the SQL Editor and run it?

# --- Supabase Storage (photos) ---
STORAGE_BUCKET        = agave           # the public bucket name you created
STORAGE_ACCESS_KEY    = <S3 access key id>
STORAGE_SECRET_KEY    = <S3 secret access key>
STORAGE_ENDPOINT      = https://<ref>.supabase.co/storage/v1/s3
STORAGE_REGION        = <project region, e.g. us-east-1>
STORAGE_PUBLIC_BASE   = https://<ref>.supabase.co/storage/v1/object/public
BUCKET_IS_PUBLIC      = yes / no

# --- Telegram --- (token already shared; keep it secret)
# nothing more needed from you here

# --- Vision model (OPTIONAL — leave blank to keep the offline stub) ---
VISION_API_KEY  =
VISION_BASE_URL = https://api.openai.com/v1
VISION_MODEL    = gpt-4o-mini

# --- After you deploy to Vercel ---
VERCEL_URL = https://<your-deployment>.vercel.app    # so I can set the Telegram webhook
```

> 🔒 These are secrets. They go into `.env` (git-ignored) and Vercel's encrypted
> env vars — never committed to the public repo.

---

## Step 1 — Create the database in Supabase

1. Supabase dashboard → your project → **SQL Editor** → **New query**.
2. Open **`supabase_schema.sql`** from this repo, copy **everything**, paste it in,
   and click **Run**. It creates all 13 tables + indexes (and an optional demo
   farm/lots near Tequila). It's idempotent — safe to re-run.
3. Confirm in **Table Editor** that tables like `agave_passports`,
   `field_observations`, `tasks`, `alerts` exist.

> The app would also auto-create tables on startup, but running the SQL first is
> cleaner for a serverless deploy (no DDL on cold start) and lets you inspect the
> schema up front.

## Step 2 — Get the database connection string

Project Settings → **Database** → *Connection string* → use the **Session pooler**
value (IPv4-friendly, port **5432**):
```
postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres
```
I'll append `?sslmode=require` when configuring it. (Avoid the *transaction*
pooler on 6543 — it breaks prepared statements with SQLAlchemy.)

## Step 3 — Create the photo storage bucket + keys

1. **Storage** → **New bucket** → name it `agave` → mark it **Public**.
2. **Storage → Settings → S3 access keys** → **New access key** → copy the
   **access key id**, **secret**, **endpoint**, and **region**.
3. The public URL base is `https://<ref>.supabase.co/storage/v1/object/public`.

(The code is already Supabase-Storage-ready: `STORAGE_PROVIDER=s3` plus the
`STORAGE_*` values above. See `app/integrations/storage_client.py`.)

## Step 4 — Telegram

Your bot **@Ageve0_bot** token is already shared. Once the API has a stable public
URL (Vercel, or the local cloudflared tunnel), I'll register the webhook:
```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=<PUBLIC_URL>/webhooks/telegram&secret_token=<SECRET>
```

## Step 5 — Run it

- **Local (full app incl. dashboard):** see `README.md` → "Run locally". With your
  Supabase values in `.env`, the API uses Supabase Postgres + Storage.
- **Deploy the API:** follow **`DEPLOY_VERCEL.md`**.

---

## Quick local run recap
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# put your Supabase + Telegram values in .env (copy from .env.example)
uvicorn app.main:app --reload --port 8000          # API + /docs
API_BASE_URL=http://localhost:8000 streamlit run dashboard/app.py   # dashboard :8501
```


---

## ✅ Provided values — configured (kept out of this public file)

Your Supabase connection string, S3 keys, region, endpoint, and public URL base
were received and stored locally in **`.env`** (the running app) and **`.env.vercel`**
(for the Vercel dashboard). Both files are git-ignored and never committed.

- DB: Supabase session pooler (`aws-1-us-east-1.pooler.supabase.com:5432`, ref `sqpsztuoshpmuiajuyok`) — **connected, schema applied**.
- Storage: bucket `agave` (public) — **validated**.
- Telegram: `@Ageve0_bot` — webhook live.

> Do not paste live secrets into this tracked file — use `.env` / `.env.vercel`.
