"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

export interface ContextAction {
  label: string;
  icon?: React.ReactNode;
  onClick: () => void;
  destructive?: boolean;
  disabled?: boolean;
}

interface ContextMenuProps {
  open: boolean;
  onClose: () => void;
  actions: ContextAction[];
  anchorPos?: { x: number; y: number };
  className?: string;
}

/**
 * Apple-style dark context menu — triggered by squeeze gesture simulation
 * or right-click / long-press.
 */
export function ContextMenu({
  open,
  onClose,
  actions,
  anchorPos,
  className,
}: ContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("pointerdown", handler, { capture: true });
    return () => document.removeEventListener("pointerdown", handler, { capture: true });
  }, [open, onClose]);

  // Keyboard dismiss
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const style = anchorPos
    ? {
        position: "fixed" as const,
        left: typeof window !== "undefined" ? Math.min(anchorPos.x, window.innerWidth - 220) : anchorPos.x,
        top: typeof window !== "undefined" ? Math.min(anchorPos.y, window.innerHeight - actions.length * 52 - 16) : anchorPos.y,
      }
    : {};

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Scrim */}
          <motion.div
            className="fixed inset-0 z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            onClick={onClose}
          />

          {/* Menu panel */}
          <motion.div
            ref={ref}
            className={cn(
              "z-50 w-52 rounded-2xl overflow-hidden shadow-context-menu",
              "glass-dark py-1",
              anchorPos ? "" : "fixed bottom-8 left-1/2 -translate-x-1/2",
              className
            )}
            style={style}
            initial={{ opacity: 0, scale: 0.88, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.88, y: 8 }}
            transition={{ type: "spring", stiffness: 400, damping: 28 }}
          >
            {actions.map((action, i) => (
              <button
                key={i}
                disabled={action.disabled}
                onClick={() => {
                  if (!action.disabled) {
                    action.onClick();
                    onClose();
                  }
                }}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-3 text-sm font-medium",
                  "transition-colors duration-75 no-select text-left",
                  action.destructive
                    ? "text-red-400 hover:bg-red-500/20 active:bg-red-500/30"
                    : "text-white/90 hover:bg-white/10 active:bg-white/20",
                  action.disabled && "opacity-40 cursor-not-allowed",
                  i > 0 && "border-t border-white/[0.06]"
                )}
              >
                {action.icon && (
                  <span className="w-5 h-5 flex items-center justify-center shrink-0 opacity-80">
                    {action.icon}
                  </span>
                )}
                {action.label}
              </button>
            ))}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
