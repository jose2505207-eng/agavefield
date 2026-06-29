import { NextRequest, NextResponse } from "next/server";

// Logout: revoke the session server-side (authoritative kill-switch), then drop
// the httpOnly cookie. We forward the session token as a Bearer so the backend
// can mark its jti revoked — a leaked copy of the token stops working too.
const BASE =
  process.env.API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://agavefield-nu.vercel.app";
const API_KEY = process.env.API_KEY || "";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const token = req.cookies.get("af_session")?.value;
  if (token) {
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
    if (API_KEY) headers["X-API-Key"] = API_KEY;
    try {
      await fetch(`${BASE}/api/auth/logout`, { method: "POST", headers, cache: "no-store" });
    } catch {
      // Best-effort: even if revocation can't be reached, still clear the cookie
      // below so the browser session ends. The token expires on its own too.
    }
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set("af_session", "", {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0,
  });
  return res;
}
