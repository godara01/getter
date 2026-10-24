import { afterEach, describe, expect, it, vi } from "vitest";

import type { RunResult } from "../lib/api";
import { runSummary, runsLeft } from "../lib/coding";

const base: RunResult = {
  status: "ok",
  message: "",
  tests: [],
  stdout: "",
  stderr: "",
  duration_ms: 5,
};

describe("runSummary", () => {
  it("counts passing tests", () => {
    const tests = [
      { name: "a", passed: true, detail: "" },
      { name: "b", passed: false, detail: "expected 1" },
    ];
    expect(runSummary({ ...base, tests })).toBe("1 of 2 tests passed");
  });

  it("falls back to the runner's message", () => {
    expect(runSummary({ ...base, status: "timeout", message: "Stopped after 5 seconds." })).toBe(
      "Stopped after 5 seconds.",
    );
  });
});

describe("runsLeft", () => {
  it("never goes below zero", () => {
    expect(runsLeft({ max_runs: 10, runs_used: 3 })).toBe(7);
    expect(runsLeft({ max_runs: 10, runs_used: 12 })).toBe(0);
  });
});

describe("loadMonaco", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  async function load(onAppend: (script: { onerror?: () => void }) => void, timeout?: number) {
    vi.stubGlobal("window", {});
    vi.stubGlobal("document", {
      createElement: () => ({}),
      head: { appendChild: onAppend },
    });
    const { loadMonaco } = await import("../lib/monaco");
    return loadMonaco(timeout);
  }

  it("resolves to null when the script fails, so the textarea is used", async () => {
    expect(await load((s) => s.onerror?.())).toBeNull();
  });

  it("resolves to null when loading hangs", async () => {
    expect(await load(() => {}, 20)).toBeNull();
  });
});
