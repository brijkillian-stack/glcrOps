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
import useSWR from "swr";
import { GlcrHeader } from "@/components/ui/GlcrHeader";
import {
  fetchAllZoneTasks,
  createZoneTask,
  patchZoneTask,
  deleteZoneTask,
  fetchTabConfig,
  patchTabConfig,
  type ZoneTask,
  type TaskCategory,
  type TaskTab,
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

// ══════════════════════════════════════════════════════════════════════════════
// Tasks Tab
// ══════════════════════════════════════════════════════════════════════════════

function TasksTab() {
  const { data: tasks, mutate, isLoading } = useSWR(
    "control:zone_tasks_all",
    fetchAllZoneTasks,
    { revalidateOnFocus: true },
  );

  const [filterCat, setFilterCat] = useState<string>("all");
  const [showInactive, setShowInactive] = useState(false);
  const [editingId, setEditingId]     = useState<string | null>(null);
  const [addingNew, setAddingNew]     = useState(false);
  const [savingId, setSavingId]       = useState<string | null>(null);
  const [deletingId, setDeletingId]   = useState<string | null>(null);
  const [error, setError]             = useState<string | null>(null);

  // Edit form state
  const [editName, setEditName]           = useState("");
  const [editCategory, setEditCategory]   = useState<TaskCategory>("zone");
  const [editCode, setEditCode]           = useState("");
  const [editOrder, setEditOrder]         = useState<number>(100);

  // New task form
  const [newName, setNewName]         = useState("");
  const [newCategory, setNewCategory] = useState<TaskCategory>("zone");
  const [newCode, setNewCode]         = useState("");
  const [newOrder, setNewOrder]       = useState<number>(100);
  const [creating, setCreating]       = useState(false);

  const newNameRef = useRef<HTMLInputElement>(null);

  const filtered = (tasks ?? []).filter((t) => {
    if (!showInactive && !t.active) return false;
    if (filterCat !== "all" && t.category !== filterCat) return false;
    return true;
  });

  // Group by category for display
  const grouped: Record<string, ZoneTask[]> = {};
  for (const t of filtered) {
    (grouped[t.category] ??= []).push(t);
  }

  function startEdit(task: ZoneTask) {
    setEditingId(task.id);
    setEditName(task.name);
    setEditCategory((task.category as TaskCategory) ?? "zone");
    setEditCode(task.code ?? "");
    setEditOrder(task.display_order ?? 100);
  }

  function cancelEdit() {
    setEditingId(null);
    setError(null);
  }

  async function saveEdit(task: ZoneTask) {
    setSavingId(task.id);
    setError(null);
    try {
      await patchZoneTask(task.id, {
        name:          editName.trim(),
        category:      editCategory,
        code:          editCode.trim() || undefined,
        display_order: editOrder,
      });
      await mutate();
      setEditingId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSavingId(null);
    }
  }

  async function handleDelete(task: ZoneTask) {
    if (!confirm(`Archive "${task.name}"? It will be hidden from task lists but historical assignments are preserved.`)) return;
    setDeletingId(task.id);
    setError(null);
    try {
      await deleteZoneTask(task.id);
      await mutate();
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Restore failed");
    } finally {
      setSavingId(null);
    }
  }

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await createZoneTask({
        name:          newName.trim(),
        category:      newCategory,
        code:          newCode.trim() || undefined,
        display_order: newOrder,
      });
      await mutate();
      setNewName("");
      setNewCode("");
      setNewOrder(100);
      setAddingNew(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  const activeCats = filterCat === "all"
    ? CATEGORIES.map((c) => c.id)
    : [filterCat as TaskCategory];

  return (
    <div className="flex flex-col gap-5">
      {/* Controls row */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Category filter pills */}
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setFilterCat("all")}
            className={cn(
              "h-7 px-3 rounded-full text-[12px] font-semibold transition-colors no-select",
              filterCat === "all"
                ? "bg-[#1A2340] text-white"
                : "bg-white text-gray-500 border border-gray-200 hover:border-gray-300",
            )}
          >
            All
          </button>
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setFilterCat(cat.id)}
              className="h-7 px-3 rounded-full text-[12px] font-semibold transition-colors no-select"
              style={
                filterCat === cat.id
                  ? { backgroundColor: cat.color, color: "#fff" }
                  : { backgroundColor: cat.bg, color: cat.color }
              }
            >
              {cat.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 ml-auto">
          {/* Show inactive toggle */}
          <label className="flex items-center gap-1.5 text-[12px] text-gray-500 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="accent-[#1A2340]"
            />
            Show archived
          </label>

          {/* Add button */}
          <button
            onClick={() => { setAddingNew(true); setTimeout(() => newNameRef.current?.focus(), 50); }}
            className="flex items-center gap-1.5 h-8 px-4 rounded-xl text-[13px] font-semibold bg-[#1A2340] text-white hover:bg-[#2a3a60] active:scale-95 transition-all duration-100 no-select"
          >
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

      {/* New task row */}
      {addingNew && (
        <div className="bg-white rounded-2xl shadow-sm border border-[#C9A84C]/40 overflow-hidden">
          <div className="px-4 py-3 bg-[#C9A84C]/08 border-b border-[#C9A84C]/20 text-[13px] font-semibold text-[#8B6914]">
            New Task
          </div>
          <div className="p-4 flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[180px]">
              <label className="block text-[11px] font-medium text-gray-500 mb-1">Name *</label>
              <input
                ref={newNameRef}
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); if (e.key === "Escape") setAddingNew(false); }}
                placeholder="Task name…"
                className="w-full h-9 px-3 rounded-xl border border-gray-200 text-[13px] focus:outline-none focus:border-[#1A2340]"
              />
            </div>
            <div className="w-36">
              <label className="block text-[11px] font-medium text-gray-500 mb-1">Category</label>
              <select
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value as TaskCategory)}
                className="w-full h-9 px-2 rounded-xl border border-gray-200 text-[13px] bg-white focus:outline-none focus:border-[#1A2340]"
              >
                {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
            </div>
            <div className="w-24">
              <label className="block text-[11px] font-medium text-gray-500 mb-1">Code</label>
              <input
                type="text"
                value={newCode}
                onChange={(e) => setNewCode(e.target.value)}
                placeholder="e.g. Z9"
                className="w-full h-9 px-3 rounded-xl border border-gray-200 text-[13px] focus:outline-none focus:border-[#1A2340]"
              />
            </div>
            <div className="w-24">
              <label className="block text-[11px] font-medium text-gray-500 mb-1">Order</label>
              <input
                type="number"
                value={newOrder}
                onChange={(e) => setNewOrder(Number(e.target.value))}
                className="w-full h-9 px-3 rounded-xl border border-gray-200 text-[13px] focus:outline-none focus:border-[#1A2340]"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={creating || !newName.trim()}
                className="h-9 px-4 rounded-xl bg-[#1A2340] text-white text-[13px] font-semibold disabled:opacity-40 hover:bg-[#2a3a60] active:scale-95 transition-all"
              >
                {creating ? "Adding…" : "Add"}
              </button>
              <button
                onClick={() => { setAddingNew(false); setError(null); }}
                className="h-9 px-3 rounded-xl text-gray-500 hover:bg-gray-100 text-[13px]"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Task list */}
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

      {/* Group by category */}
      {activeCats.map((catId) => {
        const rows = grouped[catId];
        if (!rows?.length) return null;
        const cfg = catConfig(catId);

        return (
          <div key={catId} className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            {/* Section header */}
            <div
              className="px-4 py-2.5 flex items-center gap-2 border-b"
              style={{ backgroundColor: cfg.bg, borderColor: `${cfg.color}22` }}
            >
              <span className="text-[12px] font-bold tracking-wide" style={{ color: cfg.color }}>
                {cfg.label.toUpperCase()}
              </span>
              <span className="text-[11px] font-medium" style={{ color: cfg.color, opacity: 0.7 }}>
                {rows.length} task{rows.length !== 1 ? "s" : ""}
              </span>
            </div>

            {/* Rows */}
            <div className="divide-y divide-gray-50">
              {rows.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  isEditing={editingId === task.id}
                  isSaving={savingId === task.id}
                  isDeleting={deletingId === task.id}
                  editName={editName}
                  editCategory={editCategory}
                  editCode={editCode}
                  editOrder={editOrder}
                  onEditName={setEditName}
                  onEditCategory={setEditCategory}
                  onEditCode={setEditCode}
                  onEditOrder={setEditOrder}
                  onStartEdit={() => startEdit(task)}
                  onCancelEdit={cancelEdit}
                  onSave={() => saveEdit(task)}
                  onDelete={() => handleDelete(task)}
                  onRestore={() => handleRestore(task)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Task row ──────────────────────────────────────────────────────────────────

interface TaskRowProps {
  task: ZoneTask;
  isEditing: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  editName: string;
  editCategory: TaskCategory;
  editCode: string;
  editOrder: number;
  onEditName: (v: string) => void;
  onEditCategory: (v: TaskCategory) => void;
  onEditCode: (v: string) => void;
  onEditOrder: (v: number) => void;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onSave: () => void;
  onDelete: () => void;
  onRestore: () => void;
}

function TaskRow({
  task, isEditing, isSaving, isDeleting,
  editName, editCategory, editCode, editOrder,
  onEditName, onEditCategory, onEditCode, onEditOrder,
  onStartEdit, onCancelEdit, onSave, onDelete, onRestore,
}: TaskRowProps) {
  const inactive = task.active === false;

  if (isEditing) {
    return (
      <div className="px-4 py-3 bg-blue-50/60 flex flex-wrap gap-2.5 items-center">
        <input
          autoFocus
          type="text"
          value={editName}
          onChange={(e) => onEditName(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") onSave(); if (e.key === "Escape") onCancelEdit(); }}
          className="flex-1 min-w-[150px] h-8 px-3 rounded-lg border border-blue-200 bg-white text-[13px] focus:outline-none focus:border-[#1A2340]"
        />
        <select
          value={editCategory}
          onChange={(e) => onEditCategory(e.target.value as TaskCategory)}
          className="w-28 h-8 px-2 rounded-lg border border-blue-200 bg-white text-[13px] focus:outline-none"
        >
          {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
        <input
          type="text"
          value={editCode}
          onChange={(e) => onEditCode(e.target.value)}
          placeholder="Code"
          className="w-20 h-8 px-2 rounded-lg border border-blue-200 bg-white text-[13px] focus:outline-none"
        />
        <input
          type="number"
          value={editOrder}
          onChange={(e) => onEditOrder(Number(e.target.value))}
          placeholder="Order"
          className="w-16 h-8 px-2 rounded-lg border border-blue-200 bg-white text-[13px] focus:outline-none"
        />
        <div className="flex gap-1.5">
          <button
            onClick={onSave}
            disabled={isSaving || !editName.trim()}
            className="h-8 px-3 rounded-lg bg-[#1A2340] text-white text-[12px] font-semibold flex items-center gap-1.5 disabled:opacity-40"
          >
            {isSaving ? "…" : <><CheckIcon /> Save</>}
          </button>
          <button
            onClick={onCancelEdit}
            className="h-8 px-3 rounded-lg text-gray-500 hover:bg-gray-100 text-[12px]"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "px-4 py-3 flex items-center gap-3 group transition-colors",
        inactive ? "opacity-40" : "hover:bg-gray-50/70",
      )}
    >
      {/* Order badge */}
      <span className="w-7 text-center text-[11px] font-mono text-gray-300 shrink-0">
        {task.display_order}
      </span>

      {/* Name */}
      <span className={cn("flex-1 text-[14px] font-medium", inactive && "line-through text-gray-400")}>
        {task.name}
      </span>

      {/* Code */}
      {task.code && (
        <span className="text-[11px] font-mono text-gray-400 shrink-0">{task.code}</span>
      )}

      {/* Category pill */}
      <CategoryPill cat={task.category ?? ""} />

      {/* Actions — shown on hover */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        {inactive ? (
          <button
            onClick={onRestore}
            disabled={isSaving}
            title="Restore"
            className="w-7 h-7 rounded-lg flex items-center justify-center text-emerald-500 hover:bg-emerald-50 disabled:opacity-50 transition-colors"
          >
            <RestoreIcon />
          </button>
        ) : (
          <>
            <button
              onClick={onStartEdit}
              title="Edit"
              className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 hover:text-[#1A2340] transition-colors"
            >
              <PencilIcon />
            </button>
            <button
              onClick={onDelete}
              disabled={isDeleting}
              title="Archive"
              className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:bg-red-50 hover:text-red-500 disabled:opacity-50 transition-colors"
            >
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
// Break Schedule Tab (stub — full build in next iteration)
// ══════════════════════════════════════════════════════════════════════════════

function BreaksTab() {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-8 text-center">
      <div className="w-12 h-12 rounded-2xl bg-[#C9A84C]/10 flex items-center justify-center mx-auto mb-4">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="#C9A84C" strokeWidth="1.8" />
          <path d="M12 7v5l3 3" stroke="#C9A84C" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </div>
      <div className="text-[15px] font-semibold text-gray-700 mb-1">Break Schedule Editor</div>
      <div className="text-[13px] text-gray-400">
        Configure group break times, wave windows, and duration rules.
        <br />Coming in the next build.
      </div>
    </div>
  );
}
