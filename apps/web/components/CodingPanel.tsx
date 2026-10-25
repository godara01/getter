"use client";

import { useState } from "react";

import CodeEditor from "@/components/CodeEditor";
import { ApiError, type RunResult, type Session, api } from "@/lib/api";
import { runSummary, runsLeft } from "@/lib/coding";

type Coding = NonNullable<Session["coding"]>;

/** Editor, Run button and result panel for a coding question. */
export default function CodingPanel({
  sessionId,
  coding,
  onSession,
}: {
  sessionId: string;
  coding: Coding;
  onSession: (s: Session) => void;
}) {
  const [code, setCode] = useState(coding.starter_code);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const left = runsLeft(coding);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const out = await api.run(sessionId, code);
      setResult(out.result);
      onSession(out.session);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The run did not start. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Coding task" className="space-y-3">
      <CodeEditor value={code} onChange={setCode} disabled={busy} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted">
          {coding.runner_enabled
            ? `${left} of ${coding.max_runs} runs left. Each run is saved with your interview.`
            : "Running code is not set up on this server. Write your code and explain it in your answer."}
        </p>
        <button
          type="button"
          onClick={run}
          disabled={busy || !coding.runner_enabled || left === 0 || !code.trim()}
          className="rounded-md border border-line bg-card px-4 py-2 text-sm font-medium disabled:opacity-40"
        >
          {busy ? "Running…" : "Run"}
        </button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}
      {result && (
        <div data-testid="run-result" className="rounded-md border border-line bg-card p-3 text-sm">
          <p className="font-medium">{runSummary(result)}</p>
          {result.status !== "ok" && result.message && <p className="text-muted">{result.message}</p>}
          <ul className="mt-2 space-y-1">
            {result.tests.map((t) => (
              <li key={t.name}>
                <span aria-hidden>{t.passed ? "✓" : "✗"}</span>{" "}
                <span className="sr-only">{t.passed ? "Passed:" : "Failed:"}</span>
                {t.name}
                {t.detail && <span className="text-muted"> ({t.detail})</span>}
              </li>
            ))}
          </ul>
          {result.stdout && (
            <pre className="mt-2 overflow-x-auto rounded bg-bg p-2">{result.stdout}</pre>
          )}
          {result.stderr && result.status !== "ok" && (
            <pre className="mt-2 overflow-x-auto rounded bg-bg p-2 text-red-700 dark:text-red-300">
              {result.stderr}
            </pre>
          )}
        </div>
      )}
    </section>
  );
}
