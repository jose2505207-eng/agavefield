import { NextRequest, NextResponse } from "next/server";

// Route guard for the admin UI. Unauthenticated visitors are redirected to
// /login. Public surfaces (login, the token-based worker completion page, the
// API proxy and Next route handlers) are always allowed. Real enforcement of
// permissions happens server-side (signed session + backend demo guard); this
// is the UX gate.
const PUBLIC_PREFIXES = [
  "/login",
  "/complete", // token-based worker page — must stay public
  "/api/", // Next route handlers (login/logout)
  "/proxy/", // backend proxy
  "/_next/",
  "/favicon",
];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const hasSession = Boolean(req.cookies.get("af_session")?.value);

  if (pathname === "/login") {
    return hasSession
      ? NextResponse.redirect(new URL("/", req.url))
      : NextResponse.next();
  }

  if (PUBLIC_PREFIXES.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  if (!hasSession) {
    const url = new URL("/login", req.url);
    if (pathname !== "/") url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
