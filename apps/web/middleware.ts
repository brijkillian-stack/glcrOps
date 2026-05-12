/**
 * ZDS Forge — Route protection middleware (Edge Runtime).
 *
 * Access rules
 * ────────────
 * /login/**        public — no auth required
 * /view/**         any authenticated user (all roles)
 * everything else  full access only (graves_ops_super | sudo_admin)
 *
 * Unauthenticated users  →  /login?next=<path>
 * Restricted role, wrong path  →  /view/today  (+ flash cookie zds_access_denied)
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const FULL_ACCESS_ROLES = new Set(["graves_ops_super", "sudo_admin"]);

function hasFullAccess(role: string | null | undefined): boolean {
  return !!role && FULL_ACCESS_ROLES.has(role);
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // ── 1. Public paths — always pass through ────────────────────────────────
  if (pathname.startsWith("/login")) {
    return NextResponse.next();
  }

  // ── 2. Read session cookies ───────────────────────────────────────────────
  const loggedIn = request.cookies.get("zds_logged_in")?.value === "1";
  const role     = request.cookies.get("zds_role")?.value ?? null;

  // ── 3. Not authenticated → login ─────────────────────────────────────────
  if (!loggedIn) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  // ── 4. Viewer paths — all authenticated roles welcome ────────────────────
  if (pathname.startsWith("/view")) {
    return NextResponse.next();
  }

  // ── 5. All other paths — full access required ─────────────────────────────
  if (!hasFullAccess(role)) {
    const url = new URL("/view/today", request.url);
    const res = NextResponse.redirect(url);
    // Flash cookie: the viewer page reads it once, shows the banner, then clears it.
    res.cookies.set("zds_access_denied", "1", {
      path:     "/",
      maxAge:   30,       // 30 seconds — enough for one redirect + page load
      sameSite: "strict",
      httpOnly: false,    // must be readable by client JS
    });
    return res;
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Run on all paths EXCEPT:
     *   _next/static   — static build assets
     *   _next/image    — image optimization API
     *   favicon.ico    — browser favicon request
     *   api/forge/**   — backend proxy (never requires frontend auth)
     */
    "/((?!_next/static|_next/image|favicon\\.ico|api/forge).*)",
  ],
};
