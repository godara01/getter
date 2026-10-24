import type { RunResult } from "./api";

export function runSummary(r: RunResult): string {
  if (r.tests.length > 0) {
    const passed = r.tests.filter((t) => t.passed).length;
    return `${passed} of ${r.tests.length} tests passed`;
  }
  return r.message || "No test result";
}

export function runsLeft(coding: { max_runs: number; runs_used: number }): number {
  return Math.max(0, coding.max_runs - coding.runs_used);
}
