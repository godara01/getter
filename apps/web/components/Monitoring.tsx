"use client";

import { useEffect, useState } from "react";

import { initSentry, monitoringEnabled, optedOut, setOptOut } from "@/lib/analytics";

/** Starts optional monitoring and shows the opt-out link. Renders nothing without keys. */
export function Monitoring() {
  const [off, setOff] = useState(true);
  useEffect(() => {
    setOff(optedOut());
    void initSentry().catch(() => undefined);
  }, []);
  if (!monitoringEnabled()) return null;
  return (
    <footer className="mx-auto max-w-4xl px-4 pb-8 text-xs text-muted">
      Anonymous usage and error stats help us fix problems. No answers or emails are included.{" "}
      <button
        type="button"
        className="underline"
        onClick={() => {
          setOptOut(!off);
          setOff(optedOut());
        }}
      >
        {off ? "Turn on" : "Opt out"}
      </button>
    </footer>
  );
}
