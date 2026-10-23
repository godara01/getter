"use client";

import { useSearchParams } from "next/navigation";

// Static export has no dynamic routes, so pages take ?id=<session id>.
export function useSessionId(): string | null {
  return useSearchParams().get("id");
}
