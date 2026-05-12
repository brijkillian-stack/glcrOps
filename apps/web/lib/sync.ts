/**
 * ZDS Forge — Shared sync layer (SWR-based)
 *
 * Architecture:
 *   • One SWR key per night: ["night-placements", nightId]
 *   • One SWR key per night for break waves: ["night-breaks", nightId]
 *   • Optimistic updates applied immediately; background refetch confirms
 *   • All mutations go through mutatePlacements / mutateBreaks — both share
 *     the same key so Daily Planner and Break Sheet always see the same data
 *   • A Realtime hook stub is exported for future Supabase channel wiring
 */

import { useRef, useState as useReactState } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { moveBreakTMApi, patchSlotLock, swapSlots as swapSlotsApi } from "@/lib/forge-api";

// ── Types ─────────────────────────────────────────────────────────────────────

export type GroupId = "1" | "2" | "3";

const UNDO_LIMIT = 10;

interface UndoEntry {
  prevData:  NightPlacements;
  apiRevert: () => Promise<void>;   // call to revert the action on the server
}

export interface TMAssignment {
  slot_id: string;    // unique placement slot
  zone_id: string;    // e.g. "Z1", "Z9", "RR-A"
  zone_label: string; // display label
  zone_type: "zone" | "restroom" | "auxiliary";
  tm_id: string | null;
  tm_name: string | null;
  tm_initials: string | null;
  group: GroupId | null;
  rr_side: string | null;  // "mens" | "womens" | null
  tasks: string[] | null;  // null = never customised → picker uses catalogue defaults; [] = explicitly cleared
  is_override: boolean;
  is_locked: boolean;      // locked slots are skipped by the fill engine
}

/**
 * Per-group slot within a break wave.
 * Each group goes on break at staggered times (see break schedule below).
 *
 * Break schedule — grave shift 11 PM → 7 AM:
 *   Group 1: Wave1 12:45a (15m) | Wave2 2:30a (30m) | Wave3 5:00a (15m)
 *   Group 2: Wave1  1:00a (15m) | Wave2 3:00a (30m) | Wave3 5:00a (15m)
 *   Group 3: Wave1  1:15a (15m) | Wave2 3:30a (30m) | Wave3 5:15a (15m)
 */
export interface BreakGroupSlot {
  group: GroupId;       // "1" | "2" | "3"
  start_time: string;   // "HH:MM" 24h — e.g. "00:45" = 12:45 AM
  end_time: string;
  duration_min: number; // 15 or 30
  tm_ids: string[];
  tm_names: string[];
}

export interface BreakWave {
  wave: GroupId;        // "1" = First Break | "2" = Main Break | "3" = Last Break
  label: string;        // "First Break" | "Main Break" | "Last Break"
  groups: BreakGroupSlot[];  // one per group, sorted by group number
}

export interface NightPlacements {
  night_id: string;
  date: string;
  day_name: string;
  fill_rate: number;
  last_synced: string;  // ISO timestamp
  placements: TMAssignment[];
  break_waves: BreakWave[];
}

// ── SWR key factories ─────────────────────────────────────────────────────────

export const placementsKey = (nightId: string) =>
  ["night-placements", nightId] as const;


// ── SWR fetcher ───────────────────────────────────────────────────────────────

async function fetchPlacements(nightId: string): Promise<NightPlacements> {
  const res = await fetch(`/api/forge/v1/nights/${nightId}/placements`, {
    cache: "no-store",  // always fetch fresh — SWR manages client-side deduping
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Forge API ${res.status} at /v1/nights/${nightId}/placements: ${body}`);
  }
  const data = await res.json();
  return { ...data, last_synced: new Date().toISOString() };
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

/** Primary hook — used by BOTH Daily Planner and Break Sheet */
export function useNightPlacements(nightId: string) {
  const undoStack = useRef<UndoEntry[]>([]);
  const [undoDepth, setUndoDepth] = useReactState(0); // tracks length for re-render

  const { data, error, isLoading, mutate } = useSWR(
    placementsKey(nightId),
    ([, id]) => fetchPlacements(id),
    {
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 3_000,
      // Polling fallback — replace with Supabase Realtime subscription later
      refreshInterval: 10_000,
    }
  );

  /** Push to undo stack (capped at UNDO_LIMIT). Triggers re-render via undoDepth. */
  function pushUndo(prevData: NightPlacements, apiRevert: () => Promise<void>) {
    undoStack.current = [{ prevData, apiRevert }, ...undoStack.current].slice(0, UNDO_LIMIT);
    setUndoDepth(undoStack.current.length);
  }

  /**
   * Optimistically assign a TM to a slot.
   * Immediately reflects in both Daily Planner and Break Sheet (same SWR key).
   * Records an undo entry so the action can be reverted.
   */
  async function assignTM(slotId: string, tm: { id: string; name: string; initials: string } | null) {
    if (!data) return;

    const prevData = data;
    const prevSlot = data.placements.find((p) => p.slot_id === slotId);
    const optimistic: NightPlacements = {
      ...data,
      last_synced: new Date().toISOString(),
      placements: data.placements.map((p) =>
        p.slot_id === slotId
          ? { ...p, tm_id: tm?.id ?? null, tm_name: tm?.name ?? null, tm_initials: tm?.initials ?? null }
          : p
      ),
    };

    // Push undo — reverts to old tm_id
    pushUndo(prevData, async () => {
      await fetch(`/api/forge/v1/nights/${nightId}/placements/${slotId}`, {
        method:  "PATCH",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ tm_id: prevSlot?.tm_id ?? null }),
      });
    });

    await mutate(
      async () => {
        const res = await fetch(
          `/api/forge/v1/nights/${nightId}/placements/${slotId}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tm_id: tm?.id ?? null }),
          }
        );
        if (!res.ok) {
          const body = await res.text().catch(() => "");
          throw new Error(`assignTM ${res.status}: ${body}`);
        }
        return { ...optimistic, last_synced: new Date().toISOString() };
      },
      { optimisticData: optimistic, rollbackOnError: true, revalidate: true }
    );
  }

  /**
   * Optimistically lock or unlock a slot.
   * Locked slots are skipped by the fill engine.
   */
  async function lockSlot(slotId: string, isLocked: boolean) {
    if (!data) return;

    const prevData  = data;
    const prevSlot  = data.placements.find((p) => p.slot_id === slotId);
    const optimistic: NightPlacements = {
      ...data,
      last_synced: new Date().toISOString(),
      placements: data.placements.map((p) =>
        p.slot_id === slotId ? { ...p, is_locked: isLocked } : p
      ),
    };

    // Push undo — reverts to old lock state
    pushUndo(prevData, async () => {
      await patchSlotLock(nightId, slotId, prevSlot?.is_locked ?? false);
    });

    await mutate(
      async () => {
        await patchSlotLock(nightId, slotId, isLocked);
        return { ...optimistic, last_synced: new Date().toISOString() };
      },
      { optimisticData: optimistic, rollbackOnError: true, revalidate: true }
    );
  }

  /**
   * Optimistically swap two slot TM assignments.
   * Swapping is self-inverse so the undo just calls swap again.
   */
  async function swapSlots(slotIdA: string, slotIdB: string) {
    if (!data) return;

    const prevData = data;
    const slotA    = data.placements.find((p) => p.slot_id === slotIdA);
    const slotB    = data.placements.find((p) => p.slot_id === slotIdB);
    if (!slotA || !slotB) return;

    const optimistic: NightPlacements = {
      ...data,
      last_synced: new Date().toISOString(),
      placements: data.placements.map((p) => {
        if (p.slot_id === slotIdA)
          return { ...p, tm_id: slotB.tm_id, tm_name: slotB.tm_name, tm_initials: slotB.tm_initials };
        if (p.slot_id === slotIdB)
          return { ...p, tm_id: slotA.tm_id, tm_name: slotA.tm_name, tm_initials: slotA.tm_initials };
        return p;
      }),
    };

    // Swap is its own inverse
    pushUndo(prevData, async () => {
      await swapSlotsApi(nightId, slotIdA, slotIdB);
    });

    await mutate(
      async () => {
        await swapSlotsApi(nightId, slotIdA, slotIdB);
        return { ...optimistic, last_synced: new Date().toISOString() };
      },
      { optimisticData: optimistic, rollbackOnError: true, revalidate: true }
    );
  }

  /**
   * Undo the most recent action (assign, lock, or swap).
   * Restores the previous snapshot optimistically and calls the revert API.
   */
  async function undo() {
    const entry = undoStack.current[0];
    if (!entry) return;
    undoStack.current = undoStack.current.slice(1);
    setUndoDepth(undoStack.current.length);

    await mutate(
      async () => {
        await entry.apiRevert();
        return { ...entry.prevData, last_synced: new Date().toISOString() };
      },
      { optimisticData: { ...entry.prevData, last_synced: new Date().toISOString() }, rollbackOnError: true, revalidate: true }
    );
  }

  /**
   * Optimistically move a TM between break waves.
   * Finds the TM's group in the source wave automatically, then moves them to
   * the same group in the target wave (preserving their group assignment).
   * Also reflects in Daily Planner (same key).
   */
  async function moveBreakTM(
    tmId: string,
    tmName: string,
    fromWave: GroupId,
    toWave: GroupId
  ) {
    if (!data || fromWave === toWave) return;

    // Locate which group this TM belongs to in the source wave
    const srcWave = data.break_waves.find((w) => w.wave === fromWave);
    const tmGroup = srcWave?.groups.find((g) => g.tm_ids.includes(tmId))?.group ?? null;

    const optimistic: NightPlacements = {
      ...data,
      last_synced: new Date().toISOString(),
      break_waves: data.break_waves.map((w) => {
        if (w.wave === fromWave) {
          return {
            ...w,
            groups: w.groups.map((g) =>
              g.group === tmGroup
                ? { ...g, tm_ids: g.tm_ids.filter((id) => id !== tmId), tm_names: g.tm_names.filter((n) => n !== tmName) }
                : g
            ),
          };
        }
        if (w.wave === toWave) {
          return {
            ...w,
            groups: w.groups.map((g) =>
              g.group === tmGroup
                ? { ...g, tm_ids: [...g.tm_ids, tmId], tm_names: [...g.tm_names, tmName] }
                : g
            ),
          };
        }
        return w;
      }),
    };

    await mutate(
      async () => {
        await moveBreakTMApi(nightId, tmId, Number(fromWave), Number(toWave));
        return { ...optimistic, last_synced: new Date().toISOString() };
      },
      { optimisticData: optimistic, rollbackOnError: true, revalidate: true }
    );
  }

  return {
    data,
    error,
    isLoading,
    lastSynced:  data?.last_synced ?? null,
    assignTM,
    lockSlot,
    swapSlots,
    moveBreakTM,
    undo,
    canUndo:  undoDepth > 0,
    refresh:  () => mutate(),
  };
}

/**
 * Realtime stub — wire a Supabase channel here when ready.
 *
 * Example wiring:
 *   const channel = supabase.channel(`night:${nightId}`)
 *     .on('postgres_changes', { event: '*', schema: 'public', table: 'slot_assignments',
 *         filter: `night_id=eq.${nightId}` },
 *       () => globalMutate(placementsKey(nightId)))
 *     .subscribe();
 */
export function useRealtimeSync(nightId: string) {
  // Uncomment and wire Supabase Realtime here:
  // useEffect(() => {
  //   const channel = supabase.channel(`night:${nightId}`)
  //     .on('postgres_changes', ..., () => globalMutate(placementsKey(nightId)))
  //     .subscribe();
  //   return () => supabase.removeChannel(channel);
  // }, [nightId]);
  void nightId;  // suppress unused warning until wired
  void globalMutate;
}

/** Format "Last synced" timestamp for the top bar */
export function formatLastSynced(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const now = new Date();
  const diffS = Math.floor((now.getTime() - d.getTime()) / 1000);
  if (diffS < 10) return "Just now";
  if (diffS < 60) return `${diffS}s ago`;
  const diffM = Math.floor(diffS / 60);
  if (diffM < 60) return `${diffM}m ago`;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
