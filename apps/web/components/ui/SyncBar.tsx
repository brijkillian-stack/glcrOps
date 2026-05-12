"use client";

import { useEffect, useState } from "react";
import { formatLastSynced } from "@/lib/sync";
import { cn } from "@/lib/utils";

interface SyncBarProps {
  lastSynced: string | null;
  onRefresh?: () => void;
  className?: string;
}

/** "Last synced X ago" indicator — shown in both Daily Planner and Break Sheet */
export function SyncBar({ lastSynced, onRefresh, className }: SyncBarProps) {
  const [label, setLabel] = useState(formatLastSynced(lastSynced));

  // Refresh label every 10 s so the "Xs ago" stays accurate
  useEffect(() => {
    setLabel(formatLastSynced(lastSynced));
    const t = setInterval(() => setLabel(formatLastSynced(lastSynced)), 10_000);
    return () => clearInterval(t);
  }, [lastSynced]);

  return (
    <div
      className={cn(
        "flex items-center gap-1.5 text-[11px] text-white/40 font-medium no-select",
        className
      )}
    >
      {/* Pulsing dot */}
      <span className="relative flex h-1.5 w-1.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-60" />
        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-400" />
      </span>
      <span>Synced {label}</span>
      {onRefresh && (
        <button
          onClick={onRefresh}
          className="ml-0.5 opacity-60 hover:opacity-100 transition-opacity"
          aria-label="Force refresh"
        >
          {/* SF Symbol: arrow.clockwise */}
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path
              d="M8.5 5a3.5 3.5 0 1 1-1.03-2.47L8.5 1.5V4H6l.97-.97A2.5 2.5 0 1 0 7.5 5"
              stroke="currentColor"
              strokeWidth="1"
              strokeLinecap="round"
            />
          </svg>
        </button>
      )}
    </div>
  );
}
