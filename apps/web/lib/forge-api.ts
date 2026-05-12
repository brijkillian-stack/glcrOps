/**
 * ZDS Forge API client — types mirror the FastAPI Pydantic models exactly.
 *
 * Endpoints:
 *   GET /v1/planning/weeks              → WeekRow[]
 *   GET /v1/planning/weekly/{week_id}   → WeeklyPlanningOverviewResponse
 *   GET /v1/print/week/{id}.html|.pdf
 *   GET /v1/print/night/{id}.html|.pdf
 *
 * All requests go through Next.js rewrites: /api/forge/* → http://localhost:8001/*
 */

const BASE = "/api/forge";

// ── Types — mirror apps/zds/api/models/week.py & planning.py exactly ─────────

export type WeekStatus = "draft" | "published" | "archived";

/** One row from the `weeks` Supabase table */
export interface WeekRow {
  id: string;
  week_ending: string;     // "YYYY-MM-DD"
  label: string;
  status: WeekStatus;
  schedule_path: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** WeekMeta sub-object inside WeeklyPlanningOverviewResponse */
export interface WeekMeta {
  id: string;
  label: string;
  week_start: string;      // "YYYY-MM-DD"
  week_ending: string;     // "YYYY-MM-DD"
  status: WeekStatus;
}

/** Per-night coverage snapshot — mirrors NightPlanningSnapshot */
export interface NightPlanningSnapshot {
  night_id: string;
  night_date: string;      // "YYYY-MM-DD"
  day_name: string;        // "Friday" … "Thursday"
  in_rotation: boolean;

  total_slots: number;
  filled_slots: number;
  gap_count: number;
  coverage_pct: number;    // 0–100 (percent, NOT 0–1)

  multi_area_overlap_count: number;
  override_count: number;
  reoptimize_recommended: boolean;
}

/** Aggregated week metrics — mirrors WeekMetrics */
export interface WeekMetrics {
  total_assignments: number;
  total_gaps: number;
  nights_with_gaps: number;
  multi_area_overlap_count: number;
  active_override_count: number;
  fatigue_index: number;
  reoptimize_opportunities: number;
}

export interface PlanningNote {
  night_id: string;
  day_name: string;
  note_kind: "gap" | "override" | "overlap" | "info";
  note_text: string;
}

export interface OverrideSummary {
  night_id: string;
  day_name: string;
  slot_key: string;
  tm_id: string | null;
  note: string | null;
  created_at: string | null;
}

export interface PlanningLinks {
  print_week_html: string;
  print_week_pdf: string;
  reoptimize: string;
}

/** Full weekly planning overview — mirrors WeeklyPlanningOverviewResponse */
export interface WeeklyPlanningOverviewResponse {
  week: WeekMeta;
  nights: NightPlanningSnapshot[];
  metrics: WeekMetrics;
  planning_notes: PlanningNote[];
  active_overrides: OverrideSummary[];
  links: PlanningLinks;
  cached_at: string;
}

// ── Fetchers ──────────────────────────────────────────────────────────────────

async function get<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    next: { revalidate: 15 },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Forge API ${res.status} at ${path}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/** Fetch the recent weeks list for the Launchpad */
export async function fetchWeeks(limit = 12): Promise<WeekRow[]> {
  return get<WeekRow[]>(`/v1/planning/weeks?limit=${limit}`);
}

/** Fetch the full weekly planning overview */
export async function fetchWeekOverview(weekId: string): Promise<WeeklyPlanningOverviewResponse> {
  return get<WeeklyPlanningOverviewResponse>(`/v1/planning/weekly/${weekId}`);
}

export function getWeekPrintUrl(weekId: string, format: "html" | "pdf") {
  return `${BASE}/v1/print/week/${weekId}.${format}`;
}

// ── TM Roster ─────────────────────────────────────────────────────────────────

/** Active TM from entities table — mirrors TMRow in apps/zds/api/models/tm.py */
export interface ActiveTM {
  id: string;
  name: string;
  display_name: string;
  status: string;
  metadata: Record<string, unknown> | null;
}

/** Fetch active TM roster for the picker sheet. Cached by SWR at call site. */
export async function fetchActiveTMs(): Promise<ActiveTM[]> {
  return get<ActiveTM[]>("/v1/planning/tms");
}

export function getNightPrintUrl(nightId: string, format: "html" | "pdf") {
  return `${BASE}/v1/print/night/${nightId}.${format}`;
}

// ── Zone Tasks ────────────────────────────────────────────────────────────────

export type TaskCategory = "zone" | "rr" | "aux" | "overlap_am" | "overlap_pm";

export interface ZoneTask {
  id: string;
  name: string;
  code: string;
  category: TaskCategory;
  target_codes: string[];
  description: string | null;
  display_order: number;
}

/** Fetch zone tasks filtered by broad slot type (zone | restroom | auxiliary). */
export async function fetchZoneTasks(slotType?: string): Promise<ZoneTask[]> {
  const qs = slotType ? `?slot_type=${slotType}` : "";
  return get<ZoneTask[]>(`/v1/planning/tasks${qs}`);
}

// ── Overlap Assignments ───────────────────────────────────────────────────────

/** One row from overlap_assignments — a PM or AM overlap slot for a night. */
export interface OverlapSlot {
  id: string;
  overlap_window: "pm" | "am";
  position: string;    // "PMOL1"–"PMOL6" | "AMOL1"–"AMOL6"
  is_filled: boolean;
  task: string;        // task description, e.g. "Vacuum, Bottles & Glass"
  tm_id: string | null;
  tm_name: string;     // "" when unfilled
}

/** Derive a short display label from position code: "PMOL1" → "PM OL 1" */
export function overlapPositionLabel(position: string | null | undefined): string {
  if (!position) return "—";
  return position
    .replace(/^PMOL(\d+)$/, "PM OL $1")
    .replace(/^AMOL(\d+)$/, "AM OL $1");
}

/** Fetch PM + AM overlap assignments for a single night. */
export async function fetchNightOverlaps(nightId: string): Promise<OverlapSlot[]> {
  return get<OverlapSlot[]>(`/v1/nights/${nightId}/overlaps`);
}

/** Move a TM between break waves. */
export async function moveBreakTMApi(
  nightId: string,
  tmId: string,
  fromWave: number,
  toWave: number,
): Promise<void> {
  const res = await fetch(`${BASE}/v1/nights/${nightId}/breaks/move`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tm_id: tmId, from_wave: fromWave, to_wave: toWave }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`moveBreakTM ${res.status}: ${body}`);
  }
}

/** Update custom tasks on a slot. */
export async function patchSlotTasks(
  nightId: string,
  slotId: string,
  tasks: string[],
): Promise<void> {
  const res = await fetch(
    `${BASE}/v1/nights/${nightId}/placements/${slotId}/tasks`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tasks }),
    },
  );
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`patchSlotTasks ${res.status}: ${body}`);
  }
}

// ── UI helpers ────────────────────────────────────────────────────────────────

export function formatWeekEnding(isoDate: string): string {
  if (!isoDate) return "";
  const d = new Date(`${isoDate}T12:00:00`);
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
}

/** coverage_pct is 0–100 from the API; normalize to 0–1 for display */
export function coveragePctToRate(pct: number): number {
  return pct / 100;
}

export function fillRateColor(rate: number): string {
  if (rate >= 0.9) return "#34C759";
  if (rate >= 0.75) return "#FF9500";
  return "#FF3B30";
}

export function fillRateLabel(rate: number): string {
  return `${Math.round(rate * 100)}%`;
}
