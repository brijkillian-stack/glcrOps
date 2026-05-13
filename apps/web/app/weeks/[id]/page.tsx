"use client";

import { useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter, useParams } from "next/navigation";
import useSWR from "swr";
import { GlcrHeader } from "@/components/ui/GlcrHeader";
import { FillRing } from "@/components/ui/FillRing";
import { ContextMenu, type ContextAction } from "@/components/ui/ContextMenu";
import {
  fetchWeekOverview,
  formatWeekEnding,
  coveragePctToRate,
  getWeekPrintUrl,
  patchWeekStatus,
  patchNightNote,
  runEngineForNight,
  uploadScheduleForWeek,
  deleteWeekSchedule,
  deleteWeek,
  type WeeklyPlanningOverviewResponse,
  type NightPlanningSnapshot,
  type EngineRunResult,
} from "@/lib/forge-api";
import { cn } from "@/lib/utils";
import { mutate as globalMutate } from "swr";

// ── Icons ─────────────────────────────────────────────────────────────────────

function ArrowLeftIcon() { return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function PublishIcon() { return <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1v8M4 4L7 1l3 3M2 10v2a1 1 0 001 1h8a1 1 0 001-1v-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function UserPlusIcon() { return <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="5.5" cy="4.5" r="3" stroke="currentColor" strokeWidth="1.2"/><path d="M1 12c0-2.5 2-4 4.5-4s4.5 1.5 4.5 4M10 5h3M11.5 3.5v3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>; }
function PrintIcon() { return <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><rect x="2" y="5" width="9" height="6" rx="1" stroke="currentColor" strokeWidth="1.2"/><path d="M4 5V2h5v3M4 8h5M4 10h3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg>; }
function EngineIcon() { return <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="2.5" stroke="currentColor" strokeWidth="1.2"/><path d="M6.5 1v1.5M6.5 10v1.5M1 6.5h1.5M10 6.5h1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>; }
function OpenIcon() { return <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M7.5 2h3v3M10.5 2l-5 5M5 3H2a1 1 0 00-1 1v7a1 1 0 001 1h7a1 1 0 001-1V8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>; }
function CheckIcon() { return <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M1.5 5l2.5 2.5 4.5-5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function BroomIcon() { return <svg width="11" height="11" viewBox="0 0 11 11" fill="none"><path d="M2 9l5-5M8 2L6.5 3.5M3 8.5C2 9.5 1 10 1 10s.5-1 1.5-2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><circle cx="7.5" cy="2.5" r="1" stroke="currentColor" strokeWidth="1"/></svg>; }
function ZoneIcon() { return <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><rect x="1" y="1" width="3.5" height="3.5" rx="0.6" stroke="currentColor" strokeWidth="1"/><rect x="5.5" y="1" width="3.5" height="3.5" rx="0.6" stroke="currentColor" strokeWidth="1"/><rect x="1" y="5.5" width="3.5" height="3.5" rx="0.6" stroke="currentColor" strokeWidth="1"/><rect x="5.5" y="5.5" width="3.5" height="3.5" rx="0.6" stroke="currentColor" strokeWidth="1"/></svg>; }
function RRIcon() { return <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 2h6v4a3 3 0 01-6 0V2z" stroke="currentColor" strokeWidth="1"/><path d="M4 8.5V10M6 8.5V10M3 10h4" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/></svg>; }
function NoteIcon() { return <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 1h6a1 1 0 011 1v6L7 10H2a1 1 0 01-1-1V2a1 1 0 011-1z" stroke="currentColor" strokeWidth="1"/><path d="M3 3.5h4M3 5.5h2.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/></svg>; }
function FlagIcon() { return <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 1v8M2 1h5l-1.5 2.5L7 6H2" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function ChevronRightIcon() { return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function UploadIcon()  { return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1v7M3.5 3.5L6 1l2.5 2.5M2 9v1.5a.5.5 0 00.5.5h7a.5.5 0 00.5-.5V9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function UnlinkIcon()  { return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M4.5 7.5l3-3M3 5.5l-.5.5a2.12 2.12 0 003 3l.5-.5M9 6.5l.5-.5a2.12 2.12 0 00-3-3l-.5.5M2 2l8 8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>; }
function TrashIcon()   { return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 3h8M5 3V2h2v1M4 3l.5 7h3L8 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>; }
function FileIcon()    { return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M3 1h5l2 2v8a1 1 0 01-1 1H3a1 1 0 01-1-1V2a1 1 0 011-1zM7 1v3h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>; }

// ── Week Overview ─────────────────────────────────────────────────────────────

export default function WeekOverviewPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const weekId = params?.id ?? "";

  const { data: overview, error, isLoading } = useSWR(
    weekId ? `forge:week:${weekId}` : null,
    () => fetchWeekOverview(weekId),
    { revalidateOnFocus: true, refreshInterval: 15_000 }
  );

  const [ctxNight, setCtxNight] = useState<NightPlanningSnapshot | null>(null);
  const [ctxPos, setCtxPos] = useState<{ x: number; y: number } | undefined>();
  const [publishLoading, setPublishLoading] = useState(false);
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Engine state
  const [engineNightId, setEngineNightId] = useState<string | null>(null);
  const [engineToast, setEngineToast] = useState<{ result: EngineRunResult } | null>(null);
  const engineToastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Note editing state — keyed by night_id
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [noteValue, setNoteValue] = useState("");
  const [noteSaving, setNoteSaving] = useState(false);

  // Schedule management state
  const scheduleUploadRef = useRef<HTMLInputElement>(null);
  const [scheduleUploading, setScheduleUploading] = useState(false);
  const [scheduleMsg, setScheduleMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [scheduleDeleting, setScheduleDeleting] = useState(false);

  // Delete week state
  const [deleteWeekStep, setDeleteWeekStep] = useState<"idle" | "confirm">("idle");
  const [deleteWeekInput, setDeleteWeekInput] = useState("");
  const [deleteWeekLoading, setDeleteWeekLoading] = useState(false);

  const weekStatus = overview?.week.status ?? "draft";
  const isPublished = weekStatus === "published";

  async function handleScheduleUpload(file: File) {
    setScheduleUploading(true);
    setScheduleMsg(null);
    try {
      const result = await uploadScheduleForWeek(weekId, file);
      setScheduleMsg({ ok: true, text: `Linked: ${result.filename}` });
      globalMutate(`forge:week:${weekId}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setScheduleMsg({ ok: false, text: msg });
    } finally {
      setScheduleUploading(false);
      if (scheduleUploadRef.current) scheduleUploadRef.current.value = "";
    }
  }

  async function handleScheduleDelete() {
    if (scheduleDeleting) return;
    setScheduleDeleting(true);
    setScheduleMsg(null);
    try {
      await deleteWeekSchedule(weekId, false);
      setScheduleMsg({ ok: true, text: "Schedule unlinked" });
      globalMutate(`forge:week:${weekId}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to unlink schedule";
      setScheduleMsg({ ok: false, text: msg });
    } finally {
      setScheduleDeleting(false);
    }
  }

  async function handleDeleteWeek() {
    if (deleteWeekInput !== "DELETE" || deleteWeekLoading) return;
    setDeleteWeekLoading(true);
    try {
      await deleteWeek(weekId);
      router.replace("/");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete week";
      setScheduleMsg({ ok: false, text: msg });
      setDeleteWeekStep("idle");
      setDeleteWeekInput("");
    } finally {
      setDeleteWeekLoading(false);
    }
  }

  async function handlePublish() {
    if (publishLoading) return;
    const nextStatus = isPublished ? "draft" : "published";
    setPublishLoading(true);
    try {
      await patchWeekStatus(weekId, nextStatus);
      globalMutate(`forge:week:${weekId}`);
    } catch (err) {
      console.error("patchWeekStatus failed:", err);
    } finally {
      setPublishLoading(false);
    }
  }

  const handleRunEngineForNight = useCallback(async (nightId: string) => {
    if (engineNightId) return;
    setEngineNightId(nightId);
    setEngineToast(null);
    try {
      const result = await runEngineForNight(nightId);
      setEngineToast({ result });
      if (result.success) globalMutate(`forge:week:${weekId}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setEngineToast({ result: {
        success: false, scope: "night", updated: 0, locked_skipped: 0,
        unresolved_cleared: 0, unresolved: [], fill_rate: 0,
        week_ending: "", message: "", error: msg,
      }});
    } finally {
      setEngineNightId(null);
      if (engineToastTimer.current) clearTimeout(engineToastTimer.current);
      engineToastTimer.current = setTimeout(() => setEngineToast(null), 8_000);
    }
  }, [engineNightId, weekId]);

  async function saveNote(nightId: string) {
    setNoteSaving(true);
    try {
      await patchNightNote(nightId, noteValue.trim() || null);
      globalMutate(`forge:week:${weekId}`);
    } catch (err) {
      console.error("patchNightNote failed:", err);
    } finally {
      setNoteSaving(false);
      setEditingNoteId(null);
    }
  }

  function openCtx(e: React.MouseEvent, night: NightPlanningSnapshot) {
    e.preventDefault();
    setCtxNight(night);
    setCtxPos({ x: e.clientX, y: e.clientY });
  }

  const ctxActions: ContextAction[] = ctxNight
    ? [
        { label: "Open Planner", icon: <OpenIcon />, onClick: () => router.push(`/weeks/${weekId}/nights/${ctxNight.night_id}`) },
        { label: "Print Night",  icon: <PrintIcon />, onClick: () => window.open(`/api/forge/v1/print/night/${ctxNight.night_id}.pdf`, "_blank") },
        { label: "Run Engine",   icon: <EngineIcon />, onClick: () => handleRunEngineForNight(ctxNight.night_id), disabled: !!engineNightId },
        { label: "Assign TMs…",  icon: <UserPlusIcon />, onClick: () => router.push(`/weeks/${weekId}/nights/${ctxNight.night_id}`) },
      ]
    : [];

  if (isLoading) return <WeekOverviewSkeleton onBack={() => router.back()} />;

  if (error || !overview) {
    return (
      <div className="flex flex-col min-h-dvh bg-[#F5F5F7]">
        <GlcrHeader compact right={<button onClick={() => router.back()} className="h-8 px-3 rounded-lg bg-white/10 text-white/70 text-sm"><ArrowLeftIcon /></button>} />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-gray-400">
            <p className="text-lg font-semibold text-gray-600 mb-1">Week not found</p>
            <p className="text-sm">{error?.message ?? "Could not load week data"}</p>
          </div>
        </div>
      </div>
    );
  }

  const inRotationNights = overview.nights.filter((n) => n.in_rotation);
  const weekFillRate = inRotationNights.length > 0
    ? inRotationNights.reduce((s, n) => s + n.coverage_pct, 0) / inRotationNights.length / 100
    : 0;

  return (
    <div className="flex flex-col min-h-dvh bg-[#F5F5F7]">
      <GlcrHeader
        compact
        title={`Week ending ${formatWeekEnding(overview.week.week_ending)}`}
        right={
          <div className="flex items-center gap-2">
            <button
              className="flex items-center gap-1.5 h-8 px-3 rounded-lg text-sm font-medium
                         bg-white/10 text-white/80 hover:bg-white/20 transition-colors no-select"
              onClick={() => window.open(getWeekPrintUrl(weekId, "html"), "_blank")}
            >
              <PrintIcon />
              Print Book
            </button>
            <motion.button
              whileTap={{ scale: 0.95 }}
              disabled={publishLoading}
              onClick={handlePublish}
              className={cn(
                "flex items-center gap-1.5 h-8 px-3 rounded-lg text-sm font-semibold no-select transition-all duration-200",
                isPublished
                  ? "bg-green-500/20 text-green-300 border border-green-500/30 hover:bg-red-500/20 hover:text-red-300 hover:border-red-500/30"
                  : "bg-[#007AFF] text-white hover:bg-[#0056CC]"
              )}
              title={isPublished ? "Click to unpublish" : "Publish week"}
            >
              {publishLoading
                ? <span className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                : <PublishIcon />}
              {isPublished ? "Published" : "Publish Week"}
            </motion.button>
            <button
              onClick={() => router.back()}
              className="flex items-center gap-1 h-8 px-2.5 rounded-lg text-sm font-medium
                         bg-white/10 text-white/60 hover:bg-white/20 transition-colors no-select"
            >
              <ArrowLeftIcon />
            </button>
          </div>
        }
      />

      {/* Metrics strip */}
      <div className="bg-[#1A2340] border-t border-white/[0.08] px-6 pb-4">
        <WeekMetricsStrip overview={overview} fillRate={weekFillRate} />
      </div>

      {/* Schedule management bar */}
      <div className="px-6 py-3 bg-white border-b border-gray-100">
        {/* Hidden file input */}
        <input
          ref={scheduleUploadRef}
          type="file"
          accept=".xlsx"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleScheduleUpload(file);
          }}
        />

        <div className="flex items-center gap-3 flex-wrap">
          {/* File info */}
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <span className={cn(
              "flex items-center gap-1.5 text-[12px] font-medium",
              overview.week.schedule_path ? "text-gray-600" : "text-gray-400"
            )}>
              <FileIcon />
              {overview.week.schedule_path
                ? <span className="truncate max-w-[200px]" title={overview.week.schedule_path}>{overview.week.schedule_path}</span>
                : "No schedule linked"}
            </span>
            {scheduleMsg && (
              <span className={cn(
                "text-[11px] font-medium",
                scheduleMsg.ok ? "text-emerald-600" : "text-red-500"
              )}>
                {scheduleMsg.text}
              </span>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => scheduleUploadRef.current?.click()}
              disabled={scheduleUploading}
              className="flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-[11px] font-semibold
                         bg-blue-50 text-blue-600 hover:bg-blue-100 disabled:opacity-50 transition-colors"
            >
              {scheduleUploading
                ? <span className="w-3 h-3 border-2 border-blue-300 border-t-blue-600 rounded-full animate-spin" />
                : <UploadIcon />}
              {overview.week.schedule_path ? "Re-upload" : "Upload"}
            </button>

            {overview.week.schedule_path && (
              <button
                onClick={handleScheduleDelete}
                disabled={scheduleDeleting}
                className="flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-[11px] font-semibold
                           bg-gray-100 text-gray-500 hover:bg-gray-200 disabled:opacity-50 transition-colors"
              >
                {scheduleDeleting
                  ? <span className="w-3 h-3 border-2 border-gray-300 border-t-gray-500 rounded-full animate-spin" />
                  : <UnlinkIcon />}
                Unlink
              </button>
            )}

            {/* Delete week — danger zone */}
            {deleteWeekStep === "idle" && (
              <button
                onClick={() => setDeleteWeekStep("confirm")}
                className="flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-[11px] font-semibold
                           text-red-400 hover:bg-red-50 hover:text-red-600 transition-colors"
              >
                <TrashIcon />
                Delete Week
              </button>
            )}
          </div>
        </div>

        {/* Delete week confirmation */}
        <AnimatePresence>
          {deleteWeekStep !== "idle" && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="mt-2.5 p-3 rounded-xl bg-red-50 border border-red-200 flex flex-col gap-2">
                <p className="text-[12px] text-red-700 font-medium">
                  ⚠️ This permanently deletes the week and all nights, assignments, and overlaps. Type <strong>DELETE</strong> to confirm.
                </p>
                <div className="flex items-center gap-2">
                  <input
                    autoFocus
                    type="text"
                    value={deleteWeekInput}
                    onChange={(e) => setDeleteWeekInput(e.target.value)}
                    placeholder="Type DELETE to confirm"
                    className="flex-1 h-8 px-2.5 rounded-lg text-[12px] border border-red-300
                               bg-white text-red-700 placeholder:text-red-300 outline-none
                               focus:border-red-500 font-mono"
                  />
                  <button
                    onClick={handleDeleteWeek}
                    disabled={deleteWeekInput !== "DELETE" || deleteWeekLoading}
                    className="h-8 px-3 rounded-lg text-[12px] font-semibold bg-red-600 text-white
                               hover:bg-red-700 disabled:opacity-40 transition-colors"
                  >
                    {deleteWeekLoading ? "Deleting…" : "Delete"}
                  </button>
                  <button
                    onClick={() => { setDeleteWeekStep("idle"); setDeleteWeekInput(""); }}
                    className="h-8 px-3 rounded-lg text-[12px] font-semibold bg-white text-gray-500
                               border border-gray-200 hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <main className="flex-1 px-6 py-6 overflow-hidden">
        <h2 className="section-header text-gray-500 mb-4">Nights this week</h2>

        <div className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory -mx-1 px-1">
          {overview.nights.map((night, i) => (
            <DayCard
              key={night.night_id}
              night={night}
              index={i}
              weekId={weekId}
              engineRunning={engineNightId === night.night_id}
              editingNote={editingNoteId === night.night_id}
              noteValue={editingNoteId === night.night_id ? noteValue : (night.note ?? "")}
              noteSaving={noteSaving}
              onContextMenu={(e) => openCtx(e, night)}
              onLongPressStart={(e) => {
                longPressTimer.current = setTimeout(() => openCtx(e, night), 500);
              }}
              onLongPressEnd={() => { if (longPressTimer.current) clearTimeout(longPressTimer.current); }}
              onOpen={() => router.push(`/weeks/${weekId}/nights/${night.night_id}`)}
              onNoteEdit={() => { setEditingNoteId(night.night_id); setNoteValue(night.note ?? ""); }}
              onNoteChange={setNoteValue}
              onNoteSave={() => saveNote(night.night_id)}
              onNoteCancel={() => setEditingNoteId(null)}
            />
          ))}
        </div>
      </main>

      <ContextMenu
        open={!!ctxNight}
        onClose={() => { setCtxNight(null); setCtxPos(undefined); }}
        actions={ctxActions}
        anchorPos={ctxPos}
      />

      {/* Engine Run Toast */}
      <AnimatePresence>
        {engineToast && (
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            transition={{ type: "spring", damping: 22, stiffness: 320 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-[min(420px,calc(100vw-32px))]"
          >
            <div className={cn(
              "rounded-2xl px-4 py-3.5 shadow-2xl flex items-start gap-3",
              engineToast.result.success
                ? "bg-[#1C1C1E] border border-white/10"
                : "bg-red-950 border border-red-800/60"
            )}>
              <div className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-0.5",
                engineToast.result.success ? "bg-green-500/20" : "bg-red-500/20"
              )}>
                {engineToast.result.success ? (
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M2.5 7l3 3 6-6" stroke="#34C759" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 4v4M7 10v.5" stroke="#FF3B30" strokeWidth="1.8" strokeLinecap="round"/>
                    <circle cx="7" cy="7" r="5.5" stroke="#FF3B30" strokeWidth="1.3"/>
                  </svg>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className={cn("text-[13px] font-semibold", engineToast.result.success ? "text-white" : "text-red-200")}>
                  {engineToast.result.success ? "Engine run complete" : "Engine run failed"}
                </div>
                <div className={cn("text-[12px] mt-0.5", engineToast.result.success ? "text-white/60" : "text-red-300/80")}>
                  {engineToast.result.success ? engineToast.result.message : engineToast.result.error ?? "Unknown error"}
                </div>
              </div>
              <button onClick={() => setEngineToast(null)} className="shrink-0 text-white/30 hover:text-white/70 mt-0.5">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Week Metrics Strip ────────────────────────────────────────────────────────

function WeekMetricsStrip({ overview, fillRate }: { overview: WeeklyPlanningOverviewResponse; fillRate: number }) {
  const pct = Math.round(fillRate * 100);
  const items = [
    { label: "Fill Rate",   value: `${pct}%`,                              highlight: true },
    { label: "Assigned",    value: String(overview.metrics.total_assignments) },
    { label: "Gaps",        value: String(overview.metrics.total_gaps),    warn: overview.metrics.total_gaps > 0 },
    { label: "Gap Nights",  value: String(overview.metrics.nights_with_gaps), warn: overview.metrics.nights_with_gaps > 0 },
    { label: "Overlaps",    value: String(overview.metrics.multi_area_overlap_count) },
    { label: "Overrides",   value: String(overview.metrics.active_override_count) },
  ];
  return (
    <div className="flex items-center gap-6 flex-wrap">
      {items.map((m) => (
        <div key={m.label} className="flex flex-col">
          <span className={cn("text-xl font-bold",
            m.highlight ? "text-[#C9A84C]" : m.warn ? "text-red-400" : "text-white"
          )}>
            {m.value}
          </span>
          <span className="text-[11px] text-white/40 font-medium uppercase tracking-wide">{m.label}</span>
        </div>
      ))}
    </div>
  );
}

// ── Day Card ──────────────────────────────────────────────────────────────────

interface DayCardProps {
  night: NightPlanningSnapshot;
  index: number;
  weekId: string;
  engineRunning: boolean;
  editingNote: boolean;
  noteValue: string;
  noteSaving: boolean;
  onContextMenu: (e: React.MouseEvent) => void;
  onLongPressStart: (e: React.PointerEvent) => void;
  onLongPressEnd: () => void;
  onOpen: () => void;
  onNoteEdit: () => void;
  onNoteChange: (v: string) => void;
  onNoteSave: () => void;
  onNoteCancel: () => void;
}

function DayCard({
  night, index, engineRunning,
  editingNote, noteValue, noteSaving,
  onContextMenu, onLongPressStart, onLongPressEnd,
  onOpen, onNoteEdit, onNoteChange, onNoteSave, onNoteCancel,
}: DayCardProps) {
  const fillRate    = coveragePctToRate(night.coverage_pct);
  const accentColor = fillRate >= 0.9 ? "#34C759" : fillRate >= 0.75 ? "#FF9500" : "#FF3B30";

  // Operational gap = how many TMs short of target (not raw DB rows)
  const target = night.target_capacity ?? 0;
  const opGap  = Math.max(0, target - night.filled_slots);

  // Sweeper pills
  const sweepersComplete = night.sweeper_main_filled && night.sweeper_sr_filled;
  const sweepersPartial  = night.sweeper_main_filled || night.sweeper_sr_filled;
  const missingCount     = (night.sweeper_main_filled ? 0 : 1) + (night.sweeper_sr_filled ? 0 : 1);

  // Flags
  const flags: { text: string; color: string }[] = [];
  if (opGap > 0)                             flags.push({ text: `${opGap} gap${opGap !== 1 ? "s" : ""}`, color: "text-red-500" });
  if (night.override_count > 0)              flags.push({ text: `${night.override_count} override${night.override_count !== 1 ? "s" : ""}`, color: "text-orange-500" });
  if (night.multi_area_overlap_count > 0)    flags.push({ text: `${night.multi_area_overlap_count} overlap${night.multi_area_overlap_count !== 1 ? "s" : ""}`, color: "text-blue-500" });

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
      onContextMenu={onContextMenu}
      onPointerDown={onLongPressStart}
      onPointerUp={onLongPressEnd}
      onPointerCancel={onLongPressEnd}
      className="relative snap-start shrink-0 w-52 rounded-3xl bg-white shadow-card cursor-pointer no-select
                 transition-shadow duration-200 overflow-hidden flex flex-col"
      onClick={(e) => {
        // Don't navigate if clicking the note area or its buttons
        if ((e.target as HTMLElement).closest("[data-note-area]")) return;
        onOpen();
      }}
    >
      {/* Accent bar */}
      <div className="h-[5px] w-full shrink-0" style={{ backgroundColor: accentColor }} />

      <div className="p-4 flex flex-col gap-3 flex-1">

        {/* Day + date */}
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-widest text-gray-400">{night.day_name}</div>
          <div className="text-[13px] text-gray-500 mt-0.5">
            {new Date(`${night.night_date}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
          </div>
        </div>

        {/* Fill ring + counts */}
        <div className="flex items-center gap-3">
          <FillRing rate={fillRate} size={52} strokeWidth={5} />
          <div>
            <div className="text-[13px] font-semibold text-gray-700">
              {night.filled_slots} / {target}
            </div>
            <div className="text-[11px] text-gray-400">filled</div>
          </div>
        </div>

        {/* Sweeper pill */}
        <div className={cn(
          "flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-[11px] font-semibold w-fit",
          sweepersComplete
            ? "bg-emerald-50 text-emerald-600"
            : sweepersPartial
            ? "bg-amber-50 text-amber-600"
            : "bg-red-50 text-red-500"
        )}>
          <BroomIcon />
          {sweepersComplete
            ? <><CheckIcon /> Sweepers</>
            : missingCount === 2
            ? "Missing Sweepers"
            : "Missing Sweeper"}
        </div>

        {/* Coverage breakdown */}
        <div className="flex gap-2">
          {night.zone_total > 0 && (
            <div className="flex items-center gap-1 text-[11px] text-gray-400">
              <ZoneIcon />
              <span className={night.zone_filled < night.zone_total ? "text-orange-500 font-medium" : "text-gray-500"}>
                {night.zone_filled}/{night.zone_total}
              </span>
              <span>zones</span>
            </div>
          )}
          {night.rr_total > 0 && (
            <div className="flex items-center gap-1 text-[11px] text-gray-400">
              <RRIcon />
              <span className={night.rr_filled < night.rr_total ? "text-orange-500 font-medium" : "text-gray-500"}>
                {night.rr_filled}/{night.rr_total}
              </span>
              <span>RR</span>
            </div>
          )}
        </div>

        {/* Flags */}
        {flags.length > 0 && (
          <div className="border-t border-gray-100 pt-2.5 flex flex-col gap-1">
            <div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-gray-300 mb-0.5">
              <FlagIcon />
              Flags
            </div>
            {flags.map((f, i) => (
              <div key={i} className={cn("text-[11px] font-medium flex items-center gap-1.5", f.color)}>
                <span className="w-1 h-1 rounded-full bg-current" />
                {f.text}
              </div>
            ))}
          </div>
        )}

        {/* Note section */}
        <div
          data-note-area="true"
          className="border-t border-gray-100 pt-2.5"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-gray-300 mb-1.5">
            <NoteIcon />
            Note
          </div>
          {editingNote ? (
            <div className="flex flex-col gap-1.5">
              <textarea
                autoFocus
                value={noteValue}
                onChange={(e) => onNoteChange(e.target.value)}
                placeholder="Add a note…"
                rows={3}
                className="w-full text-[12px] text-gray-700 bg-gray-50 rounded-xl px-2.5 py-2
                           border border-gray-200 outline-none focus:border-[#C9A84C] resize-none
                           placeholder:text-gray-300"
              />
              <div className="flex gap-1.5">
                <button
                  onClick={onNoteSave}
                  disabled={noteSaving}
                  className="flex-1 h-7 rounded-lg bg-[#C9A84C] text-white text-[11px] font-semibold
                             hover:bg-[#b8953f] disabled:opacity-50 transition-colors"
                >
                  {noteSaving ? "Saving…" : "Save"}
                </button>
                <button
                  onClick={onNoteCancel}
                  className="flex-1 h-7 rounded-lg bg-gray-100 text-gray-500 text-[11px] font-semibold
                             hover:bg-gray-200 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : night.note ? (
            <p
              className="text-[12px] text-gray-500 leading-snug cursor-text hover:text-gray-700"
              onClick={onNoteEdit}
            >
              {night.note}
            </p>
          ) : (
            <button
              onClick={onNoteEdit}
              className="text-[11px] text-gray-300 hover:text-gray-400 transition-colors"
            >
              + Add note…
            </button>
          )}
        </div>

      </div>

      {/* Open planner footer — always visible */}
      <button
        onClick={(e) => { e.stopPropagation(); onOpen(); }}
        className="flex items-center justify-between px-4 py-3 border-t border-gray-100
                   text-[12px] font-semibold text-[#007AFF] hover:bg-blue-50
                   transition-colors no-select shrink-0"
      >
        <span>Open Planner</span>
        <ChevronRightIcon />
      </button>

      {/* Engine running spinner overlay */}
      {engineRunning && (
        <div className="absolute inset-0 bg-white/80 flex items-center justify-center rounded-3xl">
          <div className="w-6 h-6 border-2 border-gray-200 border-t-[#C9A84C] rounded-full animate-spin" />
        </div>
      )}
    </motion.div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function WeekOverviewSkeleton({ onBack }: { onBack: () => void }) {
  return (
    <div className="flex flex-col min-h-dvh bg-[#F5F5F7]">
      <GlcrHeader compact right={
        <button onClick={onBack} className="h-8 px-2.5 rounded-lg bg-white/10 text-white/60"><ArrowLeftIcon /></button>
      } />
      <div className="bg-[#1A2340] border-t border-white/[0.08] h-14" />
      <div className="px-6 py-6 flex gap-4 overflow-hidden">
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className="w-52 h-80 rounded-3xl shimmer-bg shrink-0" style={{ animationDelay: `${i * 0.06}s` }} />
        ))}
      </div>
    </div>
  );
}
