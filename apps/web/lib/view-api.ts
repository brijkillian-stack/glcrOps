/**
 * Published Schedule Viewer — API client.
 *
 * Endpoints (all proxied through Next.js rewrites → /api/forge/*):
 *   GET  /v1/view/night/{date}   → ViewNightMeta
 *   GET  /v1/view/archive        → ViewArchiveEntry[]
 *   POST /v1/view/audit          → 204
 */

const BASE = "/api/forge";

// ── Types ──────────────────────────────────────────────────────────────────

/** Metadata returned when resolving a shift date to its published night. */
export interface ViewNightMeta {
  night_id:    string;
  shift_date:  string;   // "YYYY-MM-DD"
  day_name:    string;   // "Friday" … "Thursday"
  week_id:     string;
  week_label:  string | null;
  week_status: "published" | "archived";
  is_editable: boolean;  // computed server-side with 90-min buffer
}

/** One entry in the archive date-picker list / calendar. */
export interface ViewArchiveEntry {
  night_id:    string;
  shift_date:  string;
  day_name:    string;
  week_id:     string;
  week_label:  string | null;
  week_status: "published" | "archived";
  is_editable: boolean;
}

export interface ViewAuditPayload {
  night_id:     string;
  shift_date:   string;
  action_type:  "assign_tm" | "clear_tm" | "patch_tasks";
  slot_id?:     string;
  slot_key?:    string;
  value_before?: string;
  value_after?:  string;
  editor_label?: string;
}

// ── Fetchers ───────────────────────────────────────────────────────────────

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { next: { revalidate: 15 } });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`ViewAPI ${res.status} at ${path}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/**
 * Resolve a YYYY-MM-DD shift date to its published night.
 * Throws if the date has no published schedule (404).
 */
export async function fetchViewNight(date: string): Promise<ViewNightMeta> {
  return get<ViewNightMeta>(`/v1/view/night/${date}`);
}

/**
 * Return all published nights for the archive date picker, newest-first.
 */
export async function fetchViewArchive(): Promise<ViewArchiveEntry[]> {
  return get<ViewArchiveEntry[]>("/v1/view/archive");
}

/**
 * Fire-and-forget audit log after a viewer edit.
 * Failure is intentionally swallowed — the edit already succeeded.
 */
export async function logViewerEdit(payload: ViewAuditPayload): Promise<void> {
  try {
    await fetch(`${BASE}/v1/view/audit`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload),
    });
  } catch {
    // Audit logging is non-fatal
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────

/**
 * Format a shift date for display: "Friday, May 9" (no year for current year,
 * with year for past/future).
 */
export function formatShiftDate(isoDate: string): string {
  const d    = new Date(`${isoDate}T12:00:00`);
  const now  = new Date();
  const opts: Intl.DateTimeFormatOptions =
    d.getFullYear() === now.getFullYear()
      ? { weekday: "long", month: "long", day: "numeric" }
      : { weekday: "long", month: "long", day: "numeric", year: "numeric" };
  return d.toLocaleDateString("en-US", opts);
}

/** Short date label for the archive list: "May 9" or "May 9, 2025". */
export function formatShiftDateShort(isoDate: string): string {
  const d   = new Date(`${isoDate}T12:00:00`);
  const now = new Date();
  const opts: Intl.DateTimeFormatOptions =
    d.getFullYear() === now.getFullYear()
      ? { month: "short", day: "numeric" }
      : { month: "short", day: "numeric", year: "numeric" };
  return d.toLocaleDateString("en-US", opts);
}
