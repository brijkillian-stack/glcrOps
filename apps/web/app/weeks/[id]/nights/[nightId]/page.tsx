"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter, useParams } from "next/navigation";
import useSWR from "swr";
import { GlcrHeader } from "@/components/ui/GlcrHeader";
import { FillRing } from "@/components/ui/FillRing";
import { ContextMenu, type ContextAction } from "@/components/ui/ContextMenu";
import { SyncBar } from "@/components/ui/SyncBar";
import { useNightPlacements, useRealtimeSync, type TMAssignment, type BreakWave, type BreakGroupSlot, type GroupId } from "@/lib/sync";
import { fetchActiveTMs, fetchZoneTasks, patchSlotTasks, runEngineForNight, type ActiveTM, type ZoneTask, type EngineRunResult } from "@/lib/forge-api";
import { cn, groupColor, zoneAccentColor, rrSideTint } from "@/lib/utils";
import { formatBreakTime } from "@/lib/shift-date";

// ── Icons ─────────────────────────────────────────────────────────────────────

function ArrowLeftIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}
function PrintIcon() {
  return <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><rect x="2" y="5" width="9" height="6" rx="1" stroke="currentColor" strokeWidth="1.2"/><path d="M4 5V2h5v3M4 8h5M4 10h3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg>;
}
function EngineIcon() {
  return <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="2.5" stroke="currentColor" strokeWidth="1.2"/><path d="M6.5 1v1.5M6.5 10v1.5M1 6.5h1.5M10 6.5h1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>;
}
function WaveIcon() {
  return <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M1 6.5c1-2 2-3 3-1s2 3 3 1 2-3 3-1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>;
}
function UserIcon({ initials }: { initials: string }) {
  return (
    <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center
                    text-[11px] font-bold text-gray-600 shrink-0 ring-1 ring-gray-200">
      {initials}
    </div>
  );
}
function EmptySlotIcon() {
  return (
    <div className="w-8 h-8 rounded-full border-2 border-dashed border-gray-200
                    flex items-center justify-center shrink-0">
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
        <path d="M5 2v6M2 5h6" stroke="#CBD5E1" strokeWidth="1.4" strokeLinecap="round"/>
      </svg>
    </div>
  );
}
function TaskDotIcon() {
  return <div className="w-1.5 h-1.5 rounded-full bg-current opacity-50 shrink-0 mt-0.5" />;
}
function ChevronRightIcon() {
  return <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

// ── Coverage helpers ──────────────────────────────────────────────────────────

/** True for tasks that represent cross-area coverage ("and Zone X", "and Restroom X"). */
function isCoverageTask(t: string): boolean {
  const l = t.toLowerCase();
  return l.startsWith("and zone") || l.startsWith("and restroom") || l.startsWith("and aux") || l.startsWith("and admin");
}

/**
 * Build the canonical coverage task string for a slot that needs coverage.
 *   Zone 3           → "and Zone 3"
 *   RR 6 (mens)      → "and Restroom 6 (Men's)"
 *   RR 1 + 2 (womens)→ "and Restroom 1 + 2 (Women's)"
 *   Admin            → "and Admin"
 */
function buildCoverageTaskName(slot: TMAssignment): string {
  const label = slot.zone_label ?? "";
  if (slot.zone_type === "restroom") {
    const num = label.replace(/^RR\s*/i, "").trim();
    const side = slot.rr_side === "mens" ? "Men's" : slot.rr_side === "womens" ? "Women's" : null;
    return side ? `and Restroom ${num} (${side})` : `and Restroom ${num}`;
  }
  return `and ${label}`;
}

// ── Break schedule constants (mirrors Python _BREAK_SCHEDULE in night.py) ─────

/** [groupNum][waveNum] → [start_24h, end_24h, duration_min] */
const BREAK_TIMES: Record<string, Record<string, [string, string, number]>> = {
  "1": { "1": ["00:45", "01:00", 15], "2": ["02:30", "03:00", 30], "3": ["05:00", "05:15", 15] },
  "2": { "1": ["01:00", "01:15", 15], "2": ["03:00", "03:30", 30], "3": ["05:00", "05:15", 15] },
  "3": { "1": ["01:15", "01:30", 15], "2": ["03:30", "04:00", 30], "3": ["05:15", "05:30", 15] },
};
const WAVE_LABELS: Record<string, string> = {
  "1": "First Break", "2": "Main Break", "3": "Last Break",
};

// ── Daily Planner ─────────────────────────────────────────────────────────────

export default function DailyPlannerPage() {
  const router = useRouter();
  const params = useParams<{ id: string; nightId: string }>();
  const weekId  = params?.id ?? "";
  const nightId = params?.nightId ?? "n1";

  // ← Shared sync hook — same key used by Break Sheet view
  const { data, isLoading, lastSynced, assignTM, moveBreakTM, refresh } =
    useNightPlacements(nightId);

  // Wire Supabase Realtime when ready (no-op stub for now)
  useRealtimeSync(nightId);

  const [activeSection, setActiveSection] = useState<"zones" | "breaks">("zones");
  const [ctxSlot, setCtxSlot] = useState<TMAssignment | null>(null);
  const [ctxPos, setCtxPos] = useState<{ x: number; y: number } | undefined>();
  const [pencilHoverSlot, setPencilHoverSlot] = useState<string | null>(null);
  const [pickerSlot, setPickerSlot]     = useState<TMAssignment | null>(null);
  const [taskSlot, setTaskSlot]         = useState<TMAssignment | null>(null);
  const [coverageSlot, setCoverageSlot] = useState<TMAssignment | null>(null);

  // ── Engine run state ──────────────────────────────────────────────────────
  const [engineRunning, setEngineRunning] = useState(false);
  const [engineToast, setEngineToast]     = useState<{ result: EngineRunResult } | null>(null);
  const engineToastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function handleRunEngine() {
    if (engineRunning) return;
    setEngineRunning(true);
    setEngineToast(null);
    try {
      const result = await runEngineForNight(nightId);
      setEngineToast({ result });
      if (result.success) {
        // Refresh placements so the grid updates immediately
        refresh();
      }
      // Auto-dismiss after 8 s
      if (engineToastTimer.current) clearTimeout(engineToastTimer.current);
      engineToastTimer.current = setTimeout(() => setEngineToast(null), 8_000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setEngineToast({
        result: {
          success: false, scope: "night", updated: 0, locked_skipped: 0,
          unresolved_cleared: 0, unresolved: [], fill_rate: 0,
          week_ending: "", message: "", error: msg,
        },
      });
      if (engineToastTimer.current) clearTimeout(engineToastTimer.current);
      engineToastTimer.current = setTimeout(() => setEngineToast(null), 10_000);
    } finally {
      setEngineRunning(false);
    }
  }

  // TM roster — cached by SWR, refreshes every 10 min
  const { data: tmRoster } = useSWR("forge:tms:active", () => fetchActiveTMs(), {
    revalidateOnFocus: false,
    dedupingInterval: 600_000,
  });


  // Separate zone types
  const zones     = data?.placements.filter((p) => p.zone_type === "zone")      ?? [];
  const restrooms = data?.placements.filter((p) => p.zone_type === "restroom")  ?? [];
  const auxiliary = data?.placements.filter((p) => p.zone_type === "auxiliary") ?? [];

  /**
   * Derive break waves from zone placements (same source as the print deployment book).
   * This populates correctly even before the engine runs — the engine populates
   * break_assignments, but zone_assignments.group_num (= placements[].group) is always set.
   * Every TM appears in all 3 waves under their correct group, exactly like the print.
   */
  const breakWaves = useMemo((): BreakWave[] => {
    const placements = data?.placements ?? [];

    // Accumulate TMs by group
    const groupedTMs: Record<string, { tm_ids: string[]; tm_names: string[] }> = {
      "1": { tm_ids: [], tm_names: [] },
      "2": { tm_ids: [], tm_names: [] },
      "3": { tm_ids: [], tm_names: [] },
    };
    for (const p of placements) {
      if (p.tm_id && p.tm_name && p.group && p.group in groupedTMs) {
        groupedTMs[p.group].tm_ids.push(p.tm_id);
        groupedTMs[p.group].tm_names.push(p.tm_name);
      }
    }

    return (["1", "2", "3"] as GroupId[]).map((waveId) => ({
      wave: waveId,
      label: WAVE_LABELS[waveId],
      groups: (["1", "2", "3"] as GroupId[]).map((grpId) => {
        const [start, end, dur] = BREAK_TIMES[grpId][waveId];
        return {
          group: grpId as GroupId,
          start_time: start,
          end_time: end,
          duration_min: dur,
          tm_ids:   [...groupedTMs[grpId].tm_ids],
          tm_names: [...groupedTMs[grpId].tm_names],
        };
      }),
    }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.placements]);

  /**
   * Set of lowercased coverage task strings that are currently assigned to ANY slot.
   * Used to show a "covered" indicator on empty cards whose coverage task is claimed.
   */
  const coveredBySet = useMemo(() => {
    const s = new Set<string>();
    (data?.placements ?? []).forEach((p) => {
      (p.tasks ?? []).forEach((t) => {
        if (isCoverageTask(t)) s.add(t.toLowerCase());
      });
    });
    return s;
  }, [data?.placements]);



  function openCtx(e: React.MouseEvent, slot: TMAssignment) {
    e.preventDefault();
    setCtxSlot(slot);
    setCtxPos({ x: e.clientX, y: e.clientY });
  }

  function openPicker(slot: TMAssignment) {
    setCtxSlot(null);
    setCtxPos(undefined);
    setPickerSlot(slot);
  }

  function openTaskPicker(slot: TMAssignment) {
    setCtxSlot(null);
    setCtxPos(undefined);
    setTaskSlot(slot);
  }

  function openCoveragePicker(slot: TMAssignment) {
    setCtxSlot(null);
    setCtxPos(undefined);
    setCoverageSlot(slot);
  }

  async function addCoverage(coveringSlot: TMAssignment) {
    if (!coverageSlot) return;
    const taskName = buildCoverageTaskName(coverageSlot);
    const existing = coveringSlot.tasks ?? [];
    if (existing.includes(taskName)) return;  // already assigned
    try {
      await patchSlotTasks(nightId, coveringSlot.slot_id, [...existing, taskName]);
      refresh();
    } catch (err) {
      console.error("addCoverage failed:", err);
    }
    setCoverageSlot(null);
  }

  const ctxActions: ContextAction[] = ctxSlot
    ? [
        {
          label: ctxSlot.tm_id ? "Reassign TM" : "Assign TM",
          icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="5" cy="4" r="3" stroke="currentColor" strokeWidth="1.2"/><path d="M1 13c0-2 2-3.5 4-3.5s4 1.5 4 3.5M10 5h4M12 3v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
          onClick: () => openPicker(ctxSlot),
        },
        // ← Add Coverage — only surfaces on unassigned slots
        ...(!ctxSlot.tm_id
          ? [{
              label: "Add Coverage",
              icon: (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M5.5 8.5L8.5 5.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                  <path d="M7.5 4.5L8.5 3.5a2 2 0 012.8 2.8L10 7.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M6.5 9.5L5.5 10.5a2 2 0 01-2.8-2.8L4 6.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              ),
              onClick: () => openCoveragePicker(ctxSlot),
            }]
          : []),
        {
          label: "Clear slot",
          icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>,
          onClick: () => { assignTM(ctxSlot.slot_id, null); setCtxSlot(null); },
          disabled: !ctxSlot.tm_id,
        },
        {
          label: "Assign Tasks",
          icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="2" y="2" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.2"/><path d="M4 7h6M4 5h4M4 9h3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg>,
          onClick: () => openTaskPicker(ctxSlot),
        },
        {
          label: `Move to Break 1`,
          icon: <WaveIcon />,
          onClick: () => { ctxSlot.tm_id && moveBreakTM(ctxSlot.tm_id, ctxSlot.tm_name ?? "", ctxSlot.group ?? "1", "1"); setCtxSlot(null); },
          disabled: !ctxSlot.tm_id,
        },
      ]
    : [];

  if (isLoading) {
    return <PlannerSkeleton weekId={weekId} onBack={() => router.back()} />;
  }

  return (
    <div className="flex flex-col min-h-dvh bg-[#F5F5F7]">
      {/* Header */}
      <GlcrHeader
        compact
        title={`${data?.day_name ?? "Night"} · ${data?.date ?? ""}`}
        right={
          <div className="flex items-center gap-2">
            <SyncBar lastSynced={lastSynced} onRefresh={refresh} />

            <button
              className="flex items-center gap-1.5 h-8 px-3 rounded-lg text-[12px] font-medium
                         bg-white/10 text-white/80 hover:bg-white/20 transition-colors no-select"
              onClick={() =>
                window.open(`/api/forge/v1/print/night/${nightId}.html`, "_blank")
              }
            >
              <PrintIcon />
              Print Day
            </button>
            <button
              className={cn(
                "flex items-center gap-1.5 h-8 px-3 rounded-lg text-[12px] font-medium transition-colors no-select",
                engineRunning
                  ? "bg-amber-500/20 text-amber-300 cursor-wait"
                  : "bg-white/10 text-white/80 hover:bg-white/20",
              )}
              onClick={handleRunEngine}
              disabled={engineRunning}
            >
              {engineRunning ? (
                <svg className="animate-spin" width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.3"/>
                  <path d="M6.5 1.5a5 5 0 0 1 5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              ) : (
                <EngineIcon />
              )}
              {engineRunning ? "Running…" : "Run Engine"}
            </button>
            <button
              className="flex items-center gap-1.5 h-8 px-3 rounded-lg text-[12px] font-medium
                         bg-white/10 text-white/80 hover:bg-white/20 transition-colors no-select"
              onClick={() => setActiveSection("breaks")}
            >
              <WaveIcon />
              Break Waves
            </button>

            {/* Back */}
            <button
              onClick={() => router.back()}
              className="flex items-center gap-1 h-8 px-2.5 rounded-lg text-[12px] font-medium
                         bg-white/10 text-white/60 hover:bg-white/20 transition-colors no-select"
            >
              <ArrowLeftIcon />
            </button>
          </div>
        }
      />

      {/* Fill rate strip */}
      <div className="bg-[#1A2340] border-t border-white/[0.08] px-6 pb-3">
        <div className="flex items-center gap-5">
          <FillRing rate={data?.fill_rate ?? 0} size={52} strokeWidth={5} />
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-widest text-white/40 mb-0.5">
              Fill Rate
            </div>
            <div className="flex gap-4 text-[13px]">
              <span className="text-white font-semibold">
                {zones.filter((z) => z.tm_id).length}/{zones.length} zones
              </span>
              <span className="text-white/50">
                {restrooms.filter((r) => r.tm_id).length}/{restrooms.length} restrooms
              </span>
            </div>
          </div>

          {/* Ops Quick Actions */}
          <div className="ml-auto flex gap-2">
            {["zones", "breaks"].map((s) => (
              <button
                key={s}
                onClick={() => setActiveSection(s as "zones" | "breaks")}
                className={cn(
                  "h-7 px-3 rounded-lg text-[12px] font-semibold transition-all no-select",
                  activeSection === s
                    ? "bg-[#C9A84C] text-[#1A2340]"
                    : "bg-white/10 text-white/60 hover:bg-white/20"
                )}
              >
                {s === "zones" ? "Zones" : "Break Waves"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="flex-1 px-4 py-5 overflow-y-auto">
        <AnimatePresence mode="wait">
          {activeSection === "zones" ? (
            <motion.div
              key="zones"
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 12 }}
              transition={{ duration: 0.2 }}
              className="flex flex-col gap-5"
            >
              {/* Zone cards grid */}
              <section>
                <h2 className="section-header">Zones</h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                  {zones.map((slot, i) => (
                    <ZoneCard
                      key={slot.slot_id}
                      slot={slot}
                      index={i}
                      isCovered={!slot.tm_id && coveredBySet.has(buildCoverageTaskName(slot).toLowerCase())}
                      isPencilHover={pencilHoverSlot === slot.slot_id}
                      onPencilEnter={() => setPencilHoverSlot(slot.slot_id)}
                      onPencilLeave={() => setPencilHoverSlot(null)}
                      onContextMenu={(e) => openCtx(e, slot)}
                    />
                  ))}
                </div>
              </section>

              {/* Restrooms strip */}
              <section>
                <h2 className="section-header">Restrooms</h2>
                <div className="flex gap-2.5 overflow-x-auto pb-1">
                  {restrooms.map((slot, i) => (
                    <RestroomPill
                      key={slot.slot_id}
                      slot={slot}
                      index={i}
                      onContextMenu={(e) => openCtx(e, slot)}
                    />
                  ))}
                </div>
              </section>

              {/* Auxiliary row */}
              <section>
                <h2 className="section-header">Auxiliary</h2>
                <div className="flex gap-2.5 flex-wrap">
                  {auxiliary.map((slot, i) => (
                    <RestroomPill
                      key={slot.slot_id}
                      slot={slot}
                      index={i}
                      onContextMenu={(e) => openCtx(e, slot)}
                    />
                  ))}
                </div>
              </section>

            </motion.div>
          ) : (
            <motion.div
              key="breaks"
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.2 }}
            >
              <BreakWavesView
                waves={breakWaves}
                onMoveTM={moveBreakTM}
                lastSynced={lastSynced}
                onRefresh={refresh}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <ContextMenu
        open={!!ctxSlot}
        onClose={() => { setCtxSlot(null); setCtxPos(undefined); }}
        actions={ctxActions}
        anchorPos={ctxPos}
      />

      <TMPickerSheet
        slot={pickerSlot}
        tms={tmRoster ?? []}
        deployedTmIds={new Set(
          (data?.placements ?? [])
            .filter((p) => p.tm_id && p.slot_id !== pickerSlot?.slot_id)
            .map((p) => p.tm_id!)
        )}
        deployedSlotMap={Object.fromEntries(
          (data?.placements ?? [])
            .filter((p) => p.tm_id && p.slot_id !== pickerSlot?.slot_id)
            .map((p) => [p.tm_id!, p.zone_label])
        )}
        scheduledTmIds={new Set(
          (data?.break_waves ?? [])
            .flatMap((w) => w.groups.flatMap((g) => g.tm_ids))
        )}
        onSelect={(tm) => {
          if (!pickerSlot) return;
          const initials = tm.display_name.split(" ").map((w) => w[0]?.toUpperCase() ?? "").join("").slice(0, 2);
          assignTM(pickerSlot.slot_id, { id: tm.id, name: tm.display_name, initials });
          setPickerSlot(null);
        }}
        onClear={() => {
          if (!pickerSlot) return;
          assignTM(pickerSlot.slot_id, null);
          setPickerSlot(null);
        }}
        onClose={() => setPickerSlot(null)}
      />

      <TaskPickerSheet
        slot={taskSlot}
        nightId={nightId}
        onClose={() => setTaskSlot(null)}
        onSaved={refresh}
      />

      <CoveragePickerSheet
        coveredSlot={coverageSlot}
        allSlots={data?.placements ?? []}
        onSelect={addCoverage}
        onClose={() => setCoverageSlot(null)}
      />

      {/* ── Engine Run Toast ───────────────────────────────────────── */}
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
              {/* Icon */}
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

              {/* Body */}
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

              {/* Dismiss */}
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

// ── Zone Card ─────────────────────────────────────────────────────────────────

interface ZoneCardProps {
  slot: TMAssignment;
  index: number;
  isCovered?: boolean;          // empty slot that has coverage assigned elsewhere
  isPencilHover: boolean;
  onPencilEnter: () => void;
  onPencilLeave: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
}

function ZoneCard({
  slot,
  index,
  isCovered = false,
  isPencilHover,
  onPencilEnter,
  onPencilLeave,
  onContextMenu,
}: ZoneCardProps) {
  const accent      = zoneAccentColor(slot.zone_id);
  const groupAccent = slot.group ? groupColor(slot.group) : "#E2E8F0";
  const isEmpty = !slot.tm_id;

  // Split tasks: regular vs coverage ("and Zone/Restroom X")
  const regularTasks  = (slot.tasks ?? []).filter((t) => !isCoverageTask(t));
  const coverageTasks = (slot.tasks ?? []).filter((t) => isCoverageTask(t));

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.94 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.03, duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      onClick={onContextMenu}
      onContextMenu={onContextMenu}
      onPointerEnter={onPencilEnter}
      onPointerLeave={onPencilLeave}
      className={cn(
        "card rounded-2xl overflow-hidden cursor-pointer no-select",
        "transition-all duration-150",
        isPencilHover && "shadow-card-hover ring-2 ring-[#C9A84C]/40",
        isEmpty && "opacity-75"
      )}
    >
      {/* 5px color accent top bar (from mockup #4) */}
      <div
        className="h-[5px] w-full"
        style={{ backgroundColor: accent }}
      />

      <div className="p-3 flex flex-col gap-2.5">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="text-[13px] font-bold text-gray-900 flex items-center gap-1">
              {slot.zone_label}
              <span className="text-gray-300 shrink-0 mt-0.5"><ChevronRightIcon /></span>
            </div>
            {slot.group && (
              <div className="text-[11px] font-medium text-gray-400 mt-0.5">
                Group {slot.group}
              </div>
            )}
          </div>
          {/* Group dot — break-group color, not zone-family */}
          {slot.group && (
            <div
              className="w-2 h-2 rounded-full shrink-0 mt-0.5"
              style={{ backgroundColor: groupAccent }}
            />
          )}
        </div>

        {/* TM info */}
        <div className="flex items-center gap-2">
          {isEmpty ? (
            <EmptySlotIcon />
          ) : (
            <UserIcon initials={slot.tm_initials ?? "?"} />
          )}
          <div className="min-w-0">
            <div
              className={cn(
                "text-[13px] font-semibold truncate",
                isEmpty ? "text-gray-300 italic" : "text-gray-800"
              )}
            >
              {slot.tm_name ?? "Unassigned"}
            </div>
          </div>
        </div>

        {/* Regular tasks — up to 3 shown, "+N more" overflow */}
        {regularTasks.length > 0 && (
          <ul className="flex flex-col gap-0.5">
            {regularTasks.slice(0, 3).map((t, i) => (
              <li key={i} className="flex items-start gap-1.5 text-[11px] text-gray-500 leading-snug">
                <TaskDotIcon />
                <span className="truncate">{t}</span>
              </li>
            ))}
            {regularTasks.length > 3 && (
              <li className="text-[10px] font-semibold text-gray-400 pl-3">
                +{regularTasks.length - 3} more
              </li>
            )}
          </ul>
        )}

        {/* Coverage tasks — "and Zone/Restroom X" — bold, centered, separated */}
        {coverageTasks.length > 0 && (
          <div className={cn(
            "flex flex-col gap-0.5 pt-1.5",
            regularTasks.length > 0 && "border-t border-gray-100 mt-0.5"
          )}>
            {coverageTasks.map((t, i) => (
              <div key={i} className="text-[11.5px] font-bold text-gray-700 text-center
                                      leading-snug tracking-tight">
                {t}
              </div>
            ))}
          </div>
        )}

        {/* Override indicator */}
        {slot.is_override && (
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-orange-400" />
            <span className="text-[10px] font-semibold text-orange-500 uppercase tracking-wide">Override</span>
          </div>
        )}
      </div>

      {/* Faint checkmark watermark — empty slot that has coverage assigned */}
      {isEmpty && isCovered && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <svg width="44" height="44" viewBox="0 0 44 44" fill="none" className="opacity-[0.07]">
            <path d="M8 22l10 10 18-18" stroke="#374151" strokeWidth="4.5"
                  strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      )}

      {/* Pencil hover overlay */}
      <AnimatePresence>
        {isPencilHover && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-[#C9A84C]/05 pointer-events-none
                       flex items-end justify-end p-2"
          >
            <span className="text-[10px] font-semibold text-[#C9A84C] bg-[#C9A84C]/10
                             px-2 py-0.5 rounded-full">
              Edit
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Restroom Pill ─────────────────────────────────────────────────────────────

function RestroomPill({
  slot,
  index,
  onContextMenu,
}: {
  slot: TMAssignment;
  index: number;
  onContextMenu: (e: React.MouseEvent) => void;
}) {
  const accent  = zoneAccentColor(slot.zone_id);  // zone-family — matches print
  const bgTint  = rrSideTint(slot.rr_side);       // whisper pink/blue for mens/womens
  const sideLabel = slot.rr_side === "mens" ? "Men's" : slot.rr_side === "womens" ? "Women's" : null;

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04 }}
      onClick={onContextMenu}
      onContextMenu={onContextMenu}
      className="card flex items-center gap-2.5 px-3.5 py-2.5 rounded-2xl
                 cursor-pointer no-select shrink-0 min-w-[160px]"
      style={{ backgroundColor: bgTint !== "transparent" ? bgTint : undefined }}
    >
      {/* Zone-family left accent bar */}
      <div
        className="w-1.5 rounded-full min-h-[32px] shrink-0"
        style={{ backgroundColor: accent }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <div className="text-[12px] font-semibold text-gray-700 truncate">{slot.zone_label}</div>
          {sideLabel && (
            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full shrink-0"
                  style={{
                    backgroundColor: `${accent}22`,
                    color: accent,
                  }}>
              {sideLabel}
            </span>
          )}
        </div>
        <div className={cn("text-[11px] truncate", slot.tm_id ? "text-gray-500" : "text-gray-300 italic")}>
          {slot.tm_name ?? "Unassigned"}
        </div>
      </div>
      {slot.tm_initials && (
        <div className="shrink-0">
          <UserIcon initials={slot.tm_initials} />
        </div>
      )}
    </motion.div>
  );
}


// ── TM Picker Sheet ───────────────────────────────────────────────────────────

interface TMPickerSheetProps {
  slot: TMAssignment | null;
  tms: ActiveTM[];
  /** tm_id → zone_label for every slot that already has a TM assigned */
  deployedTmIds: Set<string>;
  deployedSlotMap: Record<string, string>;
  /** TM ids that appear in break wave assignments (= on the schedule tonight) */
  scheduledTmIds: Set<string>;
  onSelect: (tm: ActiveTM) => void;
  onClear: () => void;
  onClose: () => void;
}

/** Return true if this TM is eligible for the given zone_type.
 *  Reads `metadata.eligible_types` (string[]) when present.
 *  Falls back to true (all-eligible) when the field is absent — safe until
 *  eligibility data is loaded into the entities table. */
function isEligible(tm: ActiveTM, zoneType: string): boolean {
  const eligible = (tm.metadata as Record<string, unknown> | null)?.eligible_types;
  if (!Array.isArray(eligible)) return true;
  return (eligible as string[]).includes(zoneType);
}

function TMPickerSheet({
  slot,
  tms,
  deployedTmIds,
  deployedSlotMap,
  scheduledTmIds,
  onSelect,
  onClear,
  onClose,
}: TMPickerSheetProps) {
  const [query, setQuery] = useState("");
  const [showDeployed, setShowDeployed]         = useState(false);
  const [showNotScheduled, setShowNotScheduled] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const isOpen = !!slot;

  // Reset collapse state when slot changes
  const prevSlotId = useRef<string | null>(null);
  useEffect(() => {
    if (slot && slot.slot_id !== prevSlotId.current) {
      prevSlotId.current = slot.slot_id;
      setQuery("");
      setShowDeployed(false);
      setShowNotScheduled(false);
    }
  }, [slot]);

  // ── Partition eligible TMs into three groups ──────────────────────────────
  const eligible   = tms.filter((tm) => isEligible(tm, slot?.zone_type ?? "zone"));
  const ineligible = tms.filter((tm) => !isEligible(tm, slot?.zone_type ?? "zone"));
  void ineligible; // reserved for future "show ineligible" toggle

  const q = query.toLowerCase();
  const matchesSearch = (tm: ActiveTM) =>
    !q || tm.display_name.toLowerCase().includes(q);

  /** Already deployed to another slot this night */
  const deployedGroup    = eligible.filter((tm) => deployedTmIds.has(tm.id) && matchesSearch(tm));
  /** On the schedule (in break waves) but not yet deployed */
  const availableGroup   = eligible.filter(
    (tm) => scheduledTmIds.has(tm.id) && !deployedTmIds.has(tm.id) && matchesSearch(tm)
  );
  /** Not on tonight's schedule at all */
  const unscheduledGroup = eligible.filter(
    (tm) => !scheduledTmIds.has(tm.id) && !deployedTmIds.has(tm.id) && matchesSearch(tm)
  );

  // If search is active, collapse/expand doesn't apply — show everything that matches
  const isSearching = !!q;

  function renderTMRow(tm: ActiveTM, variant: "available" | "deployed" | "unscheduled") {
    const initials  = tm.display_name.split(" ").map((w) => w[0]?.toUpperCase() ?? "").join("").slice(0, 2);
    const isCurrent = tm.id === slot?.tm_id;
    const deployedAt = deployedSlotMap[tm.id];

    const circleStyle = isCurrent
      ? "bg-[#007AFF]/15 text-[#007AFF] ring-[#007AFF]/20"
      : variant === "deployed"
        ? "bg-amber-100 text-amber-700 ring-amber-200"
        : variant === "unscheduled"
          ? "bg-gray-50 text-gray-400 ring-gray-100"
          : "bg-gray-100 text-gray-600 ring-gray-200";

    return (
      <button
        key={tm.id}
        onClick={() => onSelect(tm)}
        className={cn(
          "w-full flex items-center gap-3 px-3 py-2.5 rounded-2xl transition-colors text-left",
          isCurrent      ? "bg-[#007AFF]/08"  :
          variant === "deployed"    ? "hover:bg-amber-50" :
          variant === "unscheduled" ? "hover:bg-gray-50 opacity-60" :
          "hover:bg-gray-50"
        )}
      >
        {/* Avatar circle */}
        <div className="relative shrink-0">
          <div className={cn(
            "w-9 h-9 rounded-full flex items-center justify-center",
            "text-[12px] font-bold ring-1",
            circleStyle
          )}>
            {initials}
          </div>
          {/* Deployed pip — small amber dot */}
          {variant === "deployed" && (
            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full
                            bg-amber-400 ring-2 ring-white flex items-center justify-center">
              <div className="w-1 h-1 rounded-full bg-white" />
            </div>
          )}
          {/* Unscheduled pip — small gray dot */}
          {variant === "unscheduled" && (
            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full
                            bg-gray-300 ring-2 ring-white" />
          )}
        </div>

        {/* Name + badge */}
        <div className="flex-1 min-w-0">
          <div className={cn(
            "text-[14px] font-semibold truncate",
            isCurrent         ? "text-[#007AFF]" :
            variant === "unscheduled" ? "text-gray-400" :
            "text-gray-800"
          )}>
            {tm.display_name}
          </div>
          {deployedAt && (
            <div className="text-[11px] text-amber-600 font-medium mt-0.5">
              Deployed → {deployedAt}
            </div>
          )}
          {variant === "unscheduled" && (
            <div className="text-[11px] text-gray-400 mt-0.5">Not on tonight's schedule</div>
          )}
        </div>

        {/* Current checkmark */}
        {isCurrent && (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="shrink-0">
            <path d="M2 7l4 4 6-7" stroke="#007AFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )}
      </button>
    );
  }

  function CollapseHeader({
    label,
    count,
    open,
    onToggle,
    accent = "gray",
  }: {
    label: string;
    count: number;
    open: boolean;
    onToggle: () => void;
    accent?: "amber" | "gray";
  }) {
    return (
      <button
        onClick={onToggle}
        className={cn(
          "w-full flex items-center gap-2 px-1 py-2.5 text-left transition-colors",
          accent === "amber" ? "text-amber-600" : "text-gray-400"
        )}
      >
        <motion.span
          animate={{ rotate: open ? 90 : 0 }}
          transition={{ duration: 0.18 }}
          className="shrink-0"
        >
          <ChevronRightIcon />
        </motion.span>
        <span className="text-[12px] font-semibold uppercase tracking-widest flex-1">
          {label}
        </span>
        <span className={cn(
          "text-[11px] font-bold px-2 py-0.5 rounded-full",
          accent === "amber"
            ? "bg-amber-100 text-amber-700"
            : "bg-gray-100 text-gray-500"
        )}>
          {count}
        </span>
      </button>
    );
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="picker-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 bg-black/30 z-40"
            onClick={onClose}
          />
          {/* Sheet */}
          <motion.div
            key="picker-sheet"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
            className="fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-3xl
                       shadow-2xl flex flex-col max-h-[82dvh]"
            onAnimationComplete={() => inputRef.current?.focus()}
          >
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-1 shrink-0">
              <div className="w-10 h-1 rounded-full bg-gray-200" />
            </div>

            {/* Header */}
            <div className="px-5 pb-3 shrink-0">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-[16px] font-bold text-gray-900">
                    {slot?.tm_id ? "Reassign" : "Assign"} TM
                  </h3>
                  <p className="text-[12px] text-gray-400">{slot?.zone_label}</p>
                </div>
                <button
                  onClick={onClose}
                  className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center
                             text-gray-500 hover:bg-gray-200 transition-colors"
                >
                  <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                    <path d="M1 1l9 9M10 1L1 10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
                  </svg>
                </button>
              </div>

              {/* Search */}
              <div className="relative">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                     width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.3"/>
                  <path d="M9.5 9.5L12.5 12.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                </svg>
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search TMs…"
                  className="w-full pl-9 pr-4 py-2 rounded-xl bg-gray-100 text-[14px]
                             text-gray-800 placeholder:text-gray-400 outline-none
                             focus:ring-2 focus:ring-[#007AFF]/30"
                />
              </div>
            </div>

            {/* TM list */}
            <div className="overflow-y-auto flex-1 px-4 pb-safe">
              {/* Clear option */}
              {slot?.tm_id && (
                <button
                  onClick={onClear}
                  className="w-full flex items-center gap-3 px-3 py-2.5 mb-1 rounded-2xl
                             text-red-500 hover:bg-red-50 transition-colors"
                >
                  <div className="w-9 h-9 rounded-full bg-red-100 flex items-center justify-center shrink-0">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  </div>
                  <span className="text-[14px] font-semibold">Clear slot</span>
                </button>
              )}

              {/* ── Available (scheduled, not deployed) ─────────────────── */}
              {isSearching ? (
                /* When searching: flat list across all groups */
                <>
                  {[...availableGroup, ...deployedGroup, ...unscheduledGroup].length === 0 && (
                    <p className="text-center text-[13px] text-gray-400 py-8">No TMs found</p>
                  )}
                  {availableGroup.map((tm) => renderTMRow(tm, "available"))}
                  {deployedGroup.map((tm) => renderTMRow(tm, "deployed"))}
                  {unscheduledGroup.map((tm) => renderTMRow(tm, "unscheduled"))}
                </>
              ) : (
                <>
                  {/* Available section — always expanded */}
                  {availableGroup.length > 0 && (
                    <>
                      <div className="text-[11px] font-semibold uppercase tracking-widest
                                      text-gray-400 px-1 pt-1 pb-2">
                        Available · {availableGroup.length}
                      </div>
                      {availableGroup.map((tm) => renderTMRow(tm, "available"))}
                    </>
                  )}

                  {availableGroup.length === 0 && deployedGroup.length === 0 && unscheduledGroup.length === 0 && (
                    <p className="text-center text-[13px] text-gray-400 py-8">No eligible TMs</p>
                  )}

                  {/* Deployed section — collapsible, amber accent */}
                  {deployedGroup.length > 0 && (
                    <div className="mt-2">
                      <CollapseHeader
                        label="Already Deployed"
                        count={deployedGroup.length}
                        open={showDeployed}
                        onToggle={() => setShowDeployed((v) => !v)}
                        accent="amber"
                      />
                      <AnimatePresence>
                        {showDeployed && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            {deployedGroup.map((tm) => renderTMRow(tm, "deployed"))}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}

                  {/* Not Scheduled section — collapsible, gray accent */}
                  {unscheduledGroup.length > 0 && (
                    <div className="mt-2">
                      <CollapseHeader
                        label="Not Scheduled Tonight"
                        count={unscheduledGroup.length}
                        open={showNotScheduled}
                        onToggle={() => setShowNotScheduled((v) => !v)}
                        accent="gray"
                      />
                      <AnimatePresence>
                        {showNotScheduled && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            {unscheduledGroup.map((tm) => renderTMRow(tm, "unscheduled"))}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}
                </>
              )}

              <div className="h-6" />
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ── Coverage Picker Sheet ─────────────────────────────────────────────────────
// Lets the supervisor pick which filled slot will cover an unassigned one.
// Selecting a covering slot writes "and Zone X" / "and Restroom X (Side)"
// as a custom task on the covering slot's zone_assignment row.

interface CoveragePickerSheetProps {
  coveredSlot: TMAssignment | null;   // the empty slot that needs coverage
  allSlots: TMAssignment[];           // all placements for tonight
  onSelect: (coveringSlot: TMAssignment) => Promise<void>;
  onClose: () => void;
}

function CoveragePickerSheet({
  coveredSlot,
  allSlots,
  onSelect,
  onClose,
}: CoveragePickerSheetProps) {
  const isOpen   = !!coveredSlot;
  const [saving, setSaving] = useState<string | null>(null);  // slot_id being saved

  if (!coveredSlot) return null;

  const taskName = buildCoverageTaskName(coveredSlot);

  // All filled slots except the covered slot itself, grouped by type
  const filled = allSlots.filter(
    (s) => s.tm_id && s.slot_id !== coveredSlot.slot_id
  );
  const filledZones = filled.filter((s) => s.zone_type === "zone");
  const filledRRs   = filled.filter((s) => s.zone_type === "restroom");
  const filledAux   = filled.filter((s) => s.zone_type === "auxiliary");

  async function handleSelect(slot: TMAssignment) {
    setSaving(slot.slot_id);
    await onSelect(slot);
    setSaving(null);
  }

  function SlotRow({ slot }: { slot: TMAssignment }) {
    const accent       = zoneAccentColor(slot.zone_id);
    const alreadyHas   = (slot.tasks ?? []).includes(taskName);
    const isSaving     = saving === slot.slot_id;
    const sideLabel    = slot.rr_side === "mens" ? "Men's" : slot.rr_side === "womens" ? "Women's" : null;

    return (
      <button
        onClick={() => !alreadyHas && handleSelect(slot)}
        disabled={alreadyHas || isSaving}
        className={cn(
          "w-full flex items-center gap-3 px-3 py-2.5 rounded-2xl transition-colors text-left",
          alreadyHas ? "opacity-50 cursor-default" : "hover:bg-gray-50 active:bg-gray-100"
        )}
      >
        {/* Zone-family accent bar */}
        <div className="w-1 h-9 rounded-full shrink-0" style={{ backgroundColor: accent }} />

        {/* Zone label + TM */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-[13px] font-semibold text-gray-800 truncate">
              {slot.zone_label}
            </span>
            {sideLabel && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full shrink-0"
                    style={{ backgroundColor: `${accent}22`, color: accent }}>
                {sideLabel}
              </span>
            )}
          </div>
          <div className="text-[11px] text-gray-400 mt-0.5 truncate">{slot.tm_name}</div>
        </div>

        {/* State indicator */}
        {alreadyHas ? (
          <span className="text-[10px] font-semibold text-green-600 bg-green-50
                           px-2 py-0.5 rounded-full shrink-0">
            Assigned
          </span>
        ) : isSaving ? (
          <div className="w-4 h-4 rounded-full border-2 border-[#007AFF] border-t-transparent
                          animate-spin shrink-0" />
        ) : (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-gray-300 shrink-0">
            <path d="M4 2l6 5-6 5" stroke="currentColor" strokeWidth="1.5"
                  strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )}
      </button>
    );
  }

  function SectionHeader({ label, count }: { label: string; count: number }) {
    if (count === 0) return null;
    return (
      <div className="text-[11px] font-semibold uppercase tracking-widest text-gray-400
                      px-1 pt-3 pb-1.5 first:pt-1">
        {label} · {count}
      </div>
    );
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            key="coverage-backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 bg-black/30 z-40"
            onClick={onClose}
          />
          <motion.div
            key="coverage-sheet"
            initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
            className="fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-3xl
                       shadow-2xl flex flex-col max-h-[80dvh]"
          >
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-1 shrink-0">
              <div className="w-10 h-1 rounded-full bg-gray-200" />
            </div>

            {/* Header */}
            <div className="px-5 pt-1 pb-4 shrink-0 flex items-start justify-between">
              <div>
                <h3 className="text-[16px] font-bold text-gray-900">Add Coverage</h3>
                <p className="text-[12px] text-gray-400 mt-0.5">
                  Who covers{" "}
                  <span className="font-semibold text-gray-600">{coveredSlot.zone_label}</span>?
                  Adds <span className="font-semibold text-gray-700">"{taskName}"</span> to their card.
                </p>
              </div>
              <button
                onClick={onClose}
                className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center
                           text-gray-500 hover:bg-gray-200 transition-colors shrink-0"
              >
                <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                  <path d="M1 1l9 9M10 1L1 10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
                </svg>
              </button>
            </div>

            {/* Slot list */}
            <div className="overflow-y-auto flex-1 px-4 pb-safe">
              {filled.length === 0 && (
                <p className="text-center text-[13px] text-gray-400 py-10">
                  No filled slots available to assign coverage
                </p>
              )}
              <SectionHeader label="Zones" count={filledZones.length} />
              {filledZones.map((s) => <SlotRow key={s.slot_id} slot={s} />)}
              <SectionHeader label="Restrooms" count={filledRRs.length} />
              {filledRRs.map((s)  => <SlotRow key={s.slot_id} slot={s} />)}
              <SectionHeader label="Auxiliary" count={filledAux.length} />
              {filledAux.map((s)  => <SlotRow key={s.slot_id} slot={s} />)}
              <div className="h-6" />
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ── Task Picker Sheet ─────────────────────────────────────────────────────────

const CATEGORY_TABS: { id: string; label: string; cats: string[] }[] = [
  { id: "zone",   label: "Zone",    cats: ["zone", "rr", "aux"] },
  { id: "am",     label: "AM",      cats: ["overlap_am"] },
  { id: "pm",     label: "PM",      cats: ["overlap_pm"] },
];

interface TaskPickerSheetProps {
  slot: TMAssignment | null;
  nightId: string;
  onClose: () => void;
  onSaved?: () => void;  // called after successful save so SWR revalidates immediately
}

function TaskPickerSheet({ slot, nightId, onClose, onSaved }: TaskPickerSheetProps) {
  const isOpen = !!slot;
  const [activeTab, setActiveTab] = useState("zone");
  const [saving, setSaving] = useState(false);
  const [customInput, setCustomInput] = useState("");
  const customInputRef = useRef<HTMLInputElement>(null);

  // Fetch ALL tasks for this slot type when the sheet opens (no slot_key filter)
  const { data: allTasks = [] } = useSWR(
    slot ? `forge:tasks:${slot.zone_type}` : null,
    () => fetchZoneTasks(slot!.zone_type),
    { revalidateOnFocus: false, dedupingInterval: 300_000 },
  );

  // Local selected state — initialised from slot.tasks when sheet opens
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // Track whether we've applied defaults for this sheet open
  const [defaultsApplied, setDefaultsApplied] = useState(false);

  // Sync selected set whenever slot changes (new sheet open)
  const prevSlotId = useRef<string | null>(null);
  useEffect(() => {
    if (slot && slot.slot_id !== prevSlotId.current) {
      prevSlotId.current = slot.slot_id;
      setActiveTab("zone");
      setCustomInput("");
      setDefaultsApplied(false);
      if (slot.tasks !== null) {
        // Explicit save exists — use it as-is (may be empty if all tasks were cleared)
        setSelected(new Set(slot.tasks));
      } else {
        // Never been customised — will be pre-filled once catalogue loads (see effect below)
        setSelected(new Set());
      }
    }
  }, [slot]);

  // Once catalogue loads AND slot has never been customised, pre-select defaults
  useEffect(() => {
    if (!slot || slot.tasks !== null || defaultsApplied || allTasks.length === 0) return;
    const defaults = allTasks
      .filter(
        (t) =>
          t.target_codes.length === 0 ||            // universal task for this slot type
          t.target_codes.includes(slot.zone_id)     // specifically targets this zone
      )
      .map((t) => t.name);
    setSelected(new Set(defaults));
    setDefaultsApplied(true);
  }, [slot, allTasks, defaultsApplied]);

  // Tasks that are selected but don't exist in the DB catalogue — these are custom
  const catalogueNames = new Set(allTasks.map((t) => t.name));
  const customTasks = [...selected].filter((name) => !catalogueNames.has(name));

  const tabTasks = allTasks.filter((t) => {
    const tab = CATEGORY_TABS.find((tb) => tb.id === activeTab);
    return tab ? tab.cats.includes(t.category) : false;
  });

  function toggle(name: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  function addCustomTask() {
    const name = customInput.trim();
    if (!name) return;
    setSelected((prev) => new Set([...prev, name]));
    setCustomInput("");
    customInputRef.current?.focus();
  }

  /**
   * Union-merge catalogue defaults into the current selection.
   * Adds any default tasks that aren't already selected.
   * Never removes custom tasks or existing selections — purely additive.
   */
  function restoreDefaults() {
    if (!slot || allTasks.length === 0) return;
    const defaults = allTasks
      .filter(
        (t) =>
          t.target_codes.length === 0 ||         // universal task for this slot type
          t.target_codes.includes(slot.zone_id)  // specifically targets this zone
      )
      .map((t) => t.name);
    setSelected((prev) => new Set([...defaults, ...prev]));
  }

  async function save() {
    if (!slot) return;
    setSaving(true);
    try {
      await patchSlotTasks(nightId, slot.slot_id, [...selected]);
      onSaved?.();   // kick SWR revalidation so the card updates immediately
      onClose();
    } catch (err) {
      console.error("patchSlotTasks failed:", err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            key="task-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 bg-black/30 z-40"
            onClick={onClose}
          />
          <motion.div
            key="task-sheet"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
            className="fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-3xl
                       shadow-2xl flex flex-col max-h-[82dvh]"
          >
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-1 shrink-0">
              <div className="w-10 h-1 rounded-full bg-gray-200" />
            </div>

            {/* Header */}
            <div className="px-5 pt-1 pb-3 shrink-0 flex items-start justify-between">
              <div>
                <h3 className="text-[16px] font-bold text-gray-900">Assign Tasks</h3>
                <p className="text-[12px] text-gray-400">
                  {slot?.zone_label}
                  {selected.size > 0 && (
                    <span className="ml-2 text-[#007AFF] font-semibold">
                      {selected.size} selected
                    </span>
                  )}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {/* Restore Defaults — additive merge, never clears custom tasks */}
                <button
                  onClick={restoreDefaults}
                  disabled={allTasks.length === 0}
                  title="Add all default tasks for this zone without clearing your custom selections"
                  className="h-8 px-3 rounded-xl bg-gray-100 text-gray-600 text-[12px] font-semibold
                             hover:bg-gray-200 transition-colors disabled:opacity-40 shrink-0"
                >
                  Restore Defaults
                </button>
                <button
                  onClick={save}
                  disabled={saving}
                  className="h-8 px-4 rounded-xl bg-[#007AFF] text-white text-[13px] font-semibold
                             disabled:opacity-50 transition-opacity"
                >
                  {saving ? "Saving…" : "Save"}
                </button>
                <button
                  onClick={onClose}
                  className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center
                             text-gray-500 hover:bg-gray-200 transition-colors"
                >
                  <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                    <path d="M1 1l9 9M10 1L1 10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
                  </svg>
                </button>
              </div>
            </div>

            {/* Segmented tab control */}
            <div className="px-5 pb-3 shrink-0">
              <div className="flex gap-1 bg-gray-100 p-1 rounded-xl">
                {CATEGORY_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      "flex-1 py-1.5 rounded-lg text-[13px] font-semibold transition-all",
                      activeTab === tab.id
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-500 hover:text-gray-700"
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Task list */}
            <div className="overflow-y-auto flex-1 px-4">
              {tabTasks.length === 0 && (
                <p className="text-center text-[13px] text-gray-400 py-10">
                  No tasks for this slot type
                </p>
              )}
              {tabTasks.map((task) => {
                const checked = selected.has(task.name);
                return (
                  <button
                    key={task.id}
                    onClick={() => toggle(task.name)}
                    className={cn(
                      "w-full flex items-center gap-3 px-3 py-3.5 rounded-2xl transition-colors text-left",
                      checked ? "bg-[#007AFF]/06" : "hover:bg-gray-50"
                    )}
                  >
                    {/* Checkbox */}
                    <div className={cn(
                      "w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-all",
                      checked
                        ? "border-[#007AFF] bg-[#007AFF]"
                        : "border-gray-300 bg-white"
                    )}>
                      {checked && (
                        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                          <path d="M2 5l2.5 2.5L8 3" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className={cn(
                        "text-[14px] font-medium truncate",
                        checked ? "text-[#007AFF]" : "text-gray-800"
                      )}>
                        {task.name}
                      </div>
                      {task.description && (
                        <div className="text-[11px] text-gray-400 truncate mt-0.5">
                          {task.description}
                        </div>
                      )}
                    </div>
                    <ChevronRightIcon />
                  </button>
                );
              })}

              {/* Custom tasks section — always visible if any exist */}
              {customTasks.length > 0 && (
                <div className="mt-3 mb-1">
                  <div className="text-[11px] font-semibold uppercase tracking-widest text-gray-400 px-1 mb-2">
                    Custom
                  </div>
                  {customTasks.map((name) => (
                    <div
                      key={name}
                      className="flex items-center gap-3 px-3 py-3 rounded-2xl bg-amber-50 mb-1"
                    >
                      <div className="w-5 h-5 rounded-full border-2 border-amber-400 bg-amber-400
                                      flex items-center justify-center shrink-0">
                        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                          <path d="M2 5l2.5 2.5L8 3" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      </div>
                      <span className="flex-1 text-[14px] font-medium text-amber-900 truncate">
                        {name}
                      </span>
                      <button
                        onClick={() => toggle(name)}
                        className="w-6 h-6 rounded-full bg-amber-200 flex items-center justify-center
                                   text-amber-700 hover:bg-amber-300 transition-colors shrink-0"
                      >
                        <svg width="9" height="9" viewBox="0 0 9 9" fill="none">
                          <path d="M1 1l7 7M8 1L1 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="h-4" />
            </div>

            {/* Custom task input — pinned above keyboard */}
            <div className="px-4 pt-3 pb-safe border-t border-gray-100 shrink-0">
              <div className="flex gap-2 items-center">
                <input
                  ref={customInputRef}
                  value={customInput}
                  onChange={(e) => setCustomInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addCustomTask()}
                  placeholder="Add custom task…"
                  className="flex-1 h-10 px-3.5 rounded-xl bg-gray-100 text-[14px]
                             text-gray-800 placeholder:text-gray-400 outline-none
                             focus:ring-2 focus:ring-[#C9A84C]/40"
                />
                <button
                  onClick={addCustomTask}
                  disabled={!customInput.trim()}
                  className="h-10 px-4 rounded-xl bg-[#C9A84C] text-white text-[13px] font-semibold
                             disabled:opacity-40 transition-opacity shrink-0"
                >
                  Add
                </button>
              </div>
              <div className="h-3" />
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ── Break Waves View ──────────────────────────────────────────────────────────
// This view is the Break Sheet — shares the SAME SWR data as the zones view.
// Any change here (moveBreakTM) immediately updates the zones view and vice versa.
//
// Layout: 3 wave columns (First / Main / Last Break).
// Each column contains 3 group rows (Group 1 / 2 / 3) with their exact times.
// TMs are draggable between waves; their group assignment is preserved.

interface BreakWavesViewProps {
  waves: BreakWave[];
  onMoveTM: (tmId: string, tmName: string, fromWave: GroupId, toWave: GroupId) => Promise<void>;
  lastSynced: string | null;
  onRefresh: () => void;
}

/** Accent color for each wave (First / Main / Last Break) */
const WAVE_COLORS: Record<GroupId, string> = {
  "1": "#3B82F6",   // blue  — First Break
  "2": "#F59E0B",   // amber — Main Break
  "3": "#10B981",   // green — Last Break
};

function BreakWavesView({ waves, onMoveTM, lastSynced, onRefresh }: BreakWavesViewProps) {
  const [dragging, setDragging] = useState<{ tmId: string; tmName: string; fromWave: GroupId } | null>(null);
  const [dropTarget, setDropTarget] = useState<GroupId | null>(null);

  function handleDragStart(tmId: string, tmName: string, fromWave: GroupId) {
    setDragging({ tmId, tmName, fromWave });
  }

  function handleDrop(toWave: GroupId) {
    if (dragging && dragging.fromWave !== toWave) {
      onMoveTM(dragging.tmId, dragging.tmName, dragging.fromWave, toWave);
    }
    setDragging(null);
    setDropTarget(null);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between mb-1">
        <h2 className="section-header !mb-0">Break Waves</h2>
        <SyncBar lastSynced={lastSynced} onRefresh={onRefresh} className="text-gray-400" />
      </div>
      <p className="text-[12px] text-gray-400 -mt-2">
        Drag TMs between waves · groups go on break at staggered times
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {waves.map((wave) => {
          const totalTMs = wave.groups.reduce((n, g) => n + g.tm_ids.length, 0);
          const waveColor = WAVE_COLORS[wave.wave as GroupId];
          const isDropTarget = dropTarget === wave.wave;

          return (
            <div
              key={wave.wave}
              onDragOver={(e) => { e.preventDefault(); setDropTarget(wave.wave as GroupId); }}
              onDragLeave={() => setDropTarget(null)}
              onDrop={() => handleDrop(wave.wave as GroupId)}
              className={cn(
                "card rounded-3xl p-4 transition-all duration-150",
                isDropTarget && "ring-2 ring-[#007AFF] bg-blue-50/30"
              )}
            >
              {/* Wave header */}
              <div className="flex items-center gap-2 mb-4">
                <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: waveColor }} />
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-bold text-gray-800">{wave.label}</div>
                </div>
                <div className="badge bg-gray-100 text-gray-500 text-[11px] shrink-0">
                  {totalTMs} TM{totalTMs !== 1 ? "s" : ""}
                </div>
              </div>

              {/* Per-group rows */}
              <div className="flex flex-col gap-3">
                {wave.groups.map((grpSlot) => (
                  <BreakGroupRow
                    key={grpSlot.group}
                    grpSlot={grpSlot}
                    waveId={wave.wave as GroupId}
                    draggingTmId={dragging?.tmId ?? null}
                    onDragStart={handleDragStart}
                  />
                ))}
              </div>

              {/* Drop hint when hovering */}
              {isDropTarget && (
                <div className="mt-3 text-[11px] text-[#007AFF] font-semibold text-center
                                py-1.5 border-2 border-dashed border-[#007AFF]/30 rounded-xl">
                  Drop to move here
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Break Group Row ───────────────────────────────────────────────────────────

interface BreakGroupRowProps {
  grpSlot: BreakGroupSlot;
  waveId: GroupId;
  draggingTmId: string | null;
  onDragStart: (tmId: string, tmName: string, fromWave: GroupId) => void;
}

function BreakGroupRow({ grpSlot, waveId, draggingTmId, onDragStart }: BreakGroupRowProps) {
  const accentColor = groupColor(grpSlot.group);
  const timeLabel = `${formatBreakTime(grpSlot.start_time)} – ${formatBreakTime(grpSlot.end_time)}`;

  return (
    <div className="rounded-2xl bg-gray-50 overflow-hidden">
      {/* Group header bar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-100">
        <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: accentColor }} />
        <span className="text-[11px] font-semibold text-gray-600">Group {grpSlot.group}</span>
        <span className="ml-auto text-[11px] text-gray-400 font-mono">{timeLabel}</span>
        <span className="ml-1 text-[10px] font-medium text-gray-300">
          {grpSlot.duration_min}m
        </span>
      </div>

      {/* TM chips */}
      <div className="px-2 py-1.5 flex flex-col gap-1">
        <AnimatePresence>
          {grpSlot.tm_names.map((name, i) => (
            <motion.div
              key={grpSlot.tm_ids[i]}
              layout
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.15 }}
              draggable
              onDragStart={() => onDragStart(grpSlot.tm_ids[i], name, waveId)}
              className={cn(
                "flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-white",
                "border border-gray-100 cursor-grab active:cursor-grabbing",
                "transition-colors duration-100 no-select",
                draggingTmId === grpSlot.tm_ids[i] && "opacity-40"
              )}
            >
              <UserIcon initials={name.split(" ").map((n) => n[0]).join("").slice(0, 2)} />
              <span className="text-[12px] font-medium text-gray-700 truncate flex-1">{name}</span>
              {/* Drag handle */}
              <span className="text-gray-200 shrink-0">
                <svg width="8" height="12" viewBox="0 0 8 12" fill="currentColor">
                  <circle cx="2" cy="2" r="1.5"/><circle cx="6" cy="2" r="1.5"/>
                  <circle cx="2" cy="6" r="1.5"/><circle cx="6" cy="6" r="1.5"/>
                  <circle cx="2" cy="10" r="1.5"/><circle cx="6" cy="10" r="1.5"/>
                </svg>
              </span>
            </motion.div>
          ))}
        </AnimatePresence>

        {grpSlot.tm_ids.length === 0 && (
          <div className="text-[11px] text-gray-300 italic py-1 px-1">No TMs</div>
        )}
      </div>
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function PlannerSkeleton({ weekId, onBack }: { weekId: string; onBack: () => void }) {
  return (
    <div className="flex flex-col min-h-dvh bg-[#F5F5F7]">
      <GlcrHeader
        compact
        title="Loading…"
        right={
          <button onClick={onBack} className="h-8 px-2.5 rounded-lg bg-white/10 text-white/60">
            <ArrowLeftIcon />
          </button>
        }
      />
      <div className="px-4 py-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            className="h-36 rounded-2xl shimmer-bg"
            style={{ animationDelay: `${i * 0.06}s` }}
          />
        ))}
      </div>
    </div>
  );
}
