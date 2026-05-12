import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Circular progress arc path for SVG rings */
export function ringPath(
  cx: number,
  cy: number,
  r: number,
  percent: number
): string {
  const angle = (percent / 100) * 360;
  const startRad = -Math.PI / 2;
  const endRad = startRad + (angle * Math.PI) / 180;
  const x1 = cx + r * Math.cos(startRad);
  const y1 = cy + r * Math.sin(startRad);
  const x2 = cx + r * Math.cos(endRad);
  const y2 = cy + r * Math.sin(endRad);
  const large = angle > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
}

/** Stroke-dasharray trick for progress circles */
export function strokeDash(percent: number, circumference: number) {
  const offset = circumference - (percent / 100) * circumference;
  return { strokeDasharray: circumference, strokeDashoffset: offset };
}

/** Zone group → accent color (break group dot / wave indicator) */
const GROUP_COLORS: Record<string, string> = {
  "1": "#3B82F6",  // blue
  "2": "#14B8A6",  // teal
  "3": "#F59E0B",  // amber
  "4": "#F43F5E",  // rose
  "5": "#8B5CF6",  // purple
  "6": "#10B981",  // emerald
  "7": "#F97316",  // orange
  "8": "#6366F1",  // indigo
};

export function groupColor(group: string | number): string {
  return GROUP_COLORS[String(group)] ?? "#64748B";
}

/**
 * Zone-family accent color — matches the print deployment book exactly.
 *
 * Color taxonomy (from render_deployment_book.py):
 *   yellow  #B89708  → Z1, Z2, RR-1
 *   red     #E53935  → Z3, Z4, Z5, Z9, Z9-SR
 *   pink    #B7679A  → Z6, RR-6
 *   blue    #1E88E5  → Z7, RR-7
 *   brown   #6B5346  → Z8, RR-8
 *   green   #43A047  → Z10, RR-10, Support 3
 *   orange  #FB8C00  → Trash 1-5, Trash 6-10
 *   purple  #8E24AA  → Admin
 *   grey    #4a5568  → Support 1, Support 2
 */
const ZONE_ACCENT: Record<string, string> = {
  // Zone slots (slot_key format from DB)
  zone_1:  "#B89708", zone_2:  "#B89708",
  zone_3:  "#E53935", zone_4:  "#E53935", zone_5: "#E53935",
  zone_6:  "#B7679A",
  zone_7:  "#1E88E5",
  zone_8:  "#6B5346",
  zone_9:  "#E53935",
  zone_10: "#43A047",
  // Restroom slots
  rr_1:    "#B89708",
  rr_6:    "#B7679A",
  rr_7:    "#1E88E5",
  rr_8:    "#6B5346",
  rr_10:   "#43A047",
  // Auxiliary
  z9_sr:      "#E53935",
  admin:      "#8E24AA",
  trash_1_5:  "#FB8C00",
  trash_6_10: "#FB8C00",
  support_1:  "#4a5568",
  support_2:  "#4a5568",
  support_3:  "#43A047",
};

export function zoneAccentColor(zoneId: string): string {
  return ZONE_ACCENT[zoneId] ?? "#94A3B8";
}

/** Restroom gender → subtle card background tint.
 *  Uses the print-system pink/blue at 5% opacity — just a whisper of color. */
export function rrSideTint(side: string | null): string {
  if (side === "womens") return "rgba(183, 103, 154, 0.07)"; // pink #B7679A @ 7%
  if (side === "mens")   return "rgba(30, 136, 229, 0.07)";  // blue #1E88E5 @ 7%
  return "transparent";
}
