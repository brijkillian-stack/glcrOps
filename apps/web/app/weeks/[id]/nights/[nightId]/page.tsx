"use client";

import { useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter, useParams } from "next/navigation";
import useSWR from "swr";
import { GlcrHeader } from "@/components/ui/GlcrHeader";
import { FillRing } from "@/components/ui/FillRing";
import { ContextMenu, type ContextAction } from "@/components/ui/ContextMenu";
import { SyncBar } from "@/components/ui/SyncBar";
import { useNightPlacements, useRealtimeSync, type TMAssignment, type BreakWave, type BreakGroupSlot, type GroupId } from "@/lib/sync";
import { fetchActiveTMs, type ActiveTM } from "@/lib/forge-api";
import { cn, groupColor } from "@/lib/utils";
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
  const [pickerSlot, setPickerSlot] = useState<TMAssignment | null>(null);

  // TM roster — cached by SWR, refreshes every 10 min
  const { data: tmRoster } = useSWR("forge:tms:active", () => fetchActiveTMs(), {
    revalidateOnFocus: false,
    dedupingInterval: 600_000,
  });

  // Separate zone types
  const zones      = data?.placements.filter((p) => p.zone_type === "zone")       ?? [];
  const restrooms  = data?.placements.filter((p) => p.zone_type === "restroom")   ?? [];
  const auxiliary  = data?.placements.filter((p) => p.zone_type === "auxiliary")  ?? [];
  const breakWaves = data?.break_waves ?? [];

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

  const ctxActions: ContextAction[] = ctxSlot
    ? [
        {
          label: ctxSlot.tm_id ? "Reassign TM" : "Assign TM",
          icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="5" cy="4" r="3" stroke="currentColor" strokeWidth="1.2"/><path d="M1 13c0-2 2-3.5 4-3.5s4 1.5 4 3.5M10 5h4M12 3v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
          onClick: () => openPicker(ctxSlot),
        },
        {
          label: "Clear slot",
          icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>,
          onClick: () => { assignTM(ctxSlot.slot_id, null); setCtxSlot(null); },
          disabled: !ctxSlot.tm_id,
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
                window.open(`/api/forge/v1/print/night/${nightId}.pdf`, "_blank")
              }
            >
              <PrintIcon />
              Print Day
            </button>
            <button
              className="flex items-center gap-1.5 h-8 px-3 rounded-lg text-[12px] font-medium
                         bg-white/10 text-white/80 hover:bg-white/20 transition-colors no-select"
              onClick={() => console.log("Run engine")}
            >
              <EngineIcon />
              Run Engine
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
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                  {zones.map((slot, i) => (
                    <ZoneCard
                      key={slot.slot_id}
                      slot={slot}
                      index={i}
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

              {/* Overlaps section */}
              <OverlapsSection />
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
    </div>
  );
}

// ── Zone Card ─────────────────────────────────────────────────────────────────

interface ZoneCardProps {
  slot: TMAssignment;
  index: number;
  isPencilHover: boolean;
  onPencilEnter: () => void;
  onPencilLeave: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
}

function ZoneCard({
  slot,
  index,
  isPencilHover,
  onPencilEnter,
  onPencilLeave,
  onContextMenu,
}: ZoneCardProps) {
  const accent = slot.group ? groupColor(slot.group) : "#E2E8F0";
  const isEmpty = !slot.tm_id;

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
          {/* Group dot */}
          {slot.group && (
            <div
              className="w-2 h-2 rounded-full shrink-0 mt-0.5"
              style={{ backgroundColor: accent }}
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

        {/* Tasks */}
        {slot.tasks.length > 0 && (
          <ul className="flex flex-col gap-1">
            {slot.tasks.slice(0, 2).map((t, i) => (
              <li
                key={i}
                className="flex items-start gap-1.5 text-[11px] text-gray-500"
              >
                <TaskDotIcon />
                <span className="truncate">{t}</span>
              </li>
            ))}
          </ul>
        )}

        {/* Override indicator */}
        {slot.is_override && (
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-orange-400" />
            <span className="text-[10px] font-semibold text-orange-500 uppercase tracking-wide">Override</span>
          </div>
        )}
      </div>

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
  const accent = slot.group ? groupColor(slot.group) : "#94A3B8";
  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04 }}
      onClick={onContextMenu}
      onContextMenu={onContextMenu}
      className="card flex items-center gap-2.5 px-3.5 py-2.5 rounded-2xl
                 cursor-pointer no-select shrink-0 min-w-[160px]"
    >
      <div
        className="w-2 h-full rounded-full min-h-[28px] shrink-0"
        style={{ backgroundColor: accent }}
      />
      <div>
        <div className="text-[12px] font-semibold text-gray-700">{slot.zone_label}</div>
        <div className={cn("text-[11px]", slot.tm_id ? "text-gray-500" : "text-gray-300 italic")}>
          {slot.tm_name ?? "Unassigned"}
        </div>
      </div>
      {slot.tm_initials && (
        <div className="ml-auto">
          <UserIcon initials={slot.tm_initials} />
        </div>
      )}
    </motion.div>
  );
}

// ── Overlaps Section ──────────────────────────────────────────────────────────

function OverlapsSection() {
  // Placeholder — in prod: fetched from the weekly planning overview
  const overlaps = [
    { label: "Fri 01:00–02:00", zones: ["Z3", "Z4"], note: "PM handoff" },
    { label: "Fri 04:30–05:00", zones: ["Z9", "Z12"], note: "AM handoff" },
  ];

  return (
    <section>
      <h2 className="section-header">Overlaps</h2>
      <div className="flex flex-col gap-2">
        {overlaps.map((o, i) => (
          <div
            key={i}
            className="card flex items-center gap-4 px-4 py-3 rounded-2xl no-select"
          >
            <div className="flex-1">
              <div className="text-[13px] font-semibold text-gray-800">{o.label}</div>
              <div className="text-[11px] text-gray-400 mt-0.5">{o.note}</div>
            </div>
            <div className="flex gap-1.5">
              {o.zones.map((z) => (
                <span key={z} className="px-2 py-0.5 rounded-md bg-blue-50 text-blue-600
                                          text-[11px] font-semibold">
                  {z}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── TM Picker Sheet ───────────────────────────────────────────────────────────

interface TMPickerSheetProps {
  slot: TMAssignment | null;
  tms: ActiveTM[];
  onSelect: (tm: ActiveTM) => void;
  onClear: () => void;
  onClose: () => void;
}

function TMPickerSheet({ slot, tms, onSelect, onClear, onClose }: TMPickerSheetProps) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const isOpen = !!slot;

  const filtered = tms.filter((tm) =>
    tm.display_name.toLowerCase().includes(query.toLowerCase())
  );

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
                       shadow-2xl flex flex-col max-h-[80dvh]"
            onAnimationComplete={() => inputRef.current?.focus()}
          >
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-1 shrink-0">
              <div className="w-10 h-1 rounded-full bg-gray-200" />
            </div>

            {/* Header */}
            <div className="px-5 pb-3 shrink-0">
              <div className="flex items-center justify-between mb-1">
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
              <div className="relative mt-2">
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
              {/* Clear option — only if slot is filled */}
              {slot?.tm_id && (
                <button
                  onClick={onClear}
                  className="w-full flex items-center gap-3 px-3 py-3 mb-1 rounded-2xl
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

              {filtered.length === 0 && (
                <p className="text-center text-[13px] text-gray-400 py-8">No TMs found</p>
              )}

              {filtered.map((tm) => {
                const initials = tm.display_name.split(" ").map((w) => w[0]?.toUpperCase() ?? "").join("").slice(0, 2);
                const isCurrent = tm.id === slot?.tm_id;
                return (
                  <button
                    key={tm.id}
                    onClick={() => onSelect(tm)}
                    className={cn(
                      "w-full flex items-center gap-3 px-3 py-3 rounded-2xl transition-colors",
                      isCurrent
                        ? "bg-[#007AFF]/08 text-[#007AFF]"
                        : "hover:bg-gray-50 text-gray-800"
                    )}
                  >
                    <div className={cn(
                      "w-9 h-9 rounded-full flex items-center justify-center shrink-0",
                      "text-[12px] font-bold ring-1",
                      isCurrent
                        ? "bg-[#007AFF]/15 text-[#007AFF] ring-[#007AFF]/20"
                        : "bg-gray-100 text-gray-600 ring-gray-200"
                    )}>
                      {initials}
                    </div>
                    <div className="flex-1 text-left">
                      <div className="text-[14px] font-semibold">{tm.display_name}</div>
                    </div>
                    {isCurrent && (
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M2 7l4 4 6-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    )}
                  </button>
                );
              })}

              {/* Bottom safe area spacer */}
              <div className="h-6" />
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
