# Agave Field — Web (Next.js frontend)

Premium frontend for the Agave Field operations platform. Consumes the existing
FastAPI backend (`/api/*`); the Python API + Supabase + Streamlit admin are
unchanged. Phase 1 = app shell + premium Dashboard with demo-mode fallback.

## Run locally
```bash
cd web
npm install
cp .env.example .env.local   # optional; defaults to the deployed API
npm run dev                  # http://localhost:3000
```

- `NEXT_PUBLIC_API_BASE_URL` — backend base URL (default `https://agavefield-nu.vercel.app`).
  When the API is empty/unreachable the dashboard shows realistic **demo data**
  (with a "Demo data" badge) and switches to live data automatically when present.

## Build
```bash
npm run build
```

## Stack
Next.js (App Router) · TypeScript · Tailwind CSS · lucide-react. Earthy agave
design system (light-first). 9 product sections; Dashboard is built, the rest are
purposeful placeholders for later phases.

## Deploy
Separate Vercel project, **Root Directory = `web/`** (the repo root keeps deploying
the FastAPI API). Set `NEXT_PUBLIC_API_BASE_URL` (and later a server-only `API_KEY`).
