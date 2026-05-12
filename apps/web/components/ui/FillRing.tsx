"use client";

import { strokeDash } from "@/lib/utils";
import { fillRateColor } from "@/lib/forge-api";

interface FillRingProps {
  rate: number;         // 0–1
  size?: number;        // px diameter
  strokeWidth?: number;
  showLabel?: boolean;
  className?: string;
}

export function FillRing({
  rate,
  size = 48,
  strokeWidth = 4,
  showLabel = true,
  className,
}: FillRingProps) {
  const r = (size - strokeWidth) / 2;
  const cx = size / 2;
  const circumference = 2 * Math.PI * r;
  const pct = Math.round(rate * 100);
  const { strokeDasharray, strokeDashoffset } = strokeDash(pct, circumference);
  const color = fillRateColor(rate);
  const fs = size < 40 ? 9 : size < 56 ? 11 : 13;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={className}
      aria-label={`${pct}% fill rate`}
    >
      {/* Track */}
      <circle
        cx={cx}
        cy={cx}
        r={r}
        fill="none"
        stroke="#E5E7EB"
        strokeWidth={strokeWidth}
      />
      {/* Progress */}
      <circle
        cx={cx}
        cy={cx}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={strokeDasharray}
        strokeDashoffset={strokeDashoffset}
        transform={`rotate(-90 ${cx} ${cx})`}
        style={{ transition: "stroke-dashoffset 0.6s cubic-bezier(0.16, 1, 0.3, 1)" }}
      />
      {showLabel && (
        <text
          x={cx}
          y={cx}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={fs}
          fontWeight="700"
          fontFamily="-apple-system, sans-serif"
          fill={color}
        >
          {pct}%
        </text>
      )}
    </svg>
  );
}
