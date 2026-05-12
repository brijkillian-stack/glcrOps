/**
 * Shift Date Logic — applies everywhere in the ZDS app.
 *
 * RULE: "Today" is always the shift START date, not the raw calendar date.
 *
 * The grave shift runs 11 PM → 7 AM.  At 3:00 AM Saturday you are still
 * on the Friday shift.  The system switches to the next shift at 8:30 AM
 * (7:00 AM shift end + 90-minute buffer).
 *
 * This module is the single source of truth for shift date logic.
 * Never use `new Date()` directly for anything shift-related — use
 * these helpers instead.
 *
 * Source: Brian's master prompt — committed to GLCR memory 2026-05-12.
 */

/** 8 hours 30 minutes — the cutover point after which we're on the next shift */
const SHIFT_CUTOVER_HOUR   = 8;
const SHIFT_CUTOVER_MINUTE = 30;

/**
 * Returns the shift date for a given moment in time.
 *
 * Before 8:30 AM  → the shift date is YESTERDAY (the shift started last night)
 * At/after 8:30 AM → the shift date is TODAY     (tonight's shift)
 *
 * @param at - The moment to evaluate (defaults to now)
 * @returns ISO date string "YYYY-MM-DD" of the shift date
 */
export function getShiftDate(at?: Date): string {
  const now = at ?? new Date();
  const h   = now.getHours();
  const m   = now.getMinutes();

  const isBeforeCutover =
    h < SHIFT_CUTOVER_HOUR ||
    (h === SHIFT_CUTOVER_HOUR && m < SHIFT_CUTOVER_MINUTE);

  const shiftDate = new Date(now);
  if (isBeforeCutover) {
    shiftDate.setDate(shiftDate.getDate() - 1);
  }

  return toISODate(shiftDate);
}

/**
 * Returns the calendar date of the shift night start for a given shift date.
 *
 * The shift date is the date the shift *starts* (e.g. "Friday").
 * The shift night starts at 11 PM on that date.
 * The shift morning ends at 7 AM the *next* calendar day.
 *
 * @param shiftDate - ISO date string "YYYY-MM-DD"
 * @returns Date object representing 11:00 PM on the shift start date
 */
export function shiftStartTime(shiftDate: string): Date {
  const d = new Date(`${shiftDate}T23:00:00`);
  return d;
}

/**
 * Returns the expected shift end time (7:00 AM the morning after the shift date).
 */
export function shiftEndTime(shiftDate: string): Date {
  const d = new Date(`${shiftDate}T07:00:00`);
  d.setDate(d.getDate() + 1);
  return d;
}

/**
 * True if `at` falls within the active window of the shift that started on `shiftDate`.
 * Active window: 11 PM on shiftDate → 8:30 AM the next calendar day.
 */
export function isActiveShift(shiftDate: string, at?: Date): boolean {
  const now   = at ?? new Date();
  const start = shiftStartTime(shiftDate);
  const end   = shiftEndTime(shiftDate);
  // cutover is 90 min after nominal end
  end.setMinutes(end.getMinutes() + 90);
  return now >= start && now <= end;
}

/**
 * True when the given shift date is in the past (the shift has ended and
 * the 8:30 AM cutover has passed).  Past shifts are read-only.
 */
export function isShiftEditable(shiftDate: string, at?: Date): boolean {
  const now     = at ?? new Date();
  const current = getShiftDate(now);
  // Editable = current shift or future shifts
  return shiftDate >= current;
}

/**
 * Human-readable "shift day" label, e.g. "Friday" or "Tonight (Friday)".
 *
 * @param shiftDate - ISO date string
 * @param at        - Current moment (defaults to now)
 */
export function shiftDayLabel(shiftDate: string, at?: Date): string {
  const current = getShiftDate(at);
  const d = new Date(`${shiftDate}T12:00:00`);
  const dayName = d.toLocaleDateString("en-US", { weekday: "long" });

  if (shiftDate === current) return `Tonight (${dayName})`;

  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowDate = toISODate(tomorrow);
  if (shiftDate === tomorrowDate) return `Tomorrow (${dayName})`;

  return dayName;
}

/** Format a Date to "YYYY-MM-DD" in local time. */
function toISODate(d: Date): string {
  const y  = d.getFullYear();
  const mo = String(d.getMonth() + 1).padStart(2, "0");
  const dy = String(d.getDate()).padStart(2, "0");
  return `${y}-${mo}-${dy}`;
}

/** Convert "HH:MM" 24h string to a display label like "12:45 AM" or "2:30 AM". */
export function formatBreakTime(hhmm: string): string {
  const [hStr, mStr] = hhmm.split(":");
  let h = parseInt(hStr, 10);
  const m = mStr ?? "00";
  const ampm = h < 12 ? "AM" : "PM";
  if (h === 0) h = 12;
  else if (h > 12) h -= 12;
  return `${h}:${m} ${ampm}`;
}
