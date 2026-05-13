"use client";

/**
 * QuickLaunch — global floating action button (lower-right corner).
 *
 * Renders on every page via RootLayout.
 * Expands on click to show nav items:
 *   • ZDS Launchpad  → /
 *   • Control Panel  → /control-panel
 */

import { useState, useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";

// ── Icons ─────────────────────────────────────────────────────────────────────

function GridIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <rect x="2"  y="2"  width="7" height="7" rx="1.5" fill="currentColor" opacity="0.9"/>
      <rect x="11" y="2"  width="7" height="7" rx="1.5" fill="currentColor" opacity="0.9"/>
      <rect x="2"  y="11" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.9"/>
      <rect x="11" y="11" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.9"/>
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <path d="M4 4l10 10M14 4L4 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  );
}

function LaunchpadIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="1" width="5.5" height="5.5" rx="1.2" fill="currentColor" opacity="0.8"/>
      <rect x="9.5" y="1" width="5.5" height="5.5" rx="1.2" fill="currentColor" opacity="0.8"/>
      <rect x="1" y="9.5" width="5.5" height="5.5" rx="1.2" fill="currentColor" opacity="0.8"/>
      <rect x="9.5" y="9.5" width="5.5" height="5.5" rx="1.2" fill="currentColor" opacity="0.8"/>
    </svg>
  );
}

function ControlPanelIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="4"  cy="5"  r="1.5" fill="currentColor"/>
      <circle cx="4"  cy="11" r="1.5" fill="currentColor"/>
      <circle cx="12" cy="8"  r="1.5" fill="currentColor"/>
      <path d="M6 5h7M6 11h7M1 8h8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

// ── Menu items ────────────────────────────────────────────────────────────────

const ITEMS = [
  {
    key:   "control-panel",
    label: "Control Panel",
    sub:   "Tasks, breaks & config",
    href:  "/control-panel",
    icon:  <ControlPanelIcon />,
    color: "#C9A84C",   // GLCR gold
  },
  {
    key:   "launchpad",
    label: "ZDS Launchpad",
    sub:   "Week overview",
    href:  "/",
    icon:  <LaunchpadIcon />,
    color: "#007AFF",   // blue
  },
] as const;

// ── Component ─────────────────────────────────────────────────────────────────

export function QuickLaunch() {
  const [open, setOpen] = useState(false);
  const router          = useRouter();
  const pathname        = usePathname();
  const wrapRef         = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  // Close on route change
  useEffect(() => { setOpen(false); }, [pathname]);

  function navigate(href: string) {
    setOpen(false);
    router.push(href);
  }

  return (
    <div
      ref={wrapRef}
      className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2.5"
      style={{ isolation: "isolate" }}
    >
      {/* Menu items — slide up when open */}
      <div
        className="flex flex-col items-end gap-2 transition-all duration-200"
        style={{
          opacity:         open ? 1 : 0,
          transform:       open ? "translateY(0)" : "translateY(8px)",
          pointerEvents:   open ? "auto" : "none",
        }}
        aria-hidden={!open}
      >
        {ITEMS.map((item, i) => (
          <button
            key={item.key}
            onClick={() => navigate(item.href)}
            className="flex items-center gap-3 pl-3 pr-4 py-2.5 rounded-2xl
                       shadow-lg cursor-pointer no-select
                       transition-transform duration-150 active:scale-95"
            style={{
              background:      "rgba(26,35,64,0.96)",
              backdropFilter:  "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
              border:          "1px solid rgba(255,255,255,0.10)",
              transitionDelay: open ? `${i * 40}ms` : "0ms",
            }}
          >
            {/* Color dot */}
            <div
              className="w-7 h-7 rounded-xl flex items-center justify-center shrink-0"
              style={{ backgroundColor: `${item.color}22`, color: item.color }}
            >
              {item.icon}
            </div>
            <div className="text-left">
              <div className="text-[13px] font-semibold text-white leading-tight">
                {item.label}
              </div>
              <div className="text-[10px] text-white/45 leading-tight mt-0.5">
                {item.sub}
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* FAB trigger */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-14 h-14 rounded-2xl flex items-center justify-center
                   shadow-xl cursor-pointer no-select
                   transition-all duration-200 active:scale-95"
        style={{
          background:     open
            ? "rgba(26,35,64,0.98)"
            : "linear-gradient(135deg, #1A2340 0%, #2a3a60 100%)",
          border:         "1px solid rgba(255,255,255,0.12)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          color:          open ? "rgba(255,255,255,0.7)" : "#C9A84C",
          transform:      open ? "rotate(0deg)" : "rotate(0deg)",
          boxShadow:      open
            ? "0 8px 32px rgba(0,0,0,0.3)"
            : "0 8px 32px rgba(201,168,76,0.25), 0 2px 8px rgba(0,0,0,0.2)",
        }}
        aria-label={open ? "Close quick launch" : "Quick launch"}
      >
        <div
          style={{
            transition: "transform 0.2s ease, opacity 0.15s ease",
            transform:  open ? "rotate(45deg) scale(0.9)" : "rotate(0deg) scale(1)",
          }}
        >
          {open ? <CloseIcon /> : <GridIcon />}
        </div>
      </button>
    </div>
  );
}
