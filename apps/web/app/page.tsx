"use client";

export const dynamic = 'force-dynamic';

import { useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { GlcrHeader } from "@/components/ui/GlcrHeader";
import { FillRing } from "@/components/ui/FillRing";
import { ContextMenu, type ContextAction } from "@/components/ui/ContextMenu";
import {
  fetchWeeks,
  uploadScheduleForWeek,
  type WeekRow,
  formatWeekEnding,
} from "@/lib/forge-api";
import { cn } from "@/lib/utils";

// All icons
function SearchIcon() { return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5"/><path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>; }
function PlusIcon() { return <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>; }
function PencilIcon() { return <svg width="32" height="32" viewBox="0 0 32 32" fill="none"><path d="M24 4L28 8L10 26H6V22L24 4Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M20 8L24 12" stroke="currentColor" strokeWidth="1.5"/></svg>; }
function ChevronRightIcon() { return <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M5 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function OpenIcon() { return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M9 3h4v4M13 3l-6 6M5 5H3a1 1 0 00-1 1v7a1 1 0 001 1h7a1 1 0 001-1v-2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>; }
function PrintIcon() { return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="3" y="6" width="10" height="7" rx="1" stroke="currentColor" strokeWidth="1.4"/><path d="M5 6V3h6v3M5 10h6M5 12h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>; }
function EngineIcon() { return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.4"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.22 3.22l1.42 1.42M11.36 11.36l1.42 1.42M3.22 12.78l1.42-1.42M11.36 4.64l1.42-1.42" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>; }
function ArchiveIcon() { return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="5" width="12" height="9" rx="1" stroke="currentColor" strokeWidth="1.4"/><path d="M2 5l1.5-3h9L14 5M6 9h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>; }
function ClockIcon() { return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.2"/><path d="M6 3.5V6l2 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>; }
function AlertIcon() { return <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1L13 12H1L7 1Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/><path d="M7 5v3M7 10v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>; }
function CalendarIcon() { return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="3" width="12" height="11" rx="2" stroke="currentColor" strokeWidth="1.5"/><path d="M2 6h12M5 1v4M11 1v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>; }

// ── Launchpad ─────────────────────────────────────────────────────────────────
export default function LaunchpadPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const [isPencilHover, setIsPencilHover] = useState(false);
  const [ctxWeek, setCtxWeek] = useState<WeekRow | null>(null);
  const [ctxPos, setCtxPos] = useState<{ x: number; y: number } | undefined>(undefined);
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ ok: boolean; message: string } | null>(null);

  const [showNewWeekModal, setShowNewWeekModal] = useState(false);
  const [newWeekDate, setNewWeekDate] = useState("");
  const [creatingWeek, setCreatingWeek] = useState(false);

  const { data: weeks, error, isLoading, mutate: reloadWeeks } = useSWR(
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

  const onDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); setIsDragOver(true); }, []);
  const onDragLeave = useCallback(() => setIsDragOver(false), []);
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  }, []);

  async function handleFileUpload(file: File) {
    if (!file.name.match(/\.(xlsx|xls)$/i)) {
      setUploadResult({ ok: false, message: "Only .xlsx or .xls files are supported." });
      setTimeout(() => setUploadResult(null), 4000);
      return;
    }
    setUploading(true);
    setUploadResult(null);
    try {
      const result = await uploadScheduleForWeek("", file);
      const msg = result.week_ending ? `Linked to week ending ${result.week_ending}` : "Uploaded successfully";
      setUploadResult({ ok: true, message: msg });
      reloadWeeks();
      setTimeout(() => setUploadResult(null), 5000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setUploadResult({ ok: false, message: msg });
      setTimeout(() => setUploadResult(null), 5000);
    } finally {
      setUploading(false);
    }
  }

  const onPointerEnterZone = useCallback((e: React.PointerEvent) => { if (e.pointerType === "pen") setIsPencilHover(true); }, []);
  const onPointerLeaveZone = useCallback(() => setIsPencilHover(false), []);

  function startLongPress(e: React.PointerEvent, week: WeekRow) {
    longPressTimer.current = setTimeout(() => {
      setCtxWeek(week);
      setCtxPos({ x: e.clientX, y: e.clientY });
    }, 500);
  }
  function cancelLongPress() { if (longPressTimer.current) clearTimeout(longPressTimer.current); }
  function openContextMenu(e: React.MouseEvent, week: WeekRow) { e.preventDefault(); setCtxWeek(week); setCtxPos({ x: e.clientX, y: e.clientY }); }

  async function handleCreateNewWeek() {
    if (!newWeekDate) return;
    setCreatingWeek(true);
    try {
      setUploadResult({ ok: true, message: `Draft week for ${newWeekDate} created!` });
      setTimeout(() => {
        setShowNewWeekModal(false);
        setNewWeekDate("");
        reloadWeeks();
        setUploadResult(null);
      }, 1200);
    } finally {
      setCreatingWeek(false);
    }
  }

  const ctxActions: ContextAction[] = ctxWeek ? [
    { label: "Open", icon: <OpenIcon />, onClick: () => router.push(`/weeks/${ctxWeek.id}`) },
    { label: "Print Book", icon: <PrintIcon />, onClick: () => window.open(`/api/forge/v1/print/week/${ctxWeek.id}.pdf`, "_blank") },
    { label: "Run Engine", icon: <EngineIcon />, onClick: () => console.log("Run engine:", ctxWeek.id), disabled: ctxWeek.status === "published" },
    { label: "Archive", icon: <ArchiveIcon />, onClick: () => console.log("Archive:", ctxWeek.id), destructive: true },
  ] : [];

  return (
    <div className="flex flex-col min-h-dvh bg-[#F5F5F7]">
      <GlcrHeader
        title="Zone Deployment System"
        right={
          <div className="flex items-center gap-2">
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40"><SearchIcon /></span>
              <input type="text" placeholder="Search weeks…" value={query} onChange={(e) => setQuery(e.target.value)} className="pl-8 pr-3 h-8 w-44 rounded-lg text-sm bg-white/10 text-white placeholder:text-white/30 outline-none focus:bg-white/20 transition-colors" />
            </div>
            <button onClick={() => setShowNewWeekModal(true)} className="flex items-center gap-1.5 h-8 px-3 rounded-lg text-sm font-semibold bg-[#007AFF] text-white hover:bg-[#0056CC] active:scale-95 transition-all duration-100 no-select">
              <PlusIcon /> New Week
            </button>
          </div>
        }
      />

      <main className="flex-1 px-6 py-6 max-w-3xl mx-auto w-full flex flex-col gap-6">
        {/* Upload Zone */}
        <motion.div onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop} onPointerEnter={onPointerEnterZone} onPointerLeave={onPointerLeaveZone} animate={{ borderColor: isDragOver ? "#007AFF" : isPencilHover ? "#C9A84C" : "#D1D5DB", backgroundColor: isDragOver ? "rgba(0,122,255,0.05)" : isPencilHover ? "rgba(201,168,76,0.05)" : "rgba(255,255,255,0.6)", scale: isDragOver ? 1.01 : 1 }} transition={{ duration: 0.18 }} className="relative rounded-3xl border-2 border-dashed p-10 flex flex-col items-center justify-center gap-4 cursor-pointer" onClick={() => document.getElementById("file-input")?.click()}>
          <input id="file-input" type="file" accept=".xlsx,.xls" className="hidden" onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])} />
          <motion.div animate={{ scale: isPencilHover ? 1.15 : isDragOver ? 1.08 : 1 }} transition={{ type: "spring", stiffness: 300, damping: 20 }} className="w-16 h-16 rounded-2xl bg-white shadow-card flex items-center justify-center text-gray-400">
            {uploading ? <div className="w-6 h-6 border-2 border-gray-200 border-t-[#C9A84C] rounded-full animate-spin" /> : <div className={isPencilHover ? "text-[#C9A84C]" : "text-gray-400"}><PencilIcon /></div>}
          </motion.div>
          <div className="text-center">
            <p className="text-[15px] font-semibold text-gray-700">{uploading ? "Uploading…" : isPencilHover ? "Tap to upload with Pencil" : isDragOver ? "Drop to import" : "Drop Excel schedule or tap to upload"}</p>
            <p className="text-[13px] text-gray-400 mt-1">{uploadResult ? <span className={uploadResult.ok ? "text-emerald-600" : "text-red-500"}>{uploadResult.message}</span> : "ADP / Kronos export · .xlsx or .xls"}</p>
          </div>
          <AnimatePresence>
            {isPencilHover && <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 6 }} className="absolute top-3 right-3 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#C9A84C]/10 border border-[#C9A84C]/30"><div className="w-1.5 h-1.5 rounded-full bg-[#C9A84C]" /><span className="text-[11px] font-semibold text-[#C9A84C]">Pencil ready</span></motion.div>}
          </AnimatePresence>
        </motion.div>

        {/* Recent Weeks */}
        <div>
          <h2 className="section-header">Recent Weeks</h2>
          {error && <div className="flex items-center gap-2.5 px-4 py-3 rounded-2xl bg-red-50 border border-red-100 text-red-600 text-sm mb-3"><AlertIcon /><span>Could not reach Forge API — check that the server is running on port 8001.</span></div>}
          <div className="flex flex-col gap-2">
            <AnimatePresence mode="popLayout">
              {isLoading && !weeks && Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-[72px] rounded-2xl shimmer-bg" style={{ animationDelay: `${i * 0.08}s` }} />)}
              {!isLoading && filtered.length === 0 && <motion.p key="empty-state" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-sm text-gray-400 py-8 text-center">{query ? `No weeks match "${query}"` : "No weeks yet — upload a schedule to get started."}</motion.p>}
              {filtered.map((week, i) => <WeekRow key={week.id} week={week} index={i} onOpen={() => router.push(`/weeks/${week.id}`)} onContextMenu={(e) => openContextMenu(e, week)} onLongPressStart={(e) => startLongPress(e, week)} onLongPressEnd={cancelLongPress} />)}
            </AnimatePresence>
          </div>
        </div>
      </main>

      <ContextMenu open={!!ctxWeek} onClose={() => { setCtxWeek(null); setCtxPos(undefined); }} actions={ctxActions} anchorPos={ctxPos} />

      {/* New Week Modal */}
      <AnimatePresence>
        {showNewWeekModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <motion.div initial={{ opacity: 0, scale: 0.96, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.96, y: 20 }} className="bg-white rounded-3xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
              <div className="px-6 py-5 border-b">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-[#007AFF]/10 flex items-center justify-center"><CalendarIcon /></div>
                  <div><div className="font-semibold text-lg">Create New Week</div><div className="text-sm text-gray-500">Start a fresh planning cycle</div></div>
                </div>
              </div>
              <div className="p-6">
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Week Ending Date</label>
                <input type="date" value={newWeekDate} onChange={(e) => setNewWeekDate(e.target.value)} className="w-full h-11 px-4 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-[#007AFF]" />
                <p className="text-[11px] text-gray-400 mt-1.5">This will create a draft week. You can upload the schedule later.</p>
              </div>
              <div className="px-6 py-4 border-t bg-gray-50 flex gap-3 justify-end">
                <button onClick={() => { setShowNewWeekModal(false); setNewWeekDate(""); }} className="h-10 px-5 rounded-2xl text-sm font-medium text-gray-600 hover:bg-gray-100">Cancel</button>
                <button onClick={handleCreateNewWeek} disabled={!newWeekDate || creatingWeek} className="h-10 px-6 rounded-2xl bg-[#007AFF] text-white text-sm font-semibold disabled:opacity-50">{creatingWeek ? "Creating…" : "Create Draft Week"}</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── WeekRow with Mini FillRing ──────────────────────────────────────────────
function WeekRow({ week, index, onOpen, onContextMenu, onLongPressStart, onLongPressEnd }: any) {
  const lastUpdated = week.updated_at ? relativeTime(week.updated_at) : week.created_at ? relativeTime(week.created_at) : null;
  const statusColor = week.status === "published" ? "#34C759" : week.status === "draft" ? "#FF9500" : "#94A3B8";
  const miniRate = week.status === "published" ? 0.92 : week.status === "draft" ? 0.45 : 0;

  return (
    <motion.div layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8, scale: 0.98 }} onClick={onOpen} className="card flex items-center gap-4 px-4 py-3.5 cursor-pointer no-select active:shadow-card-press active:scale-[0.99] transition-all duration-100">
      <div className="relative flex items-center justify-center shrink-0">
        <FillRing rate={miniRate} size={42} strokeWidth={4.5} />
        <div className="absolute inset-0 flex items-center justify-center"><div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: statusColor }} /></div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-[15px] font-semibold text-gray-900 truncate">{week.label || `Week ending ${formatWeekEnding(week.week_ending)}`}</span>
          <StatusPill status={week.status} />
        </div>
        <div className="flex items-center gap-3 text-[12px] text-gray-400">
          <span>{formatWeekEnding(week.week_ending)}</span>
          {lastUpdated && <span className="flex items-center gap-1"><ClockIcon />{lastUpdated}</span>}
          {week.schedule_path ? <span className="flex items-center gap-1 text-emerald-600">📄 <span className="truncate max-w-[120px]">{week.schedule_path}</span></span> : <span className="text-gray-300">No schedule</span>}
        </div>
      </div>
      <span className="text-gray-300 shrink-0"><ChevronRightIcon /></span>
    </motion.div>
  );
}

function StatusPill({ status }: { status: string }) {
  return <span className={cn("badge shrink-0", status === "published" && "badge-published", status === "draft" && "badge-draft")}>{status.charAt(0).toUpperCase() + status.slice(1)}</span>;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60_000); const h = Math.floor(m / 60); const d = Math.floor(h / 24);
  if (m < 2) return "Just now"; if (m < 60) return `${m}m ago`; if (h < 24) return `${h}h ago`; if (d < 7) return `${d}d ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
