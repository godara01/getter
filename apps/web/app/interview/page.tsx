"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import { ErrorNote } from "@/components/ErrorNote";
import { RichText } from "@/components/RichText";
import { useSessionId } from "@/components/useSessionId";
import { track } from "@/lib/analytics";
import { ApiError, type Session, api } from "@/lib/api";
import { formatClock } from "@/lib/text";

const MAX_CHARS = 4000;

// Loaded only when a coding question is on screen; other sections never fetch it.
const CodingPanel = dynamic(() => import("@/components/CodingPanel"), {
  ssr: false,
  loading: () => <p className="text-sm text-muted">Loading the editor…</p>,
});

function Interview() {
  const id = useSessionId();
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const lastStatus = useRef<string | null>(null);

  const show = useCallback((s: Session) => {
    // Count a completion only when this page saw the interview end.
    if (lastStatus.current === "in_progress" && s.status !== "in_progress") {
      track("interview_completed", { level: s.level });
    }
    lastStatus.current = s.status;
    setSession(s);
    setSecondsLeft(s.progress?.section_seconds_left ?? null);
  }, []);

  useEffect(() => {
    if (!id) return;
    api.session(id).then(show, (err) =>
      setError(err instanceof ApiError ? err.message : "Could not load the interview."),
    );
  }, [id, show]);

  // Section timer. The server enforces the limit; this only shows it.
  const timerRunning = secondsLeft !== null;
  useEffect(() => {
    if (!timerRunning) return;
    const t = setInterval(() => setSecondsLeft((s) => (s === null ? s : Math.max(0, s - 1))), 1000);
    return () => clearInterval(t);
  }, [timerRunning]);

  // Once the interview ends, wait for the report and open it.
  useEffect(() => {
    if (!id || session?.status !== "grading") return;
    let stopped = false;
    const poll = async () => {
      while (!stopped) {
        try {
          const report = await api.report(id);
          if (report) {
            router.push(`/report/?id=${id}`);
            return;
          }
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Could not load the report.");
          return;
        }
        await new Promise((r) => setTimeout(r, 2000));
      }
    };
    poll();
    return () => {
      stopped = true;
    };
  }, [id, session?.status, router]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.turns.length]);

  async function send() {
    if (!id || !draft.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      show(await api.answer(id, draft));
      setDraft("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Your answer was not sent. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function end() {
    if (!id || !confirm("End the interview now? You'll get feedback on what you've answered."))
      return;
    setBusy(true);
    try {
      show(await api.end(id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not end the interview.");
    } finally {
      setBusy(false);
    }
  }

  if (!id) return <ErrorNote message="No interview selected." />;
  if (!session) return error ? <ErrorNote message={error} /> : <p className="text-muted">Loading…</p>;

  const live = session.status === "in_progress";
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold">{session.title}</h1>
        {session.progress && (
          <p className="text-sm text-muted" data-testid="progress">
            Section {session.progress.section_number} of {session.progress.section_count}:{" "}
            {session.progress.section_title}
            {secondsLeft !== null && <> · {formatClock(secondsLeft)} left</>}
          </p>
        )}
      </div>

      <ol className="space-y-4" aria-label="Interview transcript">
        {session.turns.map((t) => (
          <li
            key={t.index}
            data-speaker={t.speaker}
            className={
              t.speaker === "candidate"
                ? "ml-auto max-w-[85%] rounded-lg bg-accent/10 p-4"
                : "max-w-[92%] rounded-lg border border-line bg-card p-4"
            }
          >
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">
              {t.kind === "code"
                ? "Your code"
                : t.kind === "run_result"
                  ? "Test run"
                  : t.speaker === "candidate"
                    ? "You"
                    : "Interviewer"}
            </p>
            {t.kind === "code" ? (
              <pre className="overflow-x-auto rounded-md border border-line bg-bg p-3 text-sm">
                <code>{t.text}</code>
              </pre>
            ) : t.kind === "run_result" ? (
              <pre className="overflow-x-auto whitespace-pre-wrap text-sm">{t.text}</pre>
            ) : (
              <RichText text={t.text} />
            )}
          </li>
        ))}
      </ol>
      <div ref={bottom} />

      <ErrorNote message={error} />

      {live ? (
        <div className="space-y-2">
          {session.coding && (
            <CodingPanel sessionId={session.id} coding={session.coding} onSession={show} />
          )}
          <label htmlFor="answer" className="sr-only">
            Your answer
          </label>
          <textarea
            id="answer"
            value={draft}
            maxLength={MAX_CHARS}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send();
            }}
            rows={6}
            placeholder="Type your answer. Ctrl+Enter to send."
            className="w-full rounded-md border border-line bg-card p-3"
            disabled={busy}
          />
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={end}
              disabled={busy}
              className="text-sm text-muted underline disabled:opacity-40"
            >
              End interview
            </button>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted">
                {draft.length}/{MAX_CHARS}
              </span>
              <button
                type="button"
                onClick={send}
                disabled={busy || !draft.trim()}
                className="rounded-md bg-accent px-5 py-2 font-medium text-accent-fg disabled:opacity-40"
              >
                {busy ? "Sending…" : "Send answer"}
              </button>
            </div>
          </div>
        </div>
      ) : session.status === "grading" ? (
        <p className="rounded-md border border-line bg-card p-4" role="status">
          Preparing your feedback report…
        </p>
      ) : session.status === "completed" ? (
        <Link href={`/report/?id=${session.id}`} className="font-medium text-accent underline">
          See your report
        </Link>
      ) : (
        <p className="text-muted">This interview has ended without a report ({session.status}).</p>
      )}
    </div>
  );
}

export default function InterviewPage() {
  return (
    <Suspense>
      <Interview />
    </Suspense>
  );
}
