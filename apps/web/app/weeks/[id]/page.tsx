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
  runEngineForNight,
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
  const [hoveredNight, setHoveredNight] = useState<string | null>(null);
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Engine state
  const [engineNightId, setEngineNightId] = useState<string | null>(null);
  const [engineToast, setEngineToast] = useState<{ result: EngineRunResult } | null>(null);
  const engineToastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync published state from server
  const weekStatus = overview?.week.status ?? "draft";
  const isPublished = weekStatus === "published";

  async function handlePublish() {
    if (publishLoading) return;
    const nextStatus = isPublished ? "draft" : "published";
    setPublishLoading(true);
    try {
      await patchWeekStatus(weekId, nextStatus);
      // Bust SWR cache so header badge and status update immediately
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

  function openCtx(e: React.MouseEvent, night: NightPlanningSnapshot) {
    e.preventDefault();
    setCtxNight(night);
    setCtxPos({ x: e.clientX, y: e.clientY });
  }

  const ctxActions: ContextAction[] = ctxNight
    ? [
        { label: "Open Planner", icon: <OpenIcon />, onClick: () => router.push(`/weeks/${weekId}/nights/${ctxNight.night_id}`) },
        { label: "Print Night", icon: <PrintIcon />, onClick: () => window.open(`/api/forge/v1/print/night/${ctxNight.night_id}.pdf`, "_blank") },
        { label: "Run Engine", icon: <EngineIcon />, onClick: () => handleRunEngineForNight(ctxNight.night_id), disabled: !!engineNightId },
        { label: "Assign TMs…", icon: <UserPlusIcon />, onClick: () => router.push(`/weeks/${weekId}/nights/${ctxNight.night_id}`) },
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

  // Compute fill rate as the average of per-night coverage_pct (which uses
  // per-day target capacity on the backend, not raw slot counts).
  // Only in-rotation nights count; convert 0-100 → 0-1 for FillRing.
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

      <main className="flex-1 px-6 py-6 overflow-hidden">
        <h2 className="section-header text-gray-500 mb-4">Nights this week</h2>

        {/* Planning notes */}
        <AnimatePresence>
          {overview.planning_notes.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="flex flex-wrap gap-2 mb-4"
            >
              {overview.planning_notes.slice(0, 3).map((note, i) => (
                <div
                  key={i}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[12px] font-medium",
                    note.note_kind === "gap" && "bg-red-50 text-red-600",
                    note.note_kind === "override" && "bg-orange-50 text-orange-600",
                    note.note_kind === "overlap" && "bg-blue-50 text-blue-600",
                    note.note_kind === "info" && "bg-gray-100 text-gray-600",
                  )}
                >
                  <span className="font-semibold">{note.day_name}:</span>
                  {note.note_text}
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory -mx-1 px-1">
          {overview.nights.map((night, i) => (
            <DayCard
              key={night.night_id}
              night={night}
              index={i}
              weekId={weekId}
              isHovered={hoveredNight === night.night_id}
              onHover={(id) => setHoveredNight(id)}
              onHoverEnd={() => setHoveredNight(null)}
              onContextMenu={(e) => openCtx(e, night)}
              onLongPressStart={(e) => {
                longPressTimer.current = setTimeout(() => openCtx(e, night), 500);
              }}
              onLongPressEnd={() => { if (longPressTimer.current) clearTimeout(longPressTimer.current); }}
              onOpen={() => router.push(`/weeks/${weekId}/nights/${night.night_id}`)}
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

      {/* ── Engine Run Toast ─────────────────────────────────────── */}
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
                <div className={cn(
                  "text-[13px] font-semibold leading-snug",
                  engineToast.result.success ? "text-white" : "text-red-200"
                )}>
                  {engineToast.result.success ? "Engine run complete" : "Engine run failed"}
                </div>
                <div className={cn(
                  "text-[12px] mt-0.5 leading-snug",
                  engineToast.result.success ? "text-white/60" : "text-red-300/80"
                )}>
                  {engineToast.result.success
                    ? engineToast.result.message
                    : engineToast.result.error ?? "Unknown error"}
                </div>
                {engineToast.result.success && engineToast.result.fill_rate > 0 && (
                  <div className="mt-1.5 flex items-center gap-2">
                    <div className="h-1 flex-1 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-400 rounded-full transition-all duration-700"
                        style={{ width: `${engineToast.result.fill_rate}%` }}
                      />
                    </div>
                    <span className="text-[11px] text-white/50 shrink-0">
                      {engineToast.result.fill_rate.toFixed(0)}% filled
                    </span>
                  </div>
                )}
              </div>
              <button
                onClick={() => setEngineToast(null)}
                className="shrink-0 text-white/30 hover:text-white/70 transition-colors mt-0.5"
              >
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
  isHovered: boolean;
  onHover: (id: string) => void;
  onHoverEnd: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
  onLongPressStart: (e: React.PointerEvent) => void;
  onLongPressEnd: () => void;
  onOpen: () => void;
}

function DayCard({ night, index, isHovered, onHover, onHoverEnd, onContextMenu, onLongPressStart, onLongPressEnd, onOpen }: DayCardProps) {
  const [doubleTapMode, setDoubleTapMode] = useState<"compact" | "expanded">("compact");
  const lastTap = useRef(0);

  const fillRate = coveragePctToRate(night.coverage_pct);
  const accentColor = fillRate >= 0.9 ? "#34C759" : fillRate >= 0.75 ? "#FF9500" : "#FF3B30";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
      onContextMenu={onContextMenu}
      onPointerDown={onLongPressStart}
      onPointerUp={onLongPressEnd}
      onPointerCancel={onLongPressEnd}
      onMouseEnter={() => onHover(night.night_id)}
      onMouseLeave={onHoverEnd}
      onClick={() => {
        const isDoubleTap = Date.now() - lastTap.current < 300;
        lastTap.current = Date.now();
        if (isDoubleTap) {
          setDoubleTapMode((m) => (m === "compact" ? "expanded" : "compact"));
        } else {
          onOpen();
        }
      }}
      className={cn(
        "relative snap-start shrink-0 rounded-3xl bg-white shadow-card cursor-pointer no-select",
        "transition-all duration-200 overflow-hidden",
        doubleTapMode === "expanded" ? "w-64" : "w-44"
      )}
      style={{ boxShadow: isHovered ? "0 8px 28px rgba(0,0,0,0.12), 0 0 0 2px #007AFF22" : undefined }}
    >
      <div className="h-1.5 w-full" style={{ backgroundColor: accentColor }} />

      <div className="p-4 flex flex-col gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-widest text-gray-400">{night.day_name}</div>
          <div className="text-[13px] text-gray-500 mt-0.5">
            {new Date(`${night.night_date}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <FillRing rate={fillRate} size={56} strokeWidth={5} />
          <div>
            <div className="text-[13px] font-semibold text-gray-700">{night.filled_slots} filled</div>
            <div className="text-[12px] text-gray-400">{night.gap_count} open</div>
          </div>
        </div>

        {night.reoptimize_recommended && (
          <div className="flex items-center gap-1.5 bg-red-50 rounded-lg px-2.5 py-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
            <span className="text-[11px] font-semibold text-red-500">
              {night.gap_count} gap{night.gap_count !== 1 ? "s" : ""}
            </span>
          </div>
        )}

        <AnimatePresence>
          {doubleTapMode === "expanded" && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="text-[12px] text-gray-400 overflow-hidden space-y-1"
            >
              {night.override_count > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-400" />
                  {night.override_count} override{night.override_count !== 1 ? "s" : ""}
                </div>
              )}
              {night.multi_area_overlap_count > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                  {night.multi_area_overlap_count} overlap{night.multi_area_overlap_count !== 1 ? "s" : ""}
                </div>
              )}
              <div className="text-[11px]">{night.total_slots} total slots</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {isHovered && (
          <motion.div
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 6 }}
            transition={{ duration: 0.14 }}
            className="absolute bottom-3 left-3 right-3 flex justify-center"
          >
            <button
              onClick={(e) => { e.stopPropagation(); onOpen(); }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#007AFF] text-white
                         text-[12px] font-semibold shadow-md hover:bg-[#0056CC] transition-colors no-select"
            >
              <UserPlusIcon />
              Open Planner
            </button>
          </motion.div>
        )}
      </AnimatePresence>
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
          <div key={i} className="w-44 h-52 rounded-3xl shimmer-bg shrink-0" style={{ animationDelay: `${i * 0.06}s` }} />
        ))}
      </div>
    </div>
  );
}
