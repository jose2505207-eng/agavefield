import { NextRequest, NextResponse } from "next/server";

// Server-side proxy to the FastAPI backend. Injects the RBAC API key from a
// server-only env var so it never reaches the browser; client code calls
// same-origin `/proxy/api/...` (no CORS, key-safe). Works in open mode too.
const BASE =
  process.env.API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://agavefield-nu.vercel.app";
const API_KEY = process.env.API_KEY || "";

export const dynamic = "force-dynamic";

async function forward(req: NextRequest, path: string[]) {
  const url = `${BASE}/${path.join("/")}${req.nextUrl.search}`;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (API_KEY) headers["X-API-Key"] = API_KEY;

  const init: RequestInit = { method: req.method, headers, cache: "no-store" };
  if (!["GET", "HEAD"].includes(req.method)) {
    init.body = await req.text();
  }

  try {
    const res = await fetch(url, init);
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") || "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Upstream API unreachable" }, { status: 502 });
  }
}

type Ctx = { params: { path: string[] } };
export const GET = (req: NextRequest, { params }: Ctx) => forward(req, params.path);
export const POST = (req: NextRequest, { params }: Ctx) => forward(req, params.path);
export const PATCH = (req: NextRequest, { params }: Ctx) => forward(req, params.path);
export const DELETE = (req: NextRequest, { params }: Ctx) => forward(req, params.path);
