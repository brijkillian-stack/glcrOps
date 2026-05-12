"use client";

import { SWRConfig } from "swr";

export function SWRProvider({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        // Global error handler — swap for toast when UI lib is wired
        onError: (err) => {
          console.warn("[SWR]", err);
        },
        // Keep data visible while background refetch is in flight
        keepPreviousData: true,
      }}
    >
      {children}
    </SWRConfig>
  );
}
