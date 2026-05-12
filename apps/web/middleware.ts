// Role-based access control disabled — all routes open.
// Re-enable by restoring the full middleware from git history (feat: Phase 2 commit).
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(_request: NextRequest) {
  return NextResponse.next();
}
