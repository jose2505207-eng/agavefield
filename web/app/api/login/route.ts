import { NextRequest, NextResponse } from "next/server";

// Server-side login: validate credentials against the FastAPI backend, then
// store the returned session token in an httpOnly cookie so it never reaches
// client JS. The browser only ever talks to this same-origin handler.
const BASE =
  process.env.API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000"; // dev default; set API_BASE_URL to the real backend in prod
const API_KEY = process.env.API_KEY || "";
const TTL_HOURS = Number(process.env.SESSION_TTL_HOURS || "12");

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  let body: { username?: string; password?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request" }, { status: 400 });
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (API_KEY) headers["X-API-Key"] = API_KEY;

  let upstream: Response;
  try {
    upstream = await fetch(`${BASE}/api/auth/login`, {
      method: "POST",
      headers,
      body: JSON.stringify({ username: body.username, password: body.password }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "Authentication service unreachable" }, { status: 502 });
  }

  const data = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    return NextResponse.json(
      { detail: data?.detail || "Invalid username or password" },
      { status: upstream.status },
    );
  }

  const res = NextResponse.json({ user: data.user });
  res.cookies.set("af_session", data.token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: TTL_HOURS * 3600,
  });
  return res;
}
