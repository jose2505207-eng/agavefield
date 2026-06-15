"""Vercel serverless entrypoint.

Vercel's Python runtime serves the ASGI object named ``app`` found in files
under /api. We simply re-export the FastAPI app; all routing is handled by the
rewrite in vercel.json (everything -> /api/index).

NOTE: Vercel hosts the API only. The Streamlit dashboard is a long-running
server and cannot run on Vercel — see DEPLOY_VERCEL.md for hosting options.
"""
from app.main import app  # noqa: F401  (re-exported for the Vercel runtime)
