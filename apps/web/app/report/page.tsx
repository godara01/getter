"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";

import { ErrorNote } from "@/components/ErrorNote";
import { RatingWidget } from "@/components/RatingWidget";
import { useSessionId } from "@/components/useSessionId";
import { track } from "@/lib/analytics";
import { ApiError, type Report, VERDICT_LABEL, api } from "@/lib/api";

function ScoreBar({ score, target }: { score: number | null; target: number }) {
  return (
    <div className="flex items-center gap-1" aria-label={score ? `${score} out of 4` : "Not assessed"}>
      {[1, 2, 3, 4].map((n) => (
        <span
          key={n}
          className={`h-2 w-8 rounded-sm ${
            score !== null && n <= score ? "bg-accent" : "bg-line"
          } ${n === target ? "outline outline-1 outline-offset-1 outline-muted" : ""}`}
        />
      ))}
      <span className="ml-2 text-sm tabular-nums text-muted">{score ?? "–"}/4</span>
    </div>
  );
}

function ReportView() {
  const id = useSessionId();
  const [report, setReport] = useState<Report | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let stopped = false;
    const load = async () => {
      while (!stopped) {
        try {
          const r = await api.report(id);
          if (r) {
            setReport(r);
            track("report_viewed", { verdict: r.verdict });
            setPending(false);
            return;
          }
          setPending(true);
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Could not load the report.");
          return;
        }
        await new Promise((r) => setTimeout(r, 2000));
      }
    };
    load();
    return () => {
      stopped = true;
    };
  }, [id]);

  if (!id) return <ErrorNote message="No interview selected." />;
  if (error) return <ErrorNote message={error} />;
  if (!report)
    return <p className="text-muted">{pending ? "Preparing your report…" : "Loading…"}</p>;

  const levelName = report.level === "mid" ? "mid level" : "junior level";
  return (
    <article className="space-y-10">
      <header className="space-y-3">
        <p className="text-sm text-muted">
          {report.title} · target: {levelName}
        </p>
        <h1 className="text-3xl font-semibold" data-testid="verdict">
          {VERDICT_LABEL[report.verdict]}
        </h1>
        {report.mean_score !== null && (
          <p className="text-muted">
            Average {report.mean_score.toFixed(1)} out of 4, against a bar of {report.target_score}{" "}
            ({report.scale[String(report.target_score)]}).
          </p>
        )}
        <p className="max-w-2xl leading-relaxed">{report.summary}</p>
        {report.needs_review && (
          <p className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            Two independent graders disagreed on part of this report, so treat those scores with
            caution.
          </p>
        )}
      </header>

      {report.strengths.length > 0 && (
        <section>
          <h2 className="mb-2 text-lg font-semibold">What went well</h2>
          <ul className="list-disc space-y-1 pl-5">
            {report.strengths.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2 className="mb-3 text-lg font-semibold">Skills</h2>
        <ul className="space-y-4">
          {report.skills.map((s) => (
            <li key={s.skill_id} className="rounded-lg border border-line bg-card p-4" data-testid="skill">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-medium">{s.name}</h3>
                <ScoreBar score={s.score} target={report.target_score} />
              </div>
              {s.level_description && <p className="mt-2 text-sm">{s.level_description}</p>}
              <p className="mt-2 text-sm text-muted">{s.rationale}</p>
              {s.evidence.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {s.evidence.map((e, i) => (
                    <li key={i} className="border-l-2 border-line pl-3 text-sm italic">
                      “{e.quote}” <span className="not-italic text-muted">(answer {e.turn})</span>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </section>

      {report.learning_plan.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Your learning plan</h2>
          <ol className="space-y-4">
            {report.learning_plan.map((g) => (
              <li key={g.title} className="rounded-lg border border-line bg-card p-4">
                <h3 className="font-medium">{g.title}</h3>
                <p className="mt-1 text-sm">{g.detail}</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                  {g.practice.map((p) => (
                    <li key={p}>{p}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </section>
      )}

      <RatingWidget sessionId={id} />

      <footer className="space-y-1 border-t border-line pt-4 text-xs text-muted">
        <p>
          Private practice report: only you can see it. Graded by {report.graded_by}
          {report.checked_by ? `, checked by ${report.checked_by}` : ""} against rubric{" "}
          {report.rubric}.
        </p>
        <p>
          <Link href="/practice/" className="underline">
            Take another interview
          </Link>
        </p>
      </footer>
    </article>
  );
}

export default function ReportPage() {
  return (
    <Suspense>
      <ReportView />
    </Suspense>
  );
}
