"use client";

import { useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { GlcrHeader } from "@/components/ui/GlcrHeader";
import { FillRing } from "@/components/ui/FillRing";
import { ContextMenu, type ContextAction } from "@/components/ui/ContextMenu";
import {
  fetchWeeks,
  type WeekRow,
  formatWeekEnding,
  coveragePctToRate,
} from "@/lib/forge-api";
import { cn } from "@/lib/utils";

// ── Icons ─────────────────────────────────────────────────────────────────────

function SearchIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5"/><path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>;
}
function PlusIcon() {
  return <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>;
}
function PencilIcon() {
  return <svg width="32" height="32" viewBox="0 0 32 32" fill="none"><path d="M24 4L28 8L10 26H6V22L24 4Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M20 8L24 12" stroke="currentColor" strokeWidth="1.5"/></svg>;
}
function ChevronRightIcon() {
  return <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M5 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}
function OpenIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M9 3h4v4M13 3l-6 6M5 5H3a1 1 0 00-1 1v7a1 1 0 001 1h7a1 1 0 001-1v-2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>;
}
function PrintIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="3" y="6" width="10" height="7" rx="1" stroke="currentColor" strokeWidth="1.4"/><path d="M5 6V3h6v3M5 10h6M5 12h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>;
}
function EngineIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.4"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.22 3.22l1.42 1.42M11.36 11.36l1.42 1.42M3.22 12.78l1.42-1.42M11.36 4.64l1.42-1.42" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>;
}
function ArchiveIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="5" width="12" height="9" rx="1" stroke="currentColor" strokeWidth="1.4"/><path d="M2 5l1.5-3h9L14 5M6 9h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>;
}
function ClockIcon() {
  return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.2"/><path d="M6 3.5V6l2 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>;
}
function AlertIcon() {
  return <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1L13 12H1L7 1Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/><path d="M7 5v3M7 10v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>;
}

// ── Launchpad ─────────────────────────────────────────────────────────────────

export default function LaunchpadPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const [isPencilHover, setIsPencilHover] = useState(false);
  const [ctxWeek, setCtxWeek] = useState<WeekRow | null>(null);
  const [ctxPos, setCtxPos] = useState<{ x: number; y: number } | undefined>();
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Live data from Forge API ───────────────────────────────────────────────
  const { data: weeks, error, isLoading } = useSWR(
    "forge:weeks",
    () => fetchWeeks(12),
    { revalidateOnFocus: true, refreshInterval: 60_000 }
  );

  const filtered = (weeks ?? []).filter((w) =>
    query
      ? formatWeekEnding(w.week_ending).toLowerCase().includes(query.toLowerCase()) ||
        w.label.toLowerCase().includes(query.toLowerCase()) ||
        w.status.includes(query.toLowerCase())
      : true
  );

  // ── Drag-and-drop ──────────────────────────────────────────────────────────
  const onDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); setIsDragOver(true); }, []);
  const onDragLeave = useCallback(() => setIsDragOver(false), []);
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  }, []);

  function handleFileUpload(file: File) {
    // TODO: POST to /api/forge/v1/weeks/upload
    console.log("Uploading:", file.name);
  }

  const onPointerEnterZone = useCallback((e: React.PointerEvent) => {
    if (e.pointerType === "pen") setIsPencilHover(true);
  }, []);
  const onPointerLeaveZone = useCallback(() => setIsPencilHover(false), []);

  function startLongPress(e: React.PointerEvent, week: WeekRow) {
    longPressTimer.current = setTimeout(() => {
      setCtxWeek(week);
      setCtxPos({ x: e.clientX, y: e.clientY });
    }, 500);
  }
  function cancelLongPress() {
    if (longPressTimer.current) clearTimeout(longPressTimer.current);
  }
  function openContextMenu(e: React.MouseEvent, week: WeekRow) {
    e.preventDefault();
    setCtxWeek(week);
    setCtxPos({ x: e.clientX, y: e.clientY });
  }

  const ctxActions: ContextAction[] = ctxWeek
    ? [
        { label: "Open", icon: <OpenIcon />, onClick: () => router.push(`/weeks/${ctxWeek.id}`) },
        { label: "Print Book", icon: <PrintIcon />, onClick: () => window.open(`/api/forge/v1/print/week/${ctxWeek.id}.pdf`, "_blank") },
        { label: "Run Engine", icon: <EngineIcon />, onClick: () => console.log("Run engine:", ctxWeek.id), disabled: ctxWeek.status === "published" },
        { label: "Archive", icon: <ArchiveIcon />, onClick: () => console.log("Archive:", ctxWeek.id), destructive: true },
      ]
    : [];

  return (
    <div className="flex flex-col min-h-dvh bg-[#F5F5F7]">
      <GlcrHeader
        title="Zone Deployment System"
        right={
          <div className="flex items-center gap-2">
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40"><SearchIcon /></span>
              <input
                type="text"
                placeholder="Search weeks…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-8 pr-3 h-8 w-44 rounded-lg text-sm bg-white/10 text-white
                           placeholder:text-white/30 outline-none focus:bg-white/20 transition-colors"
              />
            </div>
            <button
              className="flex items-center gap-1.5 h-8 px-3 rounded-lg text-sm font-semibold
                         bg-[#007AFF] text-white hover:bg-[#0056CC] active:scale-95
                         transition-all duration-100 no-select"
            >
              <PlusIcon />
              New Week
            </button>
          </div>
        }
      />

      <main className="flex-1 px-6 py-6 max-w-3xl mx-auto w-full flex flex-col gap-6">

        {/* Upload Zone */}
        <motion.div
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onPointerEnter={onPointerEnterZone}
          onPointerLeave={onPointerLeaveZone}
          animate={{
            borderColor: isDragOver ? "#007AFF" : isPencilHover ? "#C9A84C" : "#D1D5DB",
            backgroundColor: isDragOver ? "rgba(0,122,255,0.05)" : isPencilHover ? "rgba(201,168,76,0.05)" : "rgba(255,255,255,0.6)",
            scale: isDragOver ? 1.01 : 1,
          }}
          transition={{ duration: 0.18 }}
          className="relative rounded-3xl border-2 border-dashed p-10 flex flex-col
                     items-center justify-center gap-4 cursor-pointer"
          onClick={() => document.getElementById("file-input")?.click()}
        >
          <input id="file-input" type="file" accept=".xlsx,.xls" className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])} />

          <motion.div
            animate={{ scale: isPencilHover ? 1.15 : isDragOver ? 1.08 : 1 }}
            transition={{ type: "spring", stiffness: 300, damping: 20 }}
            className="w-16 h-16 rounded-2xl bg-white shadow-card flex items-center justify-center text-gray-400"
          >
            <div className={isPencilHover ? "text-[#C9A84C]" : "text-gray-400"}><PencilIcon /></div>
          </motion.div>

          <div className="text-center">
            <p className="text-[15px] font-semibold text-gray-700">
              {isPencilHover ? "Tap to upload with Pencil" : isDragOver ? "Drop to import" : "Drop Excel schedule or tap to upload"}
            </p>
            <p className="text-[13px] text-gray-400 mt-1">ADP / Kronos export · .xlsx or .xls</p>
          </div>

          <AnimatePresence>
            {isPencilHover && (
              <motion.div
                initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 6 }}
                className="absolute top-3 right-3 flex items-center gap-1.5 px-2.5 py-1
                           rounded-full bg-[#C9A84C]/10 border border-[#C9A84C]/30"
              >
                <div className="w-1.5 h-1.5 rounded-full bg-[#C9A84C]" />
                <span className="text-[11px] font-semibold text-[#C9A84C]">Pencil ready</span>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* Recent Weeks */}
        <div>
          <h2 className="section-header">Recent Weeks</h2>

          {/* Error state */}
          {error && (
            <div className="flex items-center gap-2.5 px-4 py-3 rounded-2xl bg-red-50 border border-red-100 text-red-600 text-sm mb-3">
              <AlertIcon />
              <span>Could not reach Forge API — check that the server is running on port 8001.</span>
            </div>
          )}

          <div className="flex flex-col gap-2">
            <AnimatePresence mode="popLayout">
              {isLoading && !weeks && (
                <>
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="h-[72px] rounded-2xl shimmer-bg" style={{ animationDelay: `${i * 0.08}s` }} />
                  ))}
                </>
              )}

              {!isLoading && filtered.length === 0 && (
                <motion.p
                  key="empty-state"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="text-sm text-gray-400 py-8 text-center"
                >
                  {query ? `No weeks match "${query}"` : "No weeks yet — upload a schedule to get started."}
                </motion.p>
              )}

              {filtered.map((week, i) => (
                <WeekRow
                  key={week.id}
                  week={week}
                  index={i}
                  onOpen={() => router.push(`/weeks/${week.id}`)}
                  onContextMenu={(e) => openContextMenu(e, week)}
                  onLongPressStart={(e) => startLongPress(e, week)}
                  onLongPressEnd={cancelLongPress}
                />
              ))}
            </AnimatePresence>
          </div>
        </div>
      </main>

      <ContextMenu
        open={!!ctxWeek}
        onClose={() => { setCtxWeek(null); setCtxPos(undefined); }}
        actions={ctxActions}
        anchorPos={ctxPos}
      />
    </div>
  );
}

// ── Week Row ──────────────────────────────────────────────────────────────────

interface WeekRowProps {
  week: WeekRow;
  index: number;
  onOpen: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
  onLongPressStart: (e: React.PointerEvent) => void;
  onLongPressEnd: () => void;
}

function WeekRow({ week, index, onOpen, onContextMenu, onLongPressStart, onLongPressEnd }: WeekRowProps) {
  const lastUpdated = week.updated_at
    ? relativeTime(week.updated_at)
    : week.created_at
    ? relativeTime(week.created_at)
    : null;

  // WeekRow doesn't have coverage data — that comes from the weekly overview.
  // Show a neutral ring placeholder; clicking opens the overview which has real data.
  const statusColor =
    week.status === "published" ? "#34C759" :
    week.status === "draft"     ? "#FF9500" : "#94A3B8";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8, scale: 0.98 }}
      transition={{ delay: index * 0.05, duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      onContextMenu={onContextMenu}
      onPointerDown={onLongPressStart}
      onPointerUp={onLongPressEnd}
      onPointerCancel={onLongPressEnd}
      onClick={onOpen}
      className="card flex items-center gap-4 px-4 py-3.5 cursor-pointer no-select
                 active:shadow-card-press active:scale-[0.99] transition-all duration-100"
    >
      {/* Status dot ring */}
      <div className="relative w-11 h-11 shrink-0 flex items-center justify-center">
        <svg width="44" height="44" viewBox="0 0 44 44">
          <circle cx="22" cy="22" r="18" fill="none" stroke="#E5E7EB" strokeWidth="3.5" />
          <circle cx="22" cy="22" r="18" fill="none" stroke={statusColor}
                  strokeWidth="3.5" strokeLinecap="round"
                  strokeDasharray={113} strokeDashoffset={week.status === "published" ? 0 : week.status === "draft" ? 56 : 85}
                  transform="rotate(-90 22 22)" style={{ transition: "stroke-dashoffset 0.5s" }} />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: statusColor }} />
        </div>
      </div>

      {/* Week info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-[15px] font-semibold text-gray-900 truncate">
            {week.label || `Week ending ${formatWeekEnding(week.week_ending)}`}
          </span>
          <StatusPill status={week.status} />
        </div>
        <div className="flex items-center gap-3 text-[12px] text-gray-400">
          <span>{formatWeekEnding(week.week_ending)}</span>
          {lastUpdated && (
            <span className="flex items-center gap-1">
              <ClockIcon />
              {lastUpdated}
            </span>
          )}
        </div>
      </div>

      <span className="text-gray-300 shrink-0"><ChevronRightIcon /></span>
    </motion.div>
  );
}

// ── Status Pill ───────────────────────────────────────────────────────────────

function StatusPill({ status }: { status: string }) {
  return (
    <span className={cn("badge shrink-0",
      status === "published" && "badge-published",
      status === "draft"     && "badge-draft",
      status === "archived"  && "badge-archived",
    )}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60_000);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (m < 2)  return "Just now";
  if (m < 60) return `${m}m ago`;
  if (h < 24) return `${h}h ago`;
  if (d < 7)  return `${d}d ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
