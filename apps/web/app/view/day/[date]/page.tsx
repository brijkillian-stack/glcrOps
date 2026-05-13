"use client";

/**
 * /view/day/[date] — Published Schedule Viewer
 *
 * Displays the published deployment for any given shift date.
 * - Past shifts:                  read-only (no edits, no context menus)
 * - Current + future published:   limited edit (assign / clear TM, audited)
 *
 * The 90-minute buffer rule is enforced server-side on the `is_editable`
 * field returned by GET /v1/view/night/{date}.
 */

import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { consumeAccessDeniedCookie } from "@/lib/auth";
import useSWR from "swr";
import { motion, AnimatePresence } from "framer-motion";
import { useNightPlacements, type TMAssignment, type GroupId } from "@/lib/sync";
import {
  fetchActiveTMs,
  getNightPrintUrl,
  getWeekPrintUrl,
  type ActiveTM,
} from "@/lib/forge-api";
import {
  fetchViewNight,
  fetchViewArchive,
  logViewerEdit,
  formatShiftDate,
  formatShiftDateShort,
  type ViewNightMeta,
  type ViewArchiveEntry,
} from "@/lib/view-api";
import { getShiftDate } from "@/lib/shift-date";
import { cn, groupColor, zoneAccentColor, rrSideTint } from "@/lib/utils";
import { formatBreakTime } from "@/lib/shift-date";

// ── Break schedule constants (matches Python _BREAK_SCHEDULE) ─────────────────
const BREAK_TIMES: Record<string, Record<string, [string, string, number]>> = {
  "1": { "1": ["00:45", "01:00", 15], "2": ["02:30", "03:00", 30], "3": ["05:00", "05:15", 15] },
  "2": { "1": ["01:00", "01:15", 15], "2": ["03:00", "03:30", 30], "3": ["05:00", "05:15", 15] },
  "3": { "1": ["01:15", "01:30", 15], "2": ["03:30", "04:00", 30], "3": ["05:15", "05:30", 15] },
};
const WAVE_LABELS: Record<string, string> = {
  "1": "First Break", "2": "Main Break", "3": "Last Break",
};

// ── Icons ─────────────────────────────────────────────────────────────────────

function ArrowLeftIcon()   { return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function CalendarIcon()    { return <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><rect x="1.5" y="2.5" width="12" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.3"/><path d="M5 1v3M10 1v3M1.5 6.5h12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>; }
function PrintIcon()       { return <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><rect x="2" y="5" width="9" height="6" rx="1" stroke="currentColor" strokeWidth="1.2"/><path d="M4 5V2h5v3M4 8h5M4 10h3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg>; }
function LockIcon()        { return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><rect x="1.5" y="5" width="9" height="6.5" rx="1.2" stroke="currentColor" strokeWidth="1.2"/><path d="M3.5 5V3.5a2.5 2.5 0 015 0V5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>; }
function CheckIcon()       { return <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M2.5 6.5l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function ChevronLeftIcon() { return <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M8.5 3L5 7l3.5 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function ChevronRightIcon(){ return <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M5.5 3L9 7l-3.5 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function XIcon()           { return <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>; }
function SearchIcon()      { return <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1.3"/><path d="M9 9l3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>; }
function EditIcon()        { return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M8.5 1.5l2 2-6 6H2.5v-2l6-6z" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function TrashIcon()       { return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M1.5 3h9M4 3V2h4v1M5 5.5v3.5M7 5.5v3.5M2 3l.7 7h6.6L10 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>; }

// ── Viewer Zone Card ──────────────────────────────────────────────────────────

interface ViewerCardProps {
  slot:       TMAssignment;
  readOnly:   boolean;
  onClick:    (slot: TMAssignment) => void;
  onLongPress?: (e: React.MouseEvent, slot: TMAssignment) => void;
}

function ViewerCard({ slot, readOnly, onClick, onLongPress }: ViewerCardProps) {
  const accent   = zoneAccentColor(slot.zone_id);
  const bgTint   = slot.zone_type === "restroom" ? rrSideTint(slot.rr_side) : "transparent";
  const isEmpty  = !slot.tm_id;
  const tasks    = slot.tasks ?? [];
  const regularTasks  = tasks.filter(t => !t.toLowerCase().startsWith("and "));
  const coverageTasks = tasks.filter(t => t.toLowerCase().startsWith("and "));

  function handleClick() {
    if (!readOnly) onClick(slot);
  }

  return (
    <div
      onClick={handleClick}
      onContextMenu={readOnly ? undefined : (e) => { e.preventDefault(); onLongPress?.(e, slot); }}
      className={cn(
        "relative rounded-2xl overflow-hidden border border-transparent",
        "transition-all duration-150",
        !readOnly && "cursor-pointer active:scale-[0.97]",
        isEmpty
          ? "bg-white/40 border-dashed border-gray-200"
          : "bg-white shadow-sm",
        !readOnly && !isEmpty && "hover:shadow-md",
        !readOnly && isEmpty && "hover:bg-white/60 hover:border-gray-300",
      )}
      style={{ background: isEmpty ? undefined : bgTint !== "transparent" ? bgTint : undefined }}
    >
      {/* Top accent stripe */}
      <div className="h-[3px] w-full" style={{ backgroundColor: isEmpty ? "#E5E7EB" : accent }} />

      <div className="px-2.5 pt-2 pb-2.5 flex flex-col gap-1 min-h-[72px]">
        {/* Zone label */}
        <div className="flex items-center justify-between gap-1">
          <span
            className="text-[10px] font-bold uppercase tracking-wider leading-none"
            style={{ color: isEmpty ? "#9CA3AF" : accent }}
          >
            {slot.zone_label}
          </span>
          {slot.rr_side && (
            <span className={cn(
              "text-[9px] font-semibold px-1 py-0.5 rounded-full uppercase tracking-wide",
              slot.rr_side === "mens"   ? "bg-blue-50 text-blue-500"   : "bg-pink-50 text-pink-500",
            )}>
              {slot.rr_side === "mens" ? "M" : "W"}
            </span>
          )}
        </div>

        {/* TM name */}
        <div className={cn(
          "text-[13px] font-semibold leading-tight",
          isEmpty ? "text-gray-300 italic font-normal text-[12px]" : "text-gray-900",
        )}>
          {isEmpty ? "Unfilled" : slot.tm_name}
        </div>

        {/* Regular tasks */}
        {regularTasks.length > 0 && (
          <div className="flex flex-col gap-0.5 mt-0.5">
            {regularTasks.map((t, i) => (
              <div key={i} className="text-[10.5px] text-gray-500 leading-snug truncate">{t}</div>
            ))}
          </div>
        )}

        {/* Coverage tasks */}
        {coverageTasks.length > 0 && (
          <div className={cn("flex flex-col gap-0.5", regularTasks.length > 0 && "border-t border-gray-100 pt-1 mt-0.5")}>
            {coverageTasks.map((t, i) => (
              <div key={i} className="text-[11px] font-bold text-gray-700 text-center leading-snug">{t}</div>
            ))}
          </div>
        )}

        {/* Edit hint — only in edit mode on empty slots */}
        {!readOnly && isEmpty && (
          <div className="text-[10px] text-gray-300 mt-auto pt-1 text-center">tap to assign</div>
        )}
      </div>

      {/* Read-only lock watermark on empty cards */}
      {readOnly && isEmpty && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="opacity-[0.07]">
            <LockIcon />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Zone Section ──────────────────────────────────────────────────────────────

interface ZoneSectionProps {
  title:    string;
  slots:    TMAssignment[];
  readOnly: boolean;
  onCardClick:      (slot: TMAssignment) => void;
  onCardContextMenu: (e: React.MouseEvent, slot: TMAssignment) => void;
}

function ZoneSection({ title, slots, readOnly, onCardClick, onCardContextMenu }: ZoneSectionProps) {
  if (slots.length === 0) return null;
  const filled = slots.filter(s => s.tm_id).length;

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[11px] font-bold uppercase tracking-widest text-gray-400">{title}</h2>
        <span className="text-[11px] font-semibold text-gray-400">{filled}/{slots.length}</span>
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 gap-2.5">
        {slots.map((slot, i) => (
          <motion.div
            key={slot.slot_id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.025, duration: 0.2 }}
          >
            <ViewerCard
              slot={slot}
              readOnly={readOnly}
              onClick={onCardClick}
              onLongPress={onCardContextMenu}
            />
          </motion.div>
        ))}
      </div>
    </section>
  );
}

// ── Break Sheet ───────────────────────────────────────────────────────────────

function BreakSheet({ placements }: { placements: TMAssignment[] }) {
  // Build group-centric structure: each group has its own 3 break times,
  // and all TMs in that group attend all three breaks together.
  const groups = useMemo(() => {
    const roster: Record<string, string[]> = { "1": [], "2": [], "3": [] };
    const seen = new Set<string>();
    for (const p of placements) {
      if (!p.tm_id || !p.tm_name || !p.group || !(p.group in roster)) continue;
      if (seen.has(p.tm_id)) continue;
      seen.add(p.tm_id);
      roster[p.group].push(p.tm_name);
    }
    return (["1","2","3"] as GroupId[]).map(grpId => ({
      group: grpId,
      names: roster[grpId],
      // All three waves for this group — times are fixed per group
      breaks: (["1","2","3"] as GroupId[]).map(waveId => {
        const [start, end, dur] = BREAK_TIMES[grpId][waveId];
        return { wave: waveId, label: WAVE_LABELS[waveId], start, end, dur };
      }),
    }));
  }, [placements]);

  return (
    <section>
      <h2 className="text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-3">
        Break Schedule
      </h2>
      <div className="flex flex-col gap-3">
        {groups.map(g => (
          <div key={g.group} className="card rounded-2xl overflow-hidden">

            {/* Group header */}
            <div className="flex items-center gap-2 px-3 py-2.5 border-b border-gray-100/80">
              <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: groupColor(g.group) }} />
              <span className="text-[12px] font-bold text-gray-700 uppercase tracking-wide">
                Group {g.group}
              </span>
              <span className="text-[11px] text-gray-400 ml-auto">
                {g.names.length} TM{g.names.length !== 1 ? "s" : ""}
              </span>
            </div>

            {/* Two-column body: break times | TM roster */}
            <div className="grid grid-cols-2 divide-x divide-gray-100">

              {/* Break times — fixed schedule for this group */}
              <div className="px-3 py-2.5">
                <div className="text-[9px] font-bold uppercase tracking-widest text-gray-400 mb-2">
                  Breaks
                </div>
                <div className="flex flex-col gap-2">
                  {g.breaks.map(b => (
                    <div key={b.wave} className="flex items-start gap-2">
                      {/* Wave color dot */}
                      <div
                        className="w-1.5 h-1.5 rounded-full mt-1 shrink-0"
                        style={{ background: b.wave === "1" ? "#60a5fa" : b.wave === "2" ? "#a78bfa" : "#34d399" }}
                      />
                      <div>
                        <div className="text-[10px] font-semibold text-gray-500 leading-none mb-0.5">
                          {b.label}
                        </div>
                        <div className="text-[12px] font-bold text-gray-800 leading-none">
                          {formatBreakTime(b.start)}
                          <span className="text-[10px] font-medium text-gray-400 ml-1">
                            {b.dur}m
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* TM roster — same people attend all three breaks */}
              <div className="px-3 py-2.5">
                <div className="text-[9px] font-bold uppercase tracking-widest text-gray-400 mb-2">
                  Team
                </div>
                {g.names.length === 0 ? (
                  <div className="text-[12px] text-gray-300 italic">No TMs assigned</div>
                ) : (
                  <div className="flex flex-col gap-0.5">
                    {g.names.map((name, i) => (
                      <div key={i} className="text-[12px] font-medium text-gray-800 leading-snug">
                        {name}
                      </div>
                    ))}
                  </div>
                )}
              </div>

            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── Archive Calendar ──────────────────────────────────────────────────────────

const MONTH_NAMES = ["January","February","March","April","May","June",
                     "July","August","September","October","November","December"];
const DAY_NAMES   = ["Su","Mo","Tu","We","Th","Fr","Sa"];

interface ArchiveCalendarProps {
  archive:       ViewArchiveEntry[];
  viewingDate:   string;
  onSelectDate:  (date: string) => void;
}

function ArchiveCalendar({ archive, viewingDate, onSelectDate }: ArchiveCalendarProps) {
  const publishedSet = useMemo(() => new Set(archive.map(e => e.shift_date)), [archive]);
  const editableSet  = useMemo(() => new Set(archive.filter(e => e.is_editable).map(e => e.shift_date)), [archive]);

  const initialDate = viewingDate || getShiftDate();
  const [year,  setYear]  = useState(() => parseInt(initialDate.slice(0, 4)));
  const [month, setMonth] = useState(() => parseInt(initialDate.slice(5, 7)) - 1); // 0-based

  function prevMonth() {
    if (month === 0) { setMonth(11); setYear(y => y - 1); }
    else setMonth(m => m - 1);
  }
  function nextMonth() {
    if (month === 11) { setMonth(0); setYear(y => y + 1); }
    else setMonth(m => m + 1);
  }

  // Build calendar grid
  const days = useMemo(() => {
    const firstDay  = new Date(year, month, 1).getDay();
    const daysInMo  = new Date(year, month + 1, 0).getDate();
    const cells: Array<{ day: number | null; iso: string | null }> = [];
    for (let i = 0; i < firstDay; i++) cells.push({ day: null, iso: null });
    for (let d = 1; d <= daysInMo; d++) {
      const iso = `${year}-${String(month + 1).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
      cells.push({ day: d, iso });
    }
    return cells;
  }, [year, month]);

  return (
    <div className="flex flex-col">
      {/* Month nav */}
      <div className="flex items-center justify-between mb-3 px-1">
        <button onClick={prevMonth} className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-500">
          <ChevronLeftIcon />
        </button>
        <span className="text-[14px] font-semibold text-gray-800">
          {MONTH_NAMES[month]} {year}
        </span>
        <button onClick={nextMonth} className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-500">
          <ChevronRightIcon />
        </button>
      </div>

      {/* Day-of-week headers */}
      <div className="grid grid-cols-7 mb-1">
        {DAY_NAMES.map(d => (
          <div key={d} className="text-center text-[10px] font-semibold text-gray-400 py-1">{d}</div>
        ))}
      </div>

      {/* Day cells */}
      <div className="grid grid-cols-7 gap-0.5">
        {days.map((cell, i) => {
          if (!cell.day || !cell.iso) {
            return <div key={i} />;
          }
          const isPublished  = publishedSet.has(cell.iso);
          const isEditable   = editableSet.has(cell.iso);
          const isViewing    = cell.iso === viewingDate;
          const isToday      = cell.iso === getShiftDate();

          return (
            <button
              key={i}
              disabled={!isPublished}
              onClick={() => isPublished && onSelectDate(cell.iso!)}
              className={cn(
                "relative aspect-square flex flex-col items-center justify-center rounded-xl",
                "text-[12px] font-medium transition-all duration-100",
                !isPublished && "text-gray-300 cursor-default",
                isPublished && !isViewing && "hover:bg-gray-100 cursor-pointer",
                isViewing && "text-white font-bold",
                isEditable && !isViewing && "text-blue-600",
                !isEditable && isPublished && !isViewing && "text-gray-700",
              )}
              style={isViewing ? { backgroundColor: "var(--blue-primary)" } : undefined}
            >
              {cell.day}
              {/* Published dot — shown for non-viewing cells */}
              {isPublished && !isViewing && (
                <div className={cn(
                  "absolute bottom-1 w-1 h-1 rounded-full",
                  isEditable ? "bg-blue-400" : "bg-green-400",
                )} />
              )}
              {/* Today indicator */}
              {isToday && !isViewing && (
                <div className="absolute top-1 right-1 w-1 h-1 rounded-full bg-orange-400" />
              )}
            </button>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 px-1">
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-green-400" />
          <span className="text-[10px] text-gray-400">Past</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
          <span className="text-[10px] text-gray-400">Editable</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-orange-400" />
          <span className="text-[10px] text-gray-400">Today</span>
        </div>
      </div>
    </div>
  );
}

// ── Archive Picker Sheet ──────────────────────────────────────────────────────

interface ArchivePickerSheetProps {
  open:         boolean;
  onClose:      () => void;
  archive:      ViewArchiveEntry[];
  archiveLoading: boolean;
  viewingDate:  string;
  onSelectDate: (date: string) => void;
}

function ArchivePickerSheet({ open, onClose, archive, archiveLoading, viewingDate, onSelectDate }: ArchivePickerSheetProps) {
  const [tab, setTab] = useState<"calendar" | "list">("calendar");

  // Group list by week label
  const byWeek = useMemo(() => {
    const map = new Map<string, ViewArchiveEntry[]>();
    for (const e of archive) {
      const key = e.week_label ?? `Week of ${e.shift_date}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(e);
    }
    return [...map.entries()];
  }, [archive]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-black/30 z-40 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Sheet */}
          <motion.div
            className="fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-3xl shadow-2xl max-h-[80vh] flex flex-col"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 340 }}
          >
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-1">
              <div className="w-10 h-1 rounded-full bg-gray-200" />
            </div>

            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
              <h2 className="text-[17px] font-bold text-gray-900">Browse Schedules</h2>
              <button onClick={onClose} className="p-2 rounded-xl hover:bg-gray-100 text-gray-400">
                <XIcon />
              </button>
            </div>

            {/* Tabs */}
            <div className="flex gap-0 px-5 pt-3">
              {(["calendar", "list"] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={cn(
                    "flex-1 py-2 text-[13px] font-semibold rounded-xl transition-colors",
                    tab === t ? "bg-blue-50 text-blue-600" : "text-gray-400 hover:text-gray-600",
                  )}
                >
                  {t === "calendar" ? "Calendar" : "List"}
                </button>
              ))}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {archiveLoading ? (
                <div className="flex items-center justify-center py-16 text-gray-400 text-[13px]">
                  Loading schedules…
                </div>
              ) : archive.length === 0 ? (
                <div className="flex items-center justify-center py-16 text-gray-400 text-[13px]">
                  No published schedules found.
                </div>
              ) : tab === "calendar" ? (
                <ArchiveCalendar
                  archive={archive}
                  viewingDate={viewingDate}
                  onSelectDate={(d) => { onSelectDate(d); onClose(); }}
                />
              ) : (
                <div className="flex flex-col gap-5">
                  {byWeek.map(([weekLabel, nights]) => (
                    <div key={weekLabel}>
                      <div className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-2">
                        {weekLabel}
                      </div>
                      <div className="flex flex-col gap-1">
                        {nights.map(entry => (
                          <button
                            key={entry.night_id}
                            onClick={() => { onSelectDate(entry.shift_date); onClose(); }}
                            className={cn(
                              "flex items-center justify-between px-3 py-2.5 rounded-xl text-left",
                              "transition-colors",
                              entry.shift_date === viewingDate
                                ? "bg-blue-500 text-white"
                                : "hover:bg-gray-50 text-gray-800",
                            )}
                          >
                            <div>
                              <div className="text-[13px] font-semibold">{entry.day_name}</div>
                              <div className={cn(
                                "text-[11px]",
                                entry.shift_date === viewingDate ? "text-white/70" : "text-gray-400",
                              )}>
                                {formatShiftDateShort(entry.shift_date)}
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              {entry.is_editable && (
                                <span className={cn(
                                  "text-[10px] font-semibold px-2 py-0.5 rounded-full",
                                  entry.shift_date === viewingDate
                                    ? "bg-white/20 text-white"
                                    : "bg-blue-50 text-blue-500",
                                )}>
                                  Editable
                                </span>
                              )}
                              {entry.shift_date === viewingDate && <CheckIcon />}
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ── Context Menu (edit mode only) ─────────────────────────────────────────────

interface SlotContextMenuProps {
  slot:    TMAssignment;
  pos:     { x: number; y: number } | null;
  onClose: () => void;
  onSwap:  () => void;
  onClear: () => void;
}

function SlotContextMenu({ slot, pos, onClose, onSwap, onClear }: SlotContextMenuProps) {
  if (!pos) return null;
  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.92 }}
        transition={{ duration: 0.1 }}
        className="fixed z-50 glass-dark rounded-2xl shadow-2xl overflow-hidden min-w-[180px] py-1"
        style={{ left: Math.min(pos.x, window.innerWidth - 200), top: Math.min(pos.y, window.innerHeight - 120) }}
      >
        <div className="px-3 py-1.5 border-b border-white/10">
          <div className="text-[11px] font-semibold text-white/50 uppercase tracking-wider">
            {slot.zone_label}
          </div>
          {slot.tm_name && (
            <div className="text-[13px] font-bold text-white">{slot.tm_name}</div>
          )}
        </div>
        {slot.tm_id ? (
          <>
            <button
              onClick={() => { onSwap(); onClose(); }}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-white/10 text-white text-[14px] transition-colors"
            >
              <EditIcon /> <span>Swap TM</span>
            </button>
            <button
              onClick={() => { onClear(); onClose(); }}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-red-500/20 text-red-400 text-[14px] transition-colors"
            >
              <TrashIcon /> <span>Clear Slot</span>
            </button>
          </>
        ) : (
          <button
            onClick={() => { onSwap(); onClose(); }}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-white/10 text-white text-[14px] transition-colors"
          >
            <EditIcon /> <span>Assign TM</span>
          </button>
        )}
      </motion.div>
    </>
  );
}

// ── TM Picker Sheet ───────────────────────────────────────────────────────────

interface TMPickerSheetProps {
  targetSlot: TMAssignment | null;
  onClose:    () => void;
  onSelect:   (tm: ActiveTM | null) => Promise<void>;
}

function TMPickerSheet({ targetSlot, onClose, onSelect }: TMPickerSheetProps) {
  const [query, setQuery] = useState("");

  const { data: tms = [], isLoading } = useSWR(
    targetSlot ? "forge:tms" : null,
    () => fetchActiveTMs(),
    { dedupingInterval: 60_000 },
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? tms.filter(t => t.display_name.toLowerCase().includes(q) || t.name.toLowerCase().includes(q)) : tms;
  }, [tms, query]);

  const open = !!targetSlot;

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 bg-black/30 z-40 backdrop-blur-sm"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-3xl shadow-2xl max-h-[70vh] flex flex-col"
            initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 340 }}
          >
            <div className="flex justify-center pt-3 pb-1">
              <div className="w-10 h-1 rounded-full bg-gray-200" />
            </div>
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
              <div>
                <h2 className="text-[17px] font-bold text-gray-900">Assign TM</h2>
                {targetSlot && (
                  <p className="text-[12px] text-gray-400">{targetSlot.zone_label}</p>
                )}
              </div>
              <button onClick={onClose} className="p-2 rounded-xl hover:bg-gray-100 text-gray-400">
                <XIcon />
              </button>
            </div>

            {/* Search */}
            <div className="px-5 pt-3 pb-2">
              <div className="flex items-center gap-2 px-3 py-2.5 bg-gray-50 rounded-xl">
                <SearchIcon />
                <input
                  autoFocus
                  type="text"
                  placeholder="Search team members…"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  className="flex-1 bg-transparent text-[14px] outline-none text-gray-800 placeholder:text-gray-400"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-5 pb-6">
              {/* Clear option */}
              {targetSlot?.tm_id && (
                <button
                  onClick={() => onSelect(null)}
                  className="w-full flex items-center gap-3 px-3 py-3 mb-1 rounded-xl text-red-500 hover:bg-red-50 transition-colors"
                >
                  <div className="w-8 h-8 rounded-full bg-red-50 flex items-center justify-center">
                    <XIcon />
                  </div>
                  <span className="text-[14px] font-medium">Clear slot</span>
                </button>
              )}

              {isLoading ? (
                <div className="text-center py-8 text-gray-400 text-[13px]">Loading…</div>
              ) : filtered.map(tm => (
                <button
                  key={tm.id}
                  onClick={() => onSelect(tm)}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors text-left",
                    targetSlot?.tm_id === tm.id ? "bg-blue-50" : "hover:bg-gray-50",
                  )}
                >
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-white text-[11px] font-bold shrink-0"
                    style={{ backgroundColor: groupColor(tm.id.charCodeAt(0) % 8 + 1) }}
                  >
                    {tm.display_name.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <div className="text-[14px] font-semibold text-gray-900">{tm.display_name}</div>
                    {tm.name !== tm.display_name && (
                      <div className="text-[11px] text-gray-400">{tm.name}</div>
                    )}
                  </div>
                  {targetSlot?.tm_id === tm.id && (
                    <div className="ml-auto text-blue-500"><CheckIcon /></div>
                  )}
                </button>
              ))}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function DayViewerPage() {
  const router       = useRouter();
  const params       = useParams<{ date: string }>();
  const shiftDate    = params?.date ?? "";

  // ── Metadata: resolve date → night_id + editability ──────────────────────
  const {
    data:    meta,
    error:   metaError,
    isLoading: metaLoading,
  } = useSWR<ViewNightMeta>(
    shiftDate ? `forge:view:meta:${shiftDate}` : null,
    () => fetchViewNight(shiftDate),
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );

  const nightId    = meta?.night_id ?? "";
  const isEditable = meta?.is_editable ?? false;

  // ── Placements (reuses the same hook + API as the main planner) ───────────
  const { data, isLoading: placementsLoading, assignTM, refresh } = useNightPlacements(
    nightId,
  );

  // ── Archive (lazy — only fetched when archive sheet opens) ────────────────
  const [archiveOpen, setArchiveOpen] = useState(false);
  const { data: archive = [], isLoading: archiveLoading } = useSWR<ViewArchiveEntry[]>(
    archiveOpen ? "forge:view:archive" : null,
    fetchViewArchive,
    { dedupingInterval: 30_000, revalidateOnFocus: false },
  );

  // ── Access-denied flash (set by middleware when restricted role redirected) ─
  const [accessDenied, setAccessDenied] = useState(false);
  useEffect(() => {
    if (consumeAccessDeniedCookie()) setAccessDenied(true);
  }, []);

  // ── Context menu + TM picker (edit mode only) ─────────────────────────────
  const [ctxSlot, setCtxSlot] = useState<TMAssignment | null>(null);
  const [ctxPos,  setCtxPos]  = useState<{ x: number; y: number } | null>(null);
  const [pickerSlot, setPickerSlot] = useState<TMAssignment | null>(null);

  function openCtx(e: React.MouseEvent, slot: TMAssignment) {
    if (!isEditable) return;
    e.preventDefault();
    setCtxSlot(slot);
    setCtxPos({ x: e.clientX, y: e.clientY });
  }

  function handleCardClick(slot: TMAssignment) {
    if (!isEditable) return;
    if (!slot.tm_id) {
      // Empty slot → open TM picker directly
      setPickerSlot(slot);
    } else {
      // Filled slot → open context menu
      setCtxSlot(slot);
      setCtxPos({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
    }
  }

  async function handleTMSelect(tm: ActiveTM | null) {
    if (!pickerSlot && !ctxSlot) return;
    const slot      = pickerSlot ?? ctxSlot!;
    const tmBefore  = slot.tm_id ?? null;
    const tmAfter   = tm?.id ?? null;

    setPickerSlot(null);
    setCtxSlot(null);

    await assignTM(slot.slot_id, tm ? { id: tm.id, name: tm.display_name, initials: tm.display_name.slice(0,2) } : null);

    // Audit log — fire-and-forget
    if (meta) {
      logViewerEdit({
        night_id:     meta.night_id,
        shift_date:   meta.shift_date,
        action_type:  tm ? "assign_tm" : "clear_tm",
        slot_id:      slot.slot_id,
        slot_key:     slot.zone_id,
        value_before: tmBefore ?? undefined,
        value_after:  tmAfter ?? undefined,
      });
    }
  }

  // ── Print helpers ─────────────────────────────────────────────────────────
  function printNight() {
    if (!nightId) return;
    window.open(getNightPrintUrl(nightId, "pdf"), "_blank");
  }
  function printWeek() {
    if (!meta?.week_id) return;
    window.open(getWeekPrintUrl(meta.week_id, "pdf"), "_blank");
  }

  // ── Derived slot groups ───────────────────────────────────────────────────
  const placements = data?.placements ?? [];
  const zones      = placements.filter(p => p.zone_type === "zone");
  const restrooms  = placements.filter(p => p.zone_type === "restroom");
  const auxiliary  = placements.filter(p => p.zone_type === "auxiliary");

  // ── Fill rate ─────────────────────────────────────────────────────────────
  const fillRate = useMemo(() => {
    if (!placements.length) return 0;
    const filled = placements.filter(p => !!p.tm_id).length;
    return Math.round((filled / placements.length) * 100);
  }, [placements]);

  // ── States: loading / error / not-found ───────────────────────────────────
  const isLoading = metaLoading || (!!nightId && placementsLoading && !data);
  const notFound  = !metaLoading && (metaError?.message?.includes("404") || (!metaLoading && !meta && !metaError));
  const isError   = !!metaError && !metaError.message?.includes("404");

  // ── Date display ──────────────────────────────────────────────────────────
  const dateLabel = shiftDate ? formatShiftDate(shiftDate) : "—";

  return (
    <div className="min-h-dvh bg-[#F5F5F7]">
      {/* ── Top Bar ─────────────────────────────────────────────────── */}
      <div className="sticky top-0 z-30 bg-[#1A2340]/95 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center gap-3">
          {/* Back */}
          <button
            onClick={() => router.push("/")}
            className="flex items-center gap-1.5 text-white/60 hover:text-white transition-colors text-[13px] font-medium shrink-0"
          >
            <ArrowLeftIcon />
            <span className="hidden sm:inline">Schedules</span>
          </button>

          <div className="w-px h-4 bg-white/20" />

          {/* Date + badge */}
          <div className="flex-1 flex items-center gap-2.5 min-w-0">
            <div className="min-w-0">
              <div className="text-white font-semibold text-[15px] leading-tight truncate">
                {isLoading ? "Loading…" : dateLabel}
              </div>
              {meta && (
                <div className="text-[11px] text-white/50 leading-tight">
                  {isEditable ? "Editable" : "Read-only"}
                  {" · "}
                  {fillRate}% filled
                </div>
              )}
            </div>

            {/* Status badge */}
            {meta && (
              <div className={cn(
                "shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold",
                isEditable
                  ? "bg-blue-500/20 text-blue-300"
                  : "bg-green-500/15 text-green-400",
              )}>
                {isEditable ? <EditIcon /> : <CheckIcon />}
                {meta.week_status === "archived" ? "Archived" : "Published"}
              </div>
            )}

            {!isEditable && meta && (
              <div className="shrink-0 flex items-center gap-1 px-2 py-1 rounded-full bg-white/10 text-white/50 text-[11px] font-medium">
                <LockIcon />
                <span className="hidden sm:inline">Read-only</span>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => setArchiveOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white text-[12px] font-medium transition-colors"
            >
              <CalendarIcon />
              <span className="hidden sm:inline">Archive</span>
            </button>

            {nightId && (
              <div className="flex items-center gap-1">
                <button
                  onClick={printNight}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white text-[12px] font-medium transition-colors"
                  title="Print Day"
                >
                  <PrintIcon />
                  <span className="hidden md:inline">Day</span>
                </button>
                <button
                  onClick={printWeek}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white text-[12px] font-medium transition-colors"
                  title="Print Week"
                >
                  <PrintIcon />
                  <span className="hidden md:inline">Week</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Access-denied banner ────────────────────────────────────── */}
      {accessDenied && (
        <div className="bg-amber-50 border-b border-amber-200">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-start justify-between gap-3">
            <div className="flex items-start gap-2.5">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5 text-amber-600">
                <path d="M8 1L15 13H1L8 1Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
                <path d="M8 6v3M8 11v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              <div>
                <p className="text-[13px] font-semibold text-amber-800">Limited Access</p>
                <p className="text-[12px] text-amber-700 mt-0.5">
                  Your role only has access to the Published Day Viewer. Contact a Graves Ops Super or Sudo Admin for full access.
                </p>
              </div>
            </div>
            <button
              onClick={() => setAccessDenied(false)}
              className="shrink-0 p-1 rounded-lg hover:bg-amber-100 text-amber-500 transition-colors"
              aria-label="Dismiss"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* ── Content ─────────────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-4 py-6">

        {/* Loading */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
            <div className="text-[13px] text-gray-400">Loading schedule…</div>
          </div>
        )}

        {/* 404 — no published schedule */}
        {!isLoading && (notFound || (!meta && !isError)) && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center justify-center py-24 gap-4 text-center"
          >
            <div className="w-16 h-16 rounded-3xl bg-gray-100 flex items-center justify-center">
              <CalendarIcon />
            </div>
            <div>
              <h2 className="text-[20px] font-bold text-gray-800 mb-1">No Published Schedule</h2>
              <p className="text-[14px] text-gray-400 max-w-xs">
                There's no published schedule for{" "}
                <strong>{shiftDate ? formatShiftDate(shiftDate) : "this date"}</strong>.
                Browse the archive to find a published night.
              </p>
            </div>
            <button
              onClick={() => setArchiveOpen(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-blue-500 text-white rounded-xl text-[14px] font-semibold hover:bg-blue-600 transition-colors"
            >
              <CalendarIcon />
              Browse Archive
            </button>
          </motion.div>
        )}

        {/* Error */}
        {isError && (
          <div className="flex flex-col items-center justify-center py-24 gap-3 text-center">
            <p className="text-[14px] text-red-400">{metaError?.message}</p>
            <button onClick={() => refresh()} className="text-[13px] text-blue-500 underline">Retry</button>
          </div>
        )}

        {/* Schedule */}
        {!isLoading && meta && data && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.25 }}
            className="flex flex-col gap-8"
          >
            {/* Read-only banner */}
            {!isEditable && (
              <div className="flex items-center gap-3 px-4 py-3 bg-amber-50 border border-amber-200 rounded-2xl">
                <LockIcon />
                <div>
                  <div className="text-[13px] font-semibold text-amber-800">Past Shift — Read-only</div>
                  <div className="text-[12px] text-amber-600">
                    This shift has ended. No edits can be made to past published schedules.
                  </div>
                </div>
              </div>
            )}

            {/* Zone sections */}
            <ZoneSection
              title="Zones"
              slots={zones}
              readOnly={!isEditable}
              onCardClick={handleCardClick}
              onCardContextMenu={openCtx}
            />
            <ZoneSection
              title="Restrooms"
              slots={restrooms}
              readOnly={!isEditable}
              onCardClick={handleCardClick}
              onCardContextMenu={openCtx}
            />
            <ZoneSection
              title="Auxiliary"
              slots={auxiliary}
              readOnly={!isEditable}
              onCardClick={handleCardClick}
              onCardContextMenu={openCtx}
            />

            {/* Break sheet */}
            {placements.length > 0 && <BreakSheet placements={placements} />}
          </motion.div>
        )}
      </div>

      {/* ── Overlays ─────────────────────────────────────────────────── */}

      {/* Context menu */}
      <AnimatePresence>
        {ctxSlot && ctxPos && isEditable && (
          <SlotContextMenu
            slot={ctxSlot}
            pos={ctxPos}
            onClose={() => { setCtxSlot(null); setCtxPos(null); }}
            onSwap={() => { setPickerSlot(ctxSlot); setCtxSlot(null); setCtxPos(null); }}
            onClear={() => { handleTMSelect(null); setCtxSlot(null); setCtxPos(null); }}
          />
        )}
      </AnimatePresence>

      {/* TM Picker */}
      <TMPickerSheet
        targetSlot={pickerSlot}
        onClose={() => setPickerSlot(null)}
        onSelect={handleTMSelect}
      />

      {/* Archive Picker */}
      <ArchivePickerSheet
        open={archiveOpen}
        onClose={() => setArchiveOpen(false)}
        archive={archive}
        archiveLoading={archiveLoading}
        viewingDate={shiftDate}
        onSelectDate={(d) => router.push(`/view/day/${d}`)}
      />
    </div>
  );
}
