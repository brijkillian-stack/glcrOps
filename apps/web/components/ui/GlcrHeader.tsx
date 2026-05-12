"use client";

import { cn } from "@/lib/utils";

interface GlcrHeaderProps {
  title?: string;
  subtitle?: string;
  right?: React.ReactNode;
  className?: string;
  compact?: boolean;
}

/** Shared top bar with the GLCR Grave logotype */
export function GlcrHeader({
  title,
  subtitle,
  right,
  className,
  compact = false,
}: GlcrHeaderProps) {
  return (
    <header
      className={cn(
        "flex items-center justify-between bg-[#1A2340] text-white px-6 shrink-0",
        compact ? "h-14 py-0" : "py-4",
        className
      )}
    >
      {/* Left — logotype */}
      <div className="flex items-center gap-3">
        {/* Diamond logo mark */}
        <div className="relative w-8 h-8 shrink-0">
          <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
            <path
              d="M16 2L30 16L16 30L2 16L16 2Z"
              fill="#C9A84C"
              opacity="0.9"
            />
            <path
              d="M16 7L25 16L16 25L7 16L16 7Z"
              fill="#1A2340"
            />
            <path
              d="M16 11L21 16L16 21L11 16L16 11Z"
              fill="#C9A84C"
              opacity="0.7"
            />
          </svg>
        </div>

        <div>
          <div className="flex items-baseline gap-2">
            <span className="text-[15px] font-bold tracking-tight leading-none">
              GLCR
            </span>
            <span
              className="text-[11px] font-semibold tracking-[0.18em] uppercase leading-none"
              style={{ color: "#C9A84C" }}
            >
              GRAVE
            </span>
          </div>
          {title && (
            <div className="text-[11px] font-medium text-white/50 tracking-wide mt-0.5">
              {title}
            </div>
          )}
        </div>
      </div>

      {/* Right slot */}
      {right && <div className="flex items-center gap-2">{right}</div>}
    </header>
  );
}
