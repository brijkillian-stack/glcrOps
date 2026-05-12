/**
 * Temporary diagnostic endpoint — DELETE after debugging.
 * Visit /api/debug-auth to see what auth state the server sees.
 */
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const cookies = {
    zds_logged_in: request.cookies.get("zds_logged_in")?.value ?? "(not set)",
    zds_role:      request.cookies.get("zds_role")?.value      ?? "(not set)",
    zds_access_denied: request.cookies.get("zds_access_denied")?.value ?? "(not set)",
  };

  const allCookies = Object.fromEntries(
    [...request.cookies].map(([k, v]) => [k, v.value])
  );

  return NextResponse.json({
    cookies_zds:   cookies,
    all_cookies:   allCookies,
    middleware_sees: {
      logged_in:  cookies.zds_logged_in === "1",
      role:       cookies.zds_role,
      has_full_access: ["graves_ops_super", "sudo_admin"].includes(cookies.zds_role),
    },
  }, { status: 200 });
}
