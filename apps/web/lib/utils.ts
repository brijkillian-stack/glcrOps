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

/** Zone group → accent color */
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
