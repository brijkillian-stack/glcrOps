/**
 * ZDS Forge — Role definitions and auth helpers.
 *
 * Full-access roles (entire application):
 *   graves_ops_super — Grave shift zone deployment manager
 *   sudo_admin       — System administrator
 *
 * Restricted roles (limited to /view/* only):
 *   days_ops_super, swings_ops_super, utility_ops_super,
 *   ops_super, ops_manager, ops_director, admin
 */

export type UserRole =
  | "graves_ops_super"
  | "days_ops_super"
  | "swings_ops_super"
  | "utility_ops_super"
  | "ops_super"
  | "ops_manager"
  | "ops_director"
  | "admin"
  | "sudo_admin";

const FULL_ACCESS_ROLES = new Set<UserRole>(["graves_ops_super", "sudo_admin"]);

/** Returns true only for roles with full application access. */
export function hasFullAccess(role: string | null | undefined): boolean {
  if (!role) return false;
  return FULL_ACCESS_ROLES.has(role as UserRole);
}

/** Human-readable label for a role slug. */
export const ROLE_LABELS: Record<UserRole, string> = {
  graves_ops_super:  "Graves Ops Super",
  days_ops_super:    "Days Ops Super",
  swings_ops_super:  "Swings Ops Super",
  utility_ops_super: "Utility Ops Super",
  ops_super:         "Ops Super",
  ops_manager:       "Ops Manager",
  ops_director:      "Ops Director",
  admin:             "Admin",
  sudo_admin:        "Sudo Admin",
};

// ── Cookie names ──────────────────────────────────────────────────────────────

export const ROLE_COOKIE          = "zds_role";
export const SESSION_COOKIE       = "zds_logged_in";
export const ACCESS_DENIED_COOKIE = "zds_access_denied";

const MAX_AGE_14D = 60 * 60 * 24 * 14; // 14 days in seconds

// ── Client-side helpers ───────────────────────────────────────────────────────

/**
 * Persist role + session cookies after a successful login.
 * Call this in the browser only (after supabase.auth.signInWithPassword).
 */
export function setAuthCookies(role: UserRole, stayLoggedIn = true): void {
  const maxAge = stayLoggedIn ? MAX_AGE_14D : undefined;
  const secure = typeof location !== "undefined" && location.protocol === "https:";
  const base   = `; path=/; SameSite=Strict${secure ? "; Secure" : ""}`;
  const age    = maxAge !== undefined ? `; max-age=${maxAge}` : "";
  document.cookie = `${ROLE_COOKIE}=${encodeURIComponent(role)}${base}${age}`;
  document.cookie = `${SESSION_COOKIE}=1${base}${age}`;
}

/** Clear auth cookies (call on sign-out). */
export function clearAuthCookies(): void {
  document.cookie = `${ROLE_COOKIE}=; path=/; max-age=0`;
  document.cookie = `${SESSION_COOKIE}=; path=/; max-age=0`;
}

/** Read the current role from browser cookies. Returns null if not set. */
export function getRoleFromCookie(): UserRole | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)zds_role=([^;]+)/);
  return match ? (decodeURIComponent(match[1]) as UserRole) : null;
}

/**
 * Check whether the access-denied flash cookie is set.
 * If it is, clears it immediately so it only fires once and returns true.
 */
export function consumeAccessDeniedCookie(): boolean {
  if (typeof document === "undefined") return false;
  const match = document.cookie.match(/(?:^|;\s*)zds_access_denied=([^;]+)/);
  if (match) {
    document.cookie = `${ACCESS_DENIED_COOKIE}=; path=/; max-age=0`;
    return true;
  }
  return false;
}
