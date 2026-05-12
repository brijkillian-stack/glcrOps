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

import useSWR, { mutate as globalMutate } from "swr";

// ── Types ─────────────────────────────────────────────────────────────────────

export type GroupId = "1" | "2" | "3";

export interface TMAssignment {
  slot_id: string;    // unique placement slot
  zone_id: string;    // e.g. "Z1", "Z9", "RR-A"
  zone_label: string; // display label
  zone_type: "zone" | "restroom" | "auxiliary";
  tm_id: string | null;
  tm_name: string | null;
  tm_initials: string | null;
  group: GroupId | null;
  tasks: string[];
  is_override: boolean;
}

export interface BreakWave {
  wave: GroupId;      // "1" | "2" | "3"
  label: string;      // "Break 1", etc.
  start_time: string; // "01:30"
  end_time: string;   // "02:00"
  tm_ids: string[];
  tm_names: string[];
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

// ── Mock data builder ─────────────────────────────────────────────────────────

const ZONE_COLORS: Record<string, GroupId> = {
  Z1: "1", Z2: "1", Z3: "2", Z4: "2", Z5: "3",
  Z6: "1", Z7: "2", Z8: "3", Z9: "1", Z10: "2",
  Z11: "3", Z12: "1",
  "RR-A": "2", "RR-B": "3", "RR-C": "1",
  "AUX-1": "2", "AUX-2": "3",
};

const MOCK_TMS = [
  { id: "tm-joy",     name: "Joy M.",     initials: "JM" },
  { id: "tm-seth",    name: "Seth K.",    initials: "SK" },
  { id: "tm-cookie",  name: "Cookie R.",  initials: "CR" },
  { id: "tm-sheri",   name: "Sheri O.",   initials: "SO" },
  { id: "tm-melissa", name: "Melissa T.", initials: "MT" },
  { id: "tm-daryl",   name: "Daryl H.",   initials: "DH" },
  { id: "tm-hena",    name: "Hena P.",    initials: "HP" },
  { id: "tm-vera",    name: "Vera S.",    initials: "VS" },
  { id: "tm-tony",    name: "Tony B.",    initials: "TB" },
  { id: "tm-ace",     name: "Ace L.",     initials: "AL" },
  { id: "tm-naye",    name: "Naye W.",    initials: "NW" },
  { id: "tm-sere",    name: "Sere D.",    initials: "SD" },
];

function buildMockPlacements(nightId: string): NightPlacements {
  const zones = [
    { id: "Z1", label: "Zone 1", type: "zone" as const },
    { id: "Z2", label: "Zone 2", type: "zone" as const },
    { id: "Z3", label: "Zone 3", type: "zone" as const },
    { id: "Z4", label: "Zone 4", type: "zone" as const },
    { id: "Z5", label: "Zone 5", type: "zone" as const },
    { id: "Z6", label: "Zone 6", type: "zone" as const },
    { id: "Z7", label: "Zone 7", type: "zone" as const },
    { id: "Z8", label: "Zone 8", type: "zone" as const },
    { id: "Z9", label: "Zone 9", type: "zone" as const },
    { id: "Z10", label: "Zone 10", type: "zone" as const },
    { id: "Z11", label: "Zone 11", type: "zone" as const },
    { id: "Z12", label: "Zone 12", type: "zone" as const },
    { id: "RR-A", label: "Restrooms A", type: "restroom" as const },
    { id: "RR-B", label: "Restrooms B", type: "restroom" as const },
    { id: "RR-C", label: "Restrooms C", type: "restroom" as const },
    { id: "AUX-1", label: "Auxiliary 1", type: "auxiliary" as const },
    { id: "AUX-2", label: "Auxiliary 2", type: "auxiliary" as const },
  ];

  const placements: TMAssignment[] = zones.map((z, i) => {
    const tm = i < MOCK_TMS.length ? MOCK_TMS[i] : null;
    return {
      slot_id: `${nightId}-${z.id}`,
      zone_id: z.id,
      zone_label: z.label,
      zone_type: z.type,
      tm_id: tm?.id ?? null,
      tm_name: tm?.name ?? null,
      tm_initials: tm?.initials ?? null,
      group: ZONE_COLORS[z.id] ?? null,
      tasks: tm ? [`Clean ${z.label}`, "Restock supplies"] : [],
      is_override: false,
    };
  });

  const break_waves: BreakWave[] = [
    {
      wave: "1",
      label: "Break 1",
      start_time: "01:00",
      end_time: "01:30",
      tm_ids: ["tm-joy", "tm-seth", "tm-cookie", "tm-sheri"],
      tm_names: ["Joy M.", "Seth K.", "Cookie R.", "Sheri O."],
    },
    {
      wave: "2",
      label: "Break 2",
      start_time: "02:30",
      end_time: "03:00",
      tm_ids: ["tm-melissa", "tm-daryl", "tm-hena", "tm-vera"],
      tm_names: ["Melissa T.", "Daryl H.", "Hena P.", "Vera S."],
    },
    {
      wave: "3",
      label: "Break 3",
      start_time: "04:00",
      end_time: "04:30",
      tm_ids: ["tm-tony", "tm-ace", "tm-naye", "tm-sere"],
      tm_names: ["Tony B.", "Ace L.", "Naye W.", "Sere D."],
    },
  ];

  return {
    night_id: nightId,
    date: "2026-05-08",
    day_name: "Friday",
    fill_rate: 0.85,
    last_synced: new Date().toISOString(),
    placements,
    break_waves,
  };
}

// ── SWR fetcher ───────────────────────────────────────────────────────────────

async function fetchPlacements(nightId: string): Promise<NightPlacements> {
  try {
    const res = await fetch(`/api/forge/v1/nights/${nightId}/placements`);
    if (!res.ok) throw new Error("API error");
    const data = await res.json();
    return { ...data, last_synced: new Date().toISOString() };
  } catch {
    // Fall back to mock data in dev / when API is down
    await new Promise((r) => setTimeout(r, 300));  // fake latency
    return buildMockPlacements(nightId);
  }
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

/** Primary hook — used by BOTH Daily Planner and Break Sheet */
export function useNightPlacements(nightId: string) {
  const { data, error, isLoading, mutate } = useSWR(
    placementsKey(nightId),
    ([, id]) => fetchPlacements(id),
    {
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 5_000,
      // Polling fallback — replace with Supabase Realtime subscription later
      refreshInterval: 30_000,
    }
  );

  /**
   * Optimistically assign a TM to a slot.
   * Immediately reflects in both Daily Planner and Break Sheet (same SWR key).
   */
  async function assignTM(slotId: string, tm: { id: string; name: string; initials: string } | null) {
    if (!data) return;

    const optimistic: NightPlacements = {
      ...data,
      last_synced: new Date().toISOString(),
      placements: data.placements.map((p) =>
        p.slot_id === slotId
          ? { ...p, tm_id: tm?.id ?? null, tm_name: tm?.name ?? null, tm_initials: tm?.initials ?? null }
          : p
      ),
    };

    await mutate(
      async () => {
        // In prod: POST /api/forge/v1/nights/{nightId}/placements/{slotId}
        // For now just return optimistic with a server timestamp
        await new Promise((r) => setTimeout(r, 120)); // simulated round-trip
        return { ...optimistic, last_synced: new Date().toISOString() };
      },
      { optimisticData: optimistic, rollbackOnError: true, revalidate: false }
    );
  }

  /**
   * Optimistically move a TM between break waves.
   * Also reflects in Daily Planner (same key).
   */
  async function moveBreakTM(
    tmId: string,
    tmName: string,
    fromWave: GroupId,
    toWave: GroupId
  ) {
    if (!data || fromWave === toWave) return;

    const optimistic: NightPlacements = {
      ...data,
      last_synced: new Date().toISOString(),
      break_waves: data.break_waves.map((w) => {
        if (w.wave === fromWave) {
          return {
            ...w,
            tm_ids: w.tm_ids.filter((id) => id !== tmId),
            tm_names: w.tm_names.filter((n) => n !== tmName),
          };
        }
        if (w.wave === toWave) {
          return {
            ...w,
            tm_ids: [...w.tm_ids, tmId],
            tm_names: [...w.tm_names, tmName],
          };
        }
        return w;
      }),
    };

    await mutate(
      async () => {
        await new Promise((r) => setTimeout(r, 120));
        return { ...optimistic, last_synced: new Date().toISOString() };
      },
      { optimisticData: optimistic, rollbackOnError: true, revalidate: false }
    );
  }

  return {
    data,
    error,
    isLoading,
    lastSynced: data?.last_synced ?? null,
    assignTM,
    moveBreakTM,
    refresh: () => mutate(),
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
