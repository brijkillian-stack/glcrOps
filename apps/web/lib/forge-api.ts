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
  schedule_path: string | null;
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
  target_capacity: number; // per-day operational staffing target

  // Zone / RR breakdown
  zone_total: number;
  zone_filled: number;
  rr_total: number;
  rr_filled: number;

  // Sweeper slots
  sweeper_main_filled: boolean;  // "Sweeper 5/8/HL"
  sweeper_sr_filled: boolean;    // "Sweeper 9/10/SR"

  multi_area_overlap_count: number;
  override_count: number;
  reoptimize_recommended: boolean;

  note: string | null;
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

export type TaskCategory = "zone" | "rr" | "aux" | "overlap_am" | "overlap_pm" | "sweep";

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
  position: number;    // 1–6 integer from the DB
  is_filled: boolean;
  task: string;        // task description, e.g. "Vacuum, Bottles & Glass"
  tm_id: string | null;
  tm_name: string;     // "" when unfilled
}

/**
 * Derive a short display label for an overlap slot.
 * Accepts the integer position + window ("pm"|"am") stored in overlap_assignments.
 * Also handles legacy string codes ("PMOL1", "AMOL3") for defensive compatibility.
 */
export function overlapPositionLabel(
  position: string | number | null | undefined,
  window?: "pm" | "am",
): string {
  if (position == null) return "—";
  if (typeof position === "number") {
    const prefix = window === "pm" ? "PM OL" : window === "am" ? "AM OL" : "OL";
    return `${prefix} ${position}`;
  }
  // Legacy string codes: "PMOL1" → "PM OL 1", "AMOL3" → "AM OL 3"
  return String(position)
    .replace(/^PMOL(\d+)$/, "PM OL $1")
    .replace(/^AMOL(\d+)$/, "AM OL $1");
}

/** Fetch PM + AM overlap assignments for a single night.
 *  Always bypasses Next.js + browser HTTP caches so SWR revalidation
 *  after a mutation always returns fresh data. */
export async function fetchNightOverlaps(nightId: string): Promise<OverlapSlot[]> {
  return get<OverlapSlot[]>(`/v1/nights/${nightId}/overlaps`, { cache: "no-store" });
}

/** Update the task description on an overlap slot. */
export async function patchOverlapTask(
  nightId: string,
  overlapId: string,
  task: string,
): Promise<void> {
  const res = await fetch(`${BASE}/v1/nights/${nightId}/overlaps/${overlapId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`patchOverlapTask ${res.status}: ${body}`);
  }
}

/** Assign or clear a TM on an overlap slot. Pass null to clear. */
export async function patchOverlapTM(
  nightId: string,
  overlapId: string,
  tmId: string | null,
): Promise<void> {
  const res = await fetch(`${BASE}/v1/nights/${nightId}/overlaps/${overlapId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tm_id: tmId }),
  });
  if (!res.ok) throw new Error(`patchOverlapTM failed: ${res.status}`);
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

// ── Engine ────────────────────────────────────────────────────────────────────

export interface EngineRunResult {
  success:            boolean;
  scope:              "night" | "week";
  updated:            number;
  locked_skipped:     number;
  unresolved_cleared: number;
  unresolved:         string[];
  fill_rate:          number;   // 0–100
  week_ending:        string;
  message:            string;
  error:              string | null;
}

/** Run the fill engine for a single night. May take up to 90 s. */
export async function runEngineForNight(nightId: string): Promise<EngineRunResult> {
  const res = await fetch(`${BASE}/v1/engine/night/${nightId}/run`, {
    method: "POST",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Engine API ${res.status}: ${body}`);
  }
  return res.json() as Promise<EngineRunResult>;
}

/** Run the fill engine for an entire week. May take up to 90 s. */
export async function runEngineForWeek(weekId: string): Promise<EngineRunResult> {
  const res = await fetch(`${BASE}/v1/engine/week/${weekId}/run`, {
    method: "POST",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Engine API ${res.status}: ${body}`);
  }
  return res.json() as Promise<EngineRunResult>;
}

// ── Week status ───────────────────────────────────────────────────────────────

/** Publish or unpublish a week. Returns the updated status. */
export async function patchWeekStatus(
  weekId: string,
  status: "published" | "draft",
): Promise<{ week_id: string; status: string; updated: boolean }> {
  const res = await fetch(`${BASE}/v1/planning/weeks/${weekId}/status`, {
    method:  "PATCH",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ status }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`patchWeekStatus ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Slot lock (Feature 0) ─────────────────────────────────────────────────────

/** Lock or unlock a zone assignment slot. */
export async function patchSlotLock(
  nightId: string,
  slotId: string,
  isLocked: boolean,
): Promise<{ slot_id: string; is_locked: boolean; updated: boolean }> {
  const res = await fetch(
    `${BASE}/v1/nights/${nightId}/placements/${slotId}/lock`,
    {
      method:  "PATCH",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ is_locked: isLocked }),
    },
  );
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`patchSlotLock ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Slot swap (Feature 2) ─────────────────────────────────────────────────────

/** Atomically swap two slot TM assignments. */
export async function swapSlots(
  nightId: string,
  slotIdA: string,
  slotIdB: string,
): Promise<{ swapped: boolean }> {
  const res = await fetch(`${BASE}/v1/nights/${nightId}/placements/swap`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ slot_id_a: slotIdA, slot_id_b: slotIdB }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`swapSlots ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Schedule / attendance (Feature 3) ────────────────────────────────────────

export type TMStatus = "present" | "late" | "call_out" | "no_show";

/** A TM in the nightly schedule with attendance status overlay. */
export interface ScheduledTM {
  tm_id: string;
  tm_name: string;
  status: TMStatus;
  note: string | null;
  break_wave: number | null;
}

/** Fetch all TMs scheduled for a night with their attendance status. */
export async function fetchNightSchedule(nightId: string): Promise<ScheduledTM[]> {
  return get<ScheduledTM[]>(`/v1/nights/${nightId}/schedule`);
}

/** Upsert attendance status for a TM on a night. */
export async function setTMStatus(
  nightId: string,
  tmId: string,
  status: TMStatus,
  opts?: { tmName?: string; note?: string },
): Promise<ScheduledTM> {
  const res = await fetch(`${BASE}/v1/nights/${nightId}/schedule/${tmId}/status`, {
    method:  "PATCH",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({
      status,
      tm_name: opts?.tmName,
      note:    opts?.note,
    }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`setTMStatus ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Audit trail (Feature 5) ───────────────────────────────────────────────────

export type TrailActionType =
  | "assign"
  | "clear"
  | "lock"
  | "unlock"
  | "swap"
  | "status"
  | "engine_run"
  | "note";

/** One entry in the night_audit_log. */
export interface TrailEntry {
  id?: string;
  night_id: string;
  action_type: TrailActionType;
  slot_id: string | null;
  zone_label: string | null;
  tm_from: string | null;
  tm_to: string | null;
  detail: string | null;
  actor: string;
  created_at?: string;
}

/** Fetch the audit trail for a night (newest first). */
export async function fetchNightTrail(
  nightId: string,
  limit = 150,
): Promise<TrailEntry[]> {
  return get<TrailEntry[]>(`/v1/nights/${nightId}/trail?limit=${limit}`);
}

/** Append one entry to the night audit trail (best-effort — never throws). */
export async function addTrailEntry(
  nightId: string,
  entry: Omit<TrailEntry, "id" | "night_id" | "created_at">,
): Promise<void> {
  try {
    const res = await fetch(`${BASE}/v1/nights/${nightId}/trail`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ ...entry, night_id: nightId }),
    });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      console.warn(`addTrailEntry ${res.status}: ${body}`);
    }
  } catch (err) {
    console.warn("addTrailEntry failed (best-effort):", err);
  }
}

// ── Sweeper assignments ───────────────────────────────────────────────────────

export type SweeperSlot = "main" | "sr";

export interface SweeperAssignment {
  slot: SweeperSlot;
  label: string;   // "Sweeper 5/8/HL" | "Sweeper 9/10/SR"
  tm_id: string | null;
  tm_name: string;
}

/** Fetch both sweeper slots for a night. */
export async function fetchNightSweepers(nightId: string): Promise<SweeperAssignment[]> {
  return get<SweeperAssignment[]>(`/v1/nights/${nightId}/sweepers`);
}

/** Assign or clear a sweeper slot. Pass tmId=null to clear. */
export async function patchSweeperSlot(
  nightId: string,
  slot: SweeperSlot,
  tmId: string | null,
  tmName: string,
): Promise<void> {
  const res = await fetch(`${BASE}/v1/nights/${nightId}/sweepers/${slot}`, {
    method:  "PATCH",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ tm_id: tmId, tm_name: tmName }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`patchSweeperSlot ${res.status}: ${body}`);
  }
}

// ── Night note ────────────────────────────────────────────────────────────────

/** Set or clear the supervisor note for a night. */
export async function patchNightNote(
  nightId: string,
  note: string | null,
): Promise<void> {
  const res = await fetch(`${BASE}/v1/nights/${nightId}/note`, {
    method:  "PATCH",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ note }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`patchNightNote ${res.status}: ${body}`);
  }
}

// ── Week / schedule management ────────────────────────────────────────────────

/** Upload (or re-upload) a schedule xlsx, linking it to the given week.
 *  Sends base64-encoded JSON instead of multipart to avoid python-multipart
 *  dependency issues on the FastAPI side.
 */
export async function uploadScheduleForWeek(
  weekId: string,
  file: File,
): Promise<{ uploaded: boolean; filename: string; week_ending: string | null; message?: string }> {
  const arrayBuf = await file.arrayBuffer();
  const bytes = new Uint8Array(arrayBuf);
  // btoa on large files needs chunking to avoid call-stack overflow
  let binary = "";
  const CHUNK = 8192;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  const b64 = btoa(binary);
  const res = await fetch(
    `${BASE}/v1/planning/weeks/upload?week_id=${encodeURIComponent(weekId)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, data: b64 }),
    },
  );
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`uploadSchedule ${res.status}: ${body}`);
  }
  return res.json();
}

/** Remove (unlink) the schedule from a week. Pass removeFromStorage=true to also delete the file. */
export async function deleteWeekSchedule(
  weekId: string,
  removeFromStorage = false,
): Promise<void> {
  const qs = removeFromStorage ? "?remove_from_storage=true" : "";
  const res = await fetch(`${BASE}/v1/planning/weeks/${weekId}/schedule${qs}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`deleteWeekSchedule ${res.status}: ${body}`);
  }
}

// ── Week overview card flip ───────────────────────────────────────────────────

/** Minimal placement shape needed for the week overview card flip back side. */
export interface SlimPlacement {
  slot_id: string;
  zone_id: string;
  zone_label: string;
  zone_type: "zone" | "restroom" | "auxiliary";
  tm_id: string | null;
  tm_name: string | null;
}

/** Fetch zone placements for a night — used by the week overview card flip.
 *  Returns only the placements array from NightPlacementsResponse.
 */
export async function fetchNightPlacements(nightId: string): Promise<SlimPlacement[]> {
  const data = await get<{ placements: SlimPlacement[] }>(`/v1/nights/${nightId}/placements`);
  return data.placements ?? [];
}

/** Permanently delete a week and all associated data. */
export async function deleteWeek(weekId: string): Promise<void> {
  const res = await fetch(
    `${BASE}/v1/planning/weeks/${weekId}?confirm=DELETE`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`deleteWeek ${res.status}: ${body}`);
  }
}
