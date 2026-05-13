"use client";

export const dynamic = "force-dynamic";

/**
 * ZDS Control Panel
 *
 * Tab 1 — Tasks:  full CRUD over zone_tasks (add, rename, delete, change
 *                 category, set display_order).
 * (Future tabs for Break Schedule, Zone Config, etc.)
 */

import { useState, useRef, useEffect } from "react";
import useSWR, { useSWRConfig } from "swr";
import { GlcrHeader } from "@/components/ui/GlcrHeader";
import {
  fetchAllZoneTasks,
  createZoneTask,
  patchZoneTask,
  deleteZoneTask,
  reorderZoneTasks,
  fetchTabConfig,
  patchTabConfig,
  fetchBreakSchedule,
  patchBreakSchedule,
  DEFAULT_BREAK_SCHEDULE,
  DAY_CODES,
  type ZoneTask,
  type TaskCategory,
  type LaborCategory,
  type TaskFrequency,
  type ShiftPhase,
  type DayCode,
  type TaskTab,
  type BreakSchedule,
  type BreakSlot,
} from "@/lib/forge-api";
import { cn } from "@/lib/utils";

// ── Icons ─────────────────────────────────────────────────────────────────────

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M10 2L12 4L5 11H3V9L10 2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M2 4h10M5 4V2.5h4V4M5.5 6.5v4M8.5 6.5v4M3 4l.8 7.5a1 1 0 001 .9h4.4a1 1 0 001-.9L11 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M2 7l4 4 6-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
      <path d="M2 2l8 8M10 2L2 10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function RestoreIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M2.5 7a4.5 4.5 0 108 0" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M2.5 4.5V7H5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Category config ───────────────────────────────────────────────────────────

const CATEGORIES: { id: TaskCategory; label: string; color: string; bg: string }[] = [
  { id: "zone",       label: "Zone",     color: "#007AFF", bg: "rgba(0,122,255,0.10)" },
  { id: "rr",         label: "Restroom", color: "#34C759", bg: "rgba(52,199,89,0.10)" },
  { id: "aux",        label: "Aux",      color: "#FF9500", bg: "rgba(255,149,0,0.10)" },
  { id: "sweep",      label: "Sweep",    color: "#C9A84C", bg: "rgba(201,168,76,0.10)" },
  { id: "overlap_am", label: "AM Ovlp",  color: "#AF52DE", bg: "rgba(175,82,222,0.10)" },
  { id: "overlap_pm", label: "PM Ovlp",  color: "#FF3B30", bg: "rgba(255,59,48,0.10)" },
];

function catConfig(cat: string) {
  return CATEGORIES.find((c) => c.id === cat) ?? { id: cat as TaskCategory, label: cat, color: "#8E8E93", bg: "rgba(142,142,147,0.10)" };
}

function CategoryPill({ cat }: { cat: string }) {
  const cfg = catConfig(cat);
  return (
    <span
      className="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-semibold"
      style={{ color: cfg.color, backgroundColor: cfg.bg }}
    >
      {cfg.label}
    </span>
  );
}

// ── Top-level tabs ────────────────────────────────────────────────────────────

const TABS = [
  { id: "tasks",     label: "Tasks" },
  { id: "tab_config", label: "Task Tabs" },
  { id: "breaks",    label: "Break Schedule" },
];

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ControlPanelPage() {
  const [activeTab, setActiveTab] = useState<string>("tasks");

  return (
    <div className="flex flex-col min-h-dvh bg-[#F5F5F7]">
      <GlcrHeader
        title="Control Panel"
        right={
          <span className="text-[11px] font-semibold tracking-wide px-2.5 py-1 rounded-full bg-[#C9A84C]/20 text-[#C9A84C]">
            ZDS Admin
          </span>
        }
      />

      {/* Tab bar */}
      <div className="sticky top-0 z-20 bg-[#F5F5F7] border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-6 flex gap-0">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "px-5 py-3 text-[13px] font-semibold border-b-2 transition-colors no-select",
                activeTab === tab.id
                  ? "border-[#1A2340] text-[#1A2340]"
                  : "border-transparent text-gray-400 hover:text-gray-600",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-6">
        {activeTab === "tasks"      && <TasksTab />}
        {activeTab === "tab_config" && <TabConfigTab />}
        {activeTab === "breaks"     && <BreaksTab />}
      </main>
    </div>
  );
}

// ── Reporting field config ────────────────────────────────────────────────────

const LABOR_CATS: { id: LaborCategory; label: string; color: string }[] = [
  { id: "cleaning",   label: "Cleaning",   color: "#34C759" },
  { id: "inspection", label: "Inspection", color: "#007AFF" },
  { id: "coverage",   label: "Coverage",   color: "#C9A84C" },
  { id: "compliance", label: "Compliance", color: "#FF3B30" },
  { id: "security",   label: "Security",   color: "#AF52DE" },
  { id: "other",      label: "Other",      color: "#8E8E93" },
];

const FREQUENCIES: { id: TaskFrequency; label: string }[] = [
  { id: "once_per_shift", label: "Once per shift" },
  { id: "ongoing",        label: "Ongoing"        },
  { id: "as_needed",      label: "As needed"      },
];

const SHIFT_PHASES: { id: ShiftPhase; label: string }[] = [
  { id: "all",       label: "All shift"  },
  { id: "opening",   label: "Opening"   },
  { id: "mid_shift", label: "Mid-shift" },
  { id: "closing",   label: "Closing"   },
];

const DAY_LABELS: Record<string, string> = {
  fri: "F", sat: "Sa", sun: "Su", mon: "M", tue: "T", wed: "W", thu: "Th",
};

function laborColor(cat?: LaborCategory | null) {
  return LABOR_CATS.find((c) => c.id === cat)?.color ?? "#8E8E93";
}

// ══════════════════════════════════════════════════════════════════════════════
// Tasks Tab
// ══════════════════════════════════════════════════════════════════════════════

// ── Empty task editor state ───────────────────────────────────────────────────
interface EditState {
  name: string;
  category: TaskCategory;
  code: string;
  description: string;
  labor_category: LaborCategory | "";
  is_compliance_required: boolean;
  frequency: TaskFrequency;
  shift_phase: ShiftPhase;
  estimated_duration_min: string;
  days_active: DayCode[];
  notes: string;
}

const EMPTY_EDIT: EditState = {
  name: "", category: "zone", code: "", description: "",
  labor_category: "", is_compliance_required: false,
  frequency: "once_per_shift", shift_phase: "all",
  estimated_duration_min: "", days_active: [...DAY_CODES], notes: "",
};

function taskToEdit(t: ZoneTask): EditState {
  return {
    name:                   t.name,
    category:               t.category,
    code:                   t.code ?? "",
    description:            t.description ?? "",
    labor_category:         t.labor_category ?? "",
    is_compliance_required: t.is_compliance_required ?? false,
    frequency:              t.frequency ?? "once_per_shift",
    shift_phase:            t.shift_phase ?? "all",
    estimated_duration_min: t.estimated_duration_min != null ? String(t.estimated_duration_min) : "",
    days_active:            t.days_active ?? [...DAY_CODES],
    notes:                  t.notes ?? "",
  };
}

function TasksTab() {
  const { data: tasks, mutate, isLoading } = useSWR(
    "control:zone_tasks_all",
    fetchAllZoneTasks,
    { revalidateOnFocus: true },
  );
  const { mutate: globalMutate } = useSWRConfig();

  /** Bust every "forge:tasks:*" key so the night page sees changes immediately. */
  function bustTaskCache() {
    globalMutate(
      (key) => typeof key === "string" && key.startsWith("forge:tasks:"),
      undefined,
      { revalidate: true },
    );
  }

  const [filterCat,    setFilterCat]    = useState<string>("all");
  const [showInactive, setShowInactive] = useState(false);
  const [editingId,    setEditingId]    = useState<string | null>(null);
  const [addingNew,    setAddingNew]    = useState(false);
  const [savingId,     setSavingId]     = useState<string | null>(null);
  const [deletingId,   setDeletingId]   = useState<string | null>(null);
  const [error,        setError]        = useState<string | null>(null);
  const [reordering,   setReordering]   = useState(false);

  // Unified edit form (used for both edit and create)
  const [editState, setEditState] = useState<EditState>(EMPTY_EDIT);

  // Drag-to-reorder state
  const [localOrder, setLocalOrder]   = useState<ZoneTask[]>([]);
  const dragSrcIdx                    = useRef<number | null>(null);
  const dragOverIdx                   = useRef<number | null>(null);
  // Keep localOrder in sync with fetched tasks (but not while reordering)
  useEffect(() => {
    if (tasks && !reordering) setLocalOrder(tasks);
  }, [tasks, reordering]);

  const filtered = localOrder.filter((t) => {
    if (!showInactive && t.active === false) return false;
    if (filterCat !== "all" && t.category !== filterCat) return false;
    return true;
  });

  const grouped: Record<string, ZoneTask[]> = {};
  for (const t of filtered) { (grouped[t.category] ??= []).push(t); }

  function setField<K extends keyof EditState>(k: K, v: EditState[K]) {
    setEditState((p) => ({ ...p, [k]: v }));
  }

  function toggleDay(day: DayCode) {
    setEditState((p) => ({
      ...p,
      days_active: p.days_active.includes(day)
        ? p.days_active.filter((d) => d !== day)
        : [...p.days_active, day],
    }));
  }

  function startEdit(task: ZoneTask) {
    setEditingId(task.id);
    setEditState(taskToEdit(task));
    setError(null);
  }

  function cancelEdit() { setEditingId(null); setError(null); }

  function buildPatch(state: EditState) {
    return {
      name:                   state.name.trim(),
      category:               state.category,
      code:                   state.code.trim() || null,
      description:            state.description.trim() || null,
      labor_category:         (state.labor_category || null) as LaborCategory | null,
      is_compliance_required: state.is_compliance_required,
      frequency:              state.frequency,
      shift_phase:            state.shift_phase,
      estimated_duration_min: state.estimated_duration_min ? Number(state.estimated_duration_min) : null,
      days_active:            state.days_active,
      notes:                  state.notes.trim() || null,
    };
  }

  async function saveEdit(task: ZoneTask) {
    setSavingId(task.id);
    setError(null);
    try {
      await patchZoneTask(task.id, buildPatch(editState));
      await mutate();
      bustTaskCache();
      setEditingId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSavingId(null);
    }
  }

  async function handleDelete(task: ZoneTask) {
    if (!confirm(`Archive "${task.name}"? Historical assignments are preserved.`)) return;
    setDeletingId(task.id);
    try {
      await deleteZoneTask(task.id);
      await mutate();
      bustTaskCache();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleRestore(task: ZoneTask) {
    setSavingId(task.id);
    try {
      await patchZoneTask(task.id, { active: true });
      await mutate();
      bustTaskCache();
    } finally {
      setSavingId(null);
    }
  }

  async function handleCreate() {
    if (!editState.name.trim()) return;
    setSavingId("new");
    setError(null);
    try {
      await createZoneTask(buildPatch(editState) as any);
      await mutate();
      bustTaskCache();
      setEditState(EMPTY_EDIT);
      setAddingNew(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setSavingId(null);
    }
  }

  // ── Drag handlers ─────────────────────────────────────────────────────────

  function onDragStart(idx: number) { dragSrcIdx.current = idx; }

  function onDragOver(e: React.DragEvent, idx: number) {
    e.preventDefault();
    dragOverIdx.current = idx;
  }

  function onDrop(catTasks: ZoneTask[]) {
    const src = dragSrcIdx.current;
    const dst = dragOverIdx.current;
    dragSrcIdx.current = null;
    dragOverIdx.current = null;
    if (src === null || dst === null || src === dst) return;

    // Reorder within this category slice
    const next = [...catTasks];
    const [moved] = next.splice(src, 1);
    next.splice(dst, 0, moved);

    // Merge back into localOrder (other categories unchanged)
    const catSet = new Set(catTasks.map((t) => t.id));
    const others = localOrder.filter((t) => !catSet.has(t.id));
    // Reconstruct full order: non-cat tasks interleaved by original position,
    // with this category's new order inserted at the position of the first cat task
    const firstCatIdx = localOrder.findIndex((t) => catSet.has(t.id));
    const newOrder = [
      ...localOrder.slice(0, firstCatIdx).filter((t) => !catSet.has(t.id)),
      ...next,
      ...localOrder.slice(firstCatIdx).filter((t) => !catSet.has(t.id)),
    ];
    setLocalOrder(newOrder);

    // Persist — fire-and-forget, mutate to confirm
    setReordering(true);
    reorderZoneTasks(newOrder.map((t) => t.id))
      .then(() => { mutate(); bustTaskCache(); })
      .catch((e) => setError(e.message))
      .finally(() => setReordering(false));
  }

  const activeCats = filterCat === "all"
    ? CATEGORIES.map((c) => c.id)
    : [filterCat as TaskCategory];

  return (
    <div className="flex flex-col gap-5">
      {/* Controls row */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setFilterCat("all")}
            className={cn("h-7 px-3 rounded-full text-[12px] font-semibold transition-colors no-select",
              filterCat === "all" ? "bg-[#1A2340] text-white" : "bg-white text-gray-500 border border-gray-200 hover:border-gray-300")}
          >All</button>
          {CATEGORIES.map((cat) => (
            <button key={cat.id} onClick={() => setFilterCat(cat.id)}
              className="h-7 px-3 rounded-full text-[12px] font-semibold transition-colors no-select"
              style={filterCat === cat.id ? { backgroundColor: cat.color, color: "#fff" } : { backgroundColor: cat.bg, color: cat.color }}>
              {cat.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <label className="flex items-center gap-1.5 text-[12px] text-gray-500 cursor-pointer select-none">
            <input type="checkbox" checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)} className="accent-[#1A2340]" />
            Show archived
          </label>
          <button
            onClick={() => { setAddingNew(true); setEditState(EMPTY_EDIT); }}
            className="flex items-center gap-1.5 h-8 px-4 rounded-xl text-[13px] font-semibold bg-[#1A2340] text-white hover:bg-[#2a3a60] active:scale-95 transition-all duration-100 no-select">
            <PlusIcon /> Add Task
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="px-4 py-3 rounded-2xl bg-red-50 border border-red-100 text-red-600 text-sm flex items-center justify-between gap-3">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600"><XIcon /></button>
        </div>
      )}

      {/* New / Edit task form */}
      {(addingNew || editingId) && (
        <TaskEditForm
          state={editState}
          isNew={addingNew}
          saving={savingId === "new" || (editingId != null && savingId === editingId)}
          onChange={setField}
          onToggleDay={toggleDay}
          onSave={editingId ? () => { const t = tasks?.find(t => t.id === editingId); if (t) saveEdit(t); } : handleCreate}
          onCancel={() => { setAddingNew(false); setEditingId(null); setError(null); }}
        />
      )}

      {/* Skeleton */}
      {isLoading && !tasks && (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-14 rounded-2xl shimmer-bg" style={{ animationDelay: `${i * 0.06}s` }} />
          ))}
        </div>
      )}

      {!isLoading && filtered.length === 0 && (
        <div className="text-center py-16 text-gray-400 text-sm">
          {showInactive ? "No tasks found." : "No active tasks in this category."}
        </div>
      )}

      {/* Task groups */}
      {activeCats.map((catId) => {
        const rows = grouped[catId];
        if (!rows?.length) return null;
        const cfg = catConfig(catId);
        return (
          <div key={catId} className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-4 py-2.5 flex items-center gap-2 border-b"
              style={{ backgroundColor: cfg.bg, borderColor: `${cfg.color}22` }}>
              <span className="text-[12px] font-bold tracking-wide" style={{ color: cfg.color }}>
                {cfg.label.toUpperCase()}
              </span>
              <span className="text-[11px] font-medium" style={{ color: cfg.color, opacity: 0.7 }}>
                {rows.length} task{rows.length !== 1 ? "s" : ""}
              </span>
              <span className="ml-auto text-[10px] text-gray-300 font-medium">drag to reorder</span>
            </div>
            <div className="divide-y divide-gray-50">
              {rows.map((task, rowIdx) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  idx={rowIdx}
                  isEditing={editingId === task.id}
                  isSaving={savingId === task.id}
                  isDeleting={deletingId === task.id}
                  onStartEdit={() => { setAddingNew(false); startEdit(task); }}
                  onCancelEdit={cancelEdit}
                  onDelete={() => handleDelete(task)}
                  onRestore={() => handleRestore(task)}
                  onDragStart={() => onDragStart(rowIdx)}
                  onDragOver={(e) => onDragOver(e, rowIdx)}
                  onDrop={() => onDrop(rows)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Task edit form (shared for create + edit) ─────────────────────────────────

interface TaskEditFormProps {
  state: EditState;
  isNew: boolean;
  saving: boolean;
  onChange: <K extends keyof EditState>(k: K, v: EditState[K]) => void;
  onToggleDay: (day: DayCode) => void;
  onSave: () => void;
  onCancel: () => void;
}

function TaskEditForm({ state, isNew, saving, onChange, onToggleDay, onSave, onCancel }: TaskEditFormProps) {
  const inputCls = "w-full h-9 px-3 rounded-xl border border-gray-200 text-[13px] focus:outline-none focus:border-[#1A2340] bg-white";
  const selectCls = "w-full h-9 px-2 rounded-xl border border-gray-200 text-[13px] bg-white focus:outline-none focus:border-[#1A2340]";
  const labelCls = "block text-[11px] font-semibold text-gray-400 mb-1 uppercase tracking-wide";

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-[#C9A84C]/40 overflow-hidden">
      <div className="px-4 py-3 border-b border-[#C9A84C]/20 flex items-center justify-between">
        <span className="text-[13px] font-semibold text-[#8B6914]">{isNew ? "New Task" : "Edit Task"}</span>
        <button onClick={onCancel} className="text-gray-400 hover:text-gray-600"><XIcon /></button>
      </div>

      <div className="p-4 flex flex-col gap-4">
        {/* Row 1: Name + Category + Code */}
        <div className="flex flex-wrap gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className={labelCls}>Name *</label>
            <input type="text" value={state.name}
              onChange={(e) => onChange("name", e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") onSave(); if (e.key === "Escape") onCancel(); }}
              placeholder="Task name…" className={inputCls} autoFocus={isNew} />
          </div>
          <div className="w-36">
            <label className={labelCls}>Category</label>
            <select value={state.category} onChange={(e) => onChange("category", e.target.value as TaskCategory)} className={selectCls}>
              {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
          </div>
          <div className="w-24">
            <label className={labelCls}>Code</label>
            <input type="text" value={state.code} onChange={(e) => onChange("code", e.target.value)}
              placeholder="e.g. Z9" className={inputCls} />
          </div>
        </div>

        {/* Row 2: Labor cat + Frequency + Phase + Duration */}
        <div className="flex flex-wrap gap-3">
          <div className="w-36">
            <label className={labelCls}>Labor Category</label>
            <select value={state.labor_category}
              onChange={(e) => onChange("labor_category", e.target.value as LaborCategory | "")} className={selectCls}>
              <option value="">— none —</option>
              {LABOR_CATS.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
          </div>
          <div className="w-36">
            <label className={labelCls}>Frequency</label>
            <select value={state.frequency} onChange={(e) => onChange("frequency", e.target.value as TaskFrequency)} className={selectCls}>
              {FREQUENCIES.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
            </select>
          </div>
          <div className="w-32">
            <label className={labelCls}>Shift Phase</label>
            <select value={state.shift_phase} onChange={(e) => onChange("shift_phase", e.target.value as ShiftPhase)} className={selectCls}>
              {SHIFT_PHASES.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </div>
          <div className="w-28">
            <label className={labelCls}>Duration (min)</label>
            <input type="number" min={1} max={480} value={state.estimated_duration_min}
              onChange={(e) => onChange("estimated_duration_min", e.target.value)}
              placeholder="e.g. 30" className={inputCls} />
          </div>
          {/* Compliance toggle */}
          <div className="flex flex-col justify-end pb-0.5">
            <label className={labelCls}>Compliance</label>
            <button
              onClick={() => onChange("is_compliance_required", !state.is_compliance_required)}
              className={cn("h-9 px-3 rounded-xl border text-[12px] font-semibold transition-colors flex items-center gap-1.5",
                state.is_compliance_required
                  ? "bg-red-50 border-red-200 text-red-600"
                  : "bg-white border-gray-200 text-gray-400 hover:border-gray-300")}
            >
              {state.is_compliance_required ? "✓ Required" : "Not required"}
            </button>
          </div>
        </div>

        {/* Row 3: Days active */}
        <div>
          <label className={labelCls}>Days Active</label>
          <div className="flex gap-1.5 flex-wrap">
            {DAY_CODES.map((day) => {
              const active = state.days_active.includes(day);
              return (
                <button key={day} onClick={() => onToggleDay(day)}
                  className={cn("w-9 h-9 rounded-xl text-[11px] font-bold transition-colors",
                    active ? "bg-[#1A2340] text-white" : "bg-gray-100 text-gray-400 hover:bg-gray-200")}>
                  {DAY_LABELS[day]}
                </button>
              );
            })}
            <button onClick={() => onChange("days_active", [...DAY_CODES])}
              className="h-9 px-2.5 rounded-xl text-[11px] text-gray-400 hover:bg-gray-100 transition-colors">
              All
            </button>
          </div>
        </div>

        {/* Row 4: Description + Notes */}
        <div className="flex flex-wrap gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className={labelCls}>Description</label>
            <textarea value={state.description} onChange={(e) => onChange("description", e.target.value)}
              rows={2} placeholder="Short description shown in task picker…"
              className="w-full px-3 py-2 rounded-xl border border-gray-200 text-[13px] focus:outline-none focus:border-[#1A2340] bg-white resize-none" />
          </div>
          <div className="flex-1 min-w-[160px]">
            <label className={labelCls}>Internal Notes</label>
            <textarea value={state.notes} onChange={(e) => onChange("notes", e.target.value)}
              rows={2} placeholder="Reporting notes, instructions…"
              className="w-full px-3 py-2 rounded-xl border border-gray-200 text-[13px] focus:outline-none focus:border-[#1A2340] bg-white resize-none" />
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-1">
          <button onClick={onSave} disabled={saving || !state.name.trim()}
            className="h-9 px-5 rounded-xl bg-[#1A2340] text-white text-[13px] font-semibold disabled:opacity-40 hover:bg-[#2a3a60] active:scale-95 transition-all">
            {saving ? "Saving…" : isNew ? "Create Task" : "Save Changes"}
          </button>
          <button onClick={onCancel} className="h-9 px-4 rounded-xl text-gray-500 hover:bg-gray-100 text-[13px]">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Task row ──────────────────────────────────────────────────────────────────

interface TaskRowProps {
  task: ZoneTask;
  idx: number;
  isEditing: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onDelete: () => void;
  onRestore: () => void;
  onDragStart: () => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: () => void;
}

function TaskRow({ task, isEditing, isSaving, isDeleting, onStartEdit, onCancelEdit, onDelete, onRestore, onDragStart, onDragOver, onDrop }: TaskRowProps) {
  const inactive = task.active === false;

  return (
    <div
      draggable={!inactive}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
      className={cn(
        "px-3 py-2.5 flex items-center gap-2.5 group transition-colors",
        inactive ? "opacity-40" : "hover:bg-gray-50/70 cursor-grab active:cursor-grabbing",
        isEditing && "bg-blue-50/40",
      )}
    >
      {/* Drag handle */}
      {!inactive && (
        <div className="text-gray-200 group-hover:text-gray-350 transition-colors shrink-0 cursor-grab">
          <svg width="10" height="14" viewBox="0 0 10 14" fill="none">
            <circle cx="3" cy="2.5" r="1.2" fill="currentColor"/>
            <circle cx="7" cy="2.5" r="1.2" fill="currentColor"/>
            <circle cx="3" cy="7"   r="1.2" fill="currentColor"/>
            <circle cx="7" cy="7"   r="1.2" fill="currentColor"/>
            <circle cx="3" cy="11.5" r="1.2" fill="currentColor"/>
            <circle cx="7" cy="11.5" r="1.2" fill="currentColor"/>
          </svg>
        </div>
      )}

      {/* Name */}
      <span className={cn("flex-1 text-[13px] font-medium truncate", inactive && "line-through text-gray-400")}>
        {task.name}
      </span>

      {/* Reporting badges (shown on non-hover, compact) */}
      <div className="flex items-center gap-1.5 shrink-0 opacity-70 group-hover:opacity-0 transition-opacity">
        {task.labor_category && (
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md"
            style={{ color: laborColor(task.labor_category), backgroundColor: `${laborColor(task.labor_category)}18` }}>
            {task.labor_category}
          </span>
        )}
        {task.is_compliance_required && (
          <span className="text-[10px] font-bold text-red-500 bg-red-50 px-1.5 py-0.5 rounded-md">C</span>
        )}
        {task.frequency && task.frequency !== "once_per_shift" && (
          <span className="text-[10px] text-gray-400 font-medium">
            {task.frequency === "ongoing" ? "∞" : "?"}
          </span>
        )}
        {task.code && (
          <span className="text-[10px] font-mono text-gray-400">{task.code}</span>
        )}
        <CategoryPill cat={task.category ?? ""} />
      </div>

      {/* Actions — shown on hover */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        {inactive ? (
          <button onClick={onRestore} disabled={isSaving} title="Restore"
            className="w-7 h-7 rounded-lg flex items-center justify-center text-emerald-500 hover:bg-emerald-50 disabled:opacity-50 transition-colors">
            <RestoreIcon />
          </button>
        ) : (
          <>
            <button onClick={onStartEdit} title="Edit"
              className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 hover:text-[#1A2340] transition-colors">
              <PencilIcon />
            </button>
            <button onClick={onDelete} disabled={isDeleting} title="Archive"
              className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:bg-red-50 hover:text-red-500 disabled:opacity-50 transition-colors">
              {isDeleting ? <span className="text-[10px]">…</span> : <TrashIcon />}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// Tab Config Tab
// ══════════════════════════════════════════════════════════════════════════════

const ALL_CATS: { id: TaskCategory; label: string; color: string }[] = [
  { id: "zone",       label: "Zone",         color: "#007AFF" },
  { id: "rr",         label: "Restroom",     color: "#34C759" },
  { id: "aux",        label: "Aux",          color: "#FF9500" },
  { id: "sweep",      label: "Sweep",        color: "#C9A84C" },
  { id: "overlap_am", label: "AM Overlap",   color: "#AF52DE" },
  { id: "overlap_pm", label: "PM Overlap",   color: "#FF3B30" },
];

function TabConfigTab() {
  const { data: savedTabs, mutate, isLoading } = useSWR(
    "control:tab_config",
    fetchTabConfig,
    { revalidateOnFocus: true },
  );

  // Local working copy — editable before saving
  const [tabs, setTabs] = useState<TaskTab[]>([]);
  const [dirty, setDirty]   = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Sync local state when DB data loads (only if not currently editing)
  useEffect(() => {
    if (savedTabs && !dirty) {
      setTabs(savedTabs.map((t) => ({ ...t, cats: [...t.cats] })));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedTabs]);

  function markDirty() { setDirty(true); setSuccess(false); }

  function moveTab(idx: number, dir: -1 | 1) {
    const next = [...tabs];
    const target = idx + dir;
    if (target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    setTabs(next);
    markDirty();
  }

  function updateLabel(idx: number, label: string) {
    const next = [...tabs];
    next[idx] = { ...next[idx], label };
    setTabs(next);
    markDirty();
  }

  function toggleCat(tabIdx: number, cat: TaskCategory) {
    const next = tabs.map((t, i) => {
      if (i !== tabIdx) return t;
      const cats = t.cats.includes(cat)
        ? t.cats.filter((c) => c !== cat)
        : [...t.cats, cat];
      return { ...t, cats };
    });
    setTabs(next);
    markDirty();
  }

  function addTab() {
    const newTab: TaskTab = {
      id:    `tab_${Date.now()}`,
      label: "New Tab",
      cats:  [],
    };
    setTabs([...tabs, newTab]);
    markDirty();
  }

  function removeTab(idx: number) {
    if (tabs.length <= 1) return;
    if (!confirm(`Remove the "${tabs[idx].label}" tab?`)) return;
    setTabs(tabs.filter((_, i) => i !== idx));
    markDirty();
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await patchTabConfig(tabs);
      await mutate();
      setDirty(false);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    if (!savedTabs) return;
    setTabs(savedTabs.map((t) => ({ ...t, cats: [...t.cats] })));
    setDirty(false);
    setError(null);
  }

  if (isLoading && !savedTabs) {
    return (
      <div className="flex flex-col gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 rounded-2xl shimmer-bg" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Explanation */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm px-5 py-4">
        <div className="text-[13px] font-semibold text-gray-700 mb-1">Task Picker Tabs</div>
        <div className="text-[12px] text-gray-400 leading-relaxed">
          Configure which tabs appear in the day planner task picker and which task categories each tab shows.
          Drag tabs up/down to reorder. Changes take effect immediately after saving.
        </div>
      </div>

      {/* Error / success banners */}
      {error && (
        <div className="px-4 py-3 rounded-2xl bg-red-50 border border-red-100 text-red-600 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 ml-3"><XIcon /></button>
        </div>
      )}
      {success && (
        <div className="px-4 py-3 rounded-2xl bg-emerald-50 border border-emerald-100 text-emerald-700 text-sm font-medium">
          Tab configuration saved — the day planner will pick it up on next load.
        </div>
      )}

      {/* Tab cards */}
      <div className="flex flex-col gap-3">
        {tabs.map((tab, idx) => (
          <div
            key={tab.id}
            className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden"
          >
            {/* Tab header */}
            <div className="px-4 py-3 flex items-center gap-3 border-b border-gray-50">
              {/* Move arrows */}
              <div className="flex flex-col gap-0.5 shrink-0">
                <button
                  onClick={() => moveTab(idx, -1)}
                  disabled={idx === 0}
                  className="w-6 h-5 rounded flex items-center justify-center text-gray-300 hover:text-gray-500 disabled:opacity-20 transition-colors"
                >
                  <svg width="10" height="7" viewBox="0 0 10 7" fill="none">
                    <path d="M1 6l4-4 4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                <button
                  onClick={() => moveTab(idx, 1)}
                  disabled={idx === tabs.length - 1}
                  className="w-6 h-5 rounded flex items-center justify-center text-gray-300 hover:text-gray-500 disabled:opacity-20 transition-colors"
                >
                  <svg width="10" height="7" viewBox="0 0 10 7" fill="none">
                    <path d="M1 1l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </div>

              {/* Tab position badge */}
              <span className="w-5 h-5 rounded-full bg-gray-100 text-[10px] font-bold text-gray-400 flex items-center justify-center shrink-0">
                {idx + 1}
              </span>

              {/* Label input */}
              <input
                type="text"
                value={tab.label}
                onChange={(e) => updateLabel(idx, e.target.value)}
                className="flex-1 h-8 px-3 rounded-lg border border-gray-200 text-[13px] font-semibold focus:outline-none focus:border-[#1A2340] bg-gray-50"
                placeholder="Tab name…"
              />

              {/* Remove button */}
              <button
                onClick={() => removeTab(idx)}
                disabled={tabs.length <= 1}
                title="Remove tab"
                className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-300 hover:bg-red-50 hover:text-red-400 disabled:opacity-20 transition-colors"
              >
                <TrashIcon />
              </button>
            </div>

            {/* Category checkboxes */}
            <div className="px-4 py-3 flex flex-wrap gap-2">
              {ALL_CATS.map((cat) => {
                const checked = tab.cats.includes(cat.id);
                return (
                  <button
                    key={cat.id}
                    onClick={() => toggleCat(idx, cat.id)}
                    className={cn(
                      "flex items-center gap-1.5 h-7 px-3 rounded-full text-[12px] font-semibold transition-all border",
                      checked
                        ? "text-white border-transparent"
                        : "bg-white border-gray-200 text-gray-400 hover:border-gray-300",
                    )}
                    style={checked ? { backgroundColor: cat.color, borderColor: cat.color } : {}}
                  >
                    {checked && (
                      <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                        <path d="M1 4l3 3 5-6" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                    {cat.label}
                  </button>
                );
              })}
              {tab.cats.length === 0 && (
                <span className="text-[11px] text-gray-300 italic self-center">No categories — tasks won't appear on this tab</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Add tab */}
      <button
        onClick={addTab}
        className="flex items-center justify-center gap-2 h-11 rounded-2xl border-2 border-dashed border-gray-200 text-[13px] font-semibold text-gray-400 hover:border-gray-300 hover:text-gray-500 transition-colors"
      >
        <PlusIcon /> Add Tab
      </button>

      {/* Save / Reset bar */}
      {dirty && (
        <div className="sticky bottom-4 flex items-center justify-between gap-3 bg-[#1A2340] text-white px-5 py-3 rounded-2xl shadow-xl">
          <span className="text-[13px] font-medium text-white/70">You have unsaved changes</span>
          <div className="flex gap-2">
            <button
              onClick={handleReset}
              className="h-9 px-4 rounded-xl text-white/60 hover:text-white text-[13px] transition-colors"
            >
              Reset
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="h-9 px-5 rounded-xl bg-[#C9A84C] text-white text-[13px] font-semibold disabled:opacity-50 hover:bg-[#b8973d] transition-colors"
            >
              {saving ? "Saving…" : "Save Changes"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// Break Schedule Tab
// ══════════════════════════════════════════════════════════════════════════════

const GROUPS  = ["1", "2", "3"] as const;
const WAVES   = ["1", "2", "3"] as const;

const WAVE_COLORS: Record<string, string> = {
  "1": "#60a5fa",   // blue   — First Break
  "2": "#a78bfa",   // purple — Main Break
  "3": "#34d399",   // green  — Last Break
};

const GROUP_COLORS: Record<string, string> = {
  "1": "#C9A84C",
  "2": "#007AFF",
  "3": "#34C759",
};

/** Parse "HH:MM" into total minutes from midnight */
function timeToMins(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

/** Format total minutes (may be > 24h for early-AM times) back to "HH:MM" */
function minsToTime(mins: number): string {
  const h = Math.floor(mins / 60) % 24;
  const m = mins % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** Display a 24h "HH:MM" string as 12h "h:MM AM/PM" */
function fmt12(t: string): string {
  const [hStr, mStr] = t.split(":");
  let h = parseInt(hStr, 10);
  const m = mStr;
  const period = h < 12 ? "AM" : "PM";
  if (h === 0) h = 12;
  else if (h > 12) h -= 12;
  return `${h}:${m} ${period}`;
}

/** Deep-clone a BreakSchedule so edits don't mutate SWR cache */
function cloneSchedule(s: BreakSchedule): BreakSchedule {
  return {
    wave_labels: { ...s.wave_labels },
    times: Object.fromEntries(
      Object.entries(s.times).map(([g, waves]) => [
        g,
        Object.fromEntries(
          Object.entries(waves).map(([w, slot]) => [w, [...slot] as BreakSlot])
        ),
      ])
    ),
  };
}

function BreaksTab() {
  const { data: savedSchedule, mutate, isLoading } = useSWR(
    "control:break_schedule",
    fetchBreakSchedule,
    { revalidateOnFocus: true },
  );

  const [schedule, setSchedule] = useState<BreakSchedule>(DEFAULT_BREAK_SCHEDULE);
  const [dirty, setDirty]     = useState(false);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (savedSchedule && !dirty) {
      setSchedule(cloneSchedule(savedSchedule));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedSchedule]);

  function markDirty() { setDirty(true); setSuccess(false); }

  function updateWaveLabel(waveId: string, label: string) {
    setSchedule((prev) => ({
      ...prev,
      wave_labels: { ...prev.wave_labels, [waveId]: label },
    }));
    markDirty();
  }

  function updateSlotStart(grp: string, wave: string, start: string) {
    setSchedule((prev) => {
      const next = cloneSchedule(prev);
      const slot = next.times[grp][wave];
      const startMins = timeToMins(start);
      const dur       = slot[2];
      const endMins   = (startMins + dur) % (24 * 60);
      next.times[grp][wave] = [start, minsToTime(endMins), dur];
      return next;
    });
    markDirty();
  }

  function updateSlotDuration(grp: string, wave: string, dur: number) {
    setSchedule((prev) => {
      const next = cloneSchedule(prev);
      const slot  = next.times[grp][wave];
      const startMins = timeToMins(slot[0]);
      const endMins   = (startMins + dur) % (24 * 60);
      next.times[grp][wave] = [slot[0], minsToTime(endMins), dur];
      return next;
    });
    markDirty();
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await patchBreakSchedule(schedule);
      await mutate();
      setDirty(false);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    if (!savedSchedule) return;
    setSchedule(cloneSchedule(savedSchedule));
    setDirty(false);
    setError(null);
  }

  if (isLoading && !savedSchedule) {
    return (
      <div className="flex flex-col gap-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-40 rounded-2xl shimmer-bg" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Header card */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm px-5 py-4">
        <div className="text-[13px] font-semibold text-gray-700 mb-1">Break Schedule</div>
        <div className="text-[12px] text-gray-400 leading-relaxed">
          3 groups × 3 waves. Each group's TMs take their breaks together.
          Changing start time auto-adjusts end time by the same duration. Times are 24-hour (graves shift spans midnight).
        </div>
      </div>

      {/* Wave label editors */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-4 py-2.5 border-b border-gray-50 text-[11px] font-bold uppercase tracking-wide text-gray-400">
          Wave Labels
        </div>
        <div className="px-4 py-3 flex flex-wrap gap-3">
          {WAVES.map((waveId) => (
            <div key={waveId} className="flex items-center gap-2">
              <div
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ background: WAVE_COLORS[waveId] }}
              />
              <input
                type="text"
                value={schedule.wave_labels?.[waveId] ?? ""}
                onChange={(e) => updateWaveLabel(waveId, e.target.value)}
                className="w-36 h-8 px-3 rounded-lg border border-gray-200 text-[13px] font-medium focus:outline-none focus:border-[#1A2340] bg-gray-50"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Error / success */}
      {error && (
        <div className="px-4 py-3 rounded-2xl bg-red-50 border border-red-100 text-red-600 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-3 text-red-400 hover:text-red-600"><XIcon /></button>
        </div>
      )}
      {success && (
        <div className="px-4 py-3 rounded-2xl bg-emerald-50 border border-emerald-100 text-emerald-700 text-sm font-medium">
          Break schedule saved — the break sheet will pick it up on next load.
        </div>
      )}

      {/* Group grid */}
      {GROUPS.map((grpId) => (
        <div key={grpId} className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          {/* Group header */}
          <div
            className="px-4 py-2.5 flex items-center gap-2 border-b"
            style={{ borderColor: `${GROUP_COLORS[grpId]}22`, backgroundColor: `${GROUP_COLORS[grpId]}10` }}
          >
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: GROUP_COLORS[grpId] }} />
            <span className="text-[12px] font-bold tracking-wide" style={{ color: GROUP_COLORS[grpId] }}>
              GROUP {grpId}
            </span>
          </div>

          {/* Wave rows */}
          <div className="divide-y divide-gray-50">
            {WAVES.map((waveId) => {
              const slot = schedule.times?.[grpId]?.[waveId]
                ?? DEFAULT_BREAK_SCHEDULE.times[grpId][waveId];
              const [start, end, dur] = slot;
              const label = schedule.wave_labels?.[waveId] ?? waveId;

              return (
                <div key={waveId} className="px-4 py-3 flex items-center gap-4 flex-wrap">
                  {/* Wave dot + label */}
                  <div className="flex items-center gap-2 w-28 shrink-0">
                    <div className="w-2 h-2 rounded-full shrink-0" style={{ background: WAVE_COLORS[waveId] }} />
                    <span className="text-[12px] font-semibold text-gray-600 truncate">{label}</span>
                  </div>

                  {/* Start time */}
                  <div className="flex flex-col gap-0.5">
                    <label className="text-[10px] font-medium text-gray-400">Start</label>
                    <input
                      type="time"
                      value={start}
                      onChange={(e) => updateSlotStart(grpId, waveId, e.target.value)}
                      className="h-9 px-2.5 rounded-lg border border-gray-200 text-[13px] font-mono focus:outline-none focus:border-[#1A2340] bg-gray-50 w-28"
                    />
                  </div>

                  {/* Arrow */}
                  <svg width="16" height="10" viewBox="0 0 16 10" fill="none" className="text-gray-300 shrink-0 mt-3">
                    <path d="M1 5h12M9 1l4 4-4 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>

                  {/* End time (computed, read-only) */}
                  <div className="flex flex-col gap-0.5">
                    <label className="text-[10px] font-medium text-gray-400">End</label>
                    <div className="h-9 px-2.5 rounded-lg border border-gray-100 text-[13px] font-mono text-gray-400 bg-gray-50 flex items-center w-28">
                      {end}
                    </div>
                  </div>

                  {/* Duration */}
                  <div className="flex flex-col gap-0.5">
                    <label className="text-[10px] font-medium text-gray-400">Duration (min)</label>
                    <input
                      type="number"
                      min={5}
                      max={60}
                      step={5}
                      value={dur}
                      onChange={(e) => updateSlotDuration(grpId, waveId, parseInt(e.target.value, 10) || dur)}
                      className="h-9 px-2.5 rounded-lg border border-gray-200 text-[13px] font-mono focus:outline-none focus:border-[#1A2340] bg-gray-50 w-24"
                    />
                  </div>

                  {/* 12h preview */}
                  <div className="text-[12px] text-gray-400 font-medium mt-3 shrink-0">
                    {fmt12(start)} – {fmt12(end)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* Save / Reset bar */}
      {dirty && (
        <div className="sticky bottom-4 flex items-center justify-between gap-3 bg-[#1A2340] text-white px-5 py-3 rounded-2xl shadow-xl">
          <span className="text-[13px] font-medium text-white/70">You have unsaved changes</span>
          <div className="flex gap-2">
            <button
              onClick={handleReset}
              className="h-9 px-4 rounded-xl text-white/60 hover:text-white text-[13px] transition-colors"
            >
              Reset
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="h-9 px-5 rounded-xl bg-[#C9A84C] text-white text-[13px] font-semibold disabled:opacity-50 hover:bg-[#b8973d] transition-colors"
            >
              {saving ? "Saving…" : "Save Changes"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
