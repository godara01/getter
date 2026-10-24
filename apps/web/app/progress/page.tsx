"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ErrorNote } from "@/components/ErrorNote";
import { SkillChart } from "@/components/SkillChart";
import { ApiError, type ProgressData, api, clerkEnabled, getEmail } from "@/lib/api";
import { gapLabel } from "@/lib/progress";

export default function ProgressPage() {
  const [data, setData] = useState<ProgressData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!clerkEnabled && !getEmail()) {
      setData({ roles: [] });
      return;
    }
    api.progress().then(setData, (err) =>
      setError(err instanceof ApiError ? err.message : "Could not load your progress."),
    );
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">My progress</h1>
        <p className="text-sm text-muted">
          Scores from your finished, graded practice interviews. Only you can see this.
        </p>
      </div>
      <ErrorNote message={error} />
      {data === null && !error && <p className="text-muted">Loading…</p>}
      {data?.roles.length === 0 && (
        <p className="text-muted" data-testid="progress-empty">
          Nothing to show yet. Finish a practice interview and your scores will appear here.{" "}
          <Link href="/practice/" className="text-accent underline">
            Start one
          </Link>
          .
        </p>
      )}
      {data?.roles.map((role) => (
        <section key={`${role.template_id}-${role.level}`} className="space-y-4">
          <h2 className="text-lg font-semibold">
            {role.title} ({role.level === "mid" ? "mid" : "junior"}){" "}
            <span className="text-sm font-normal text-muted">
              {role.sessions} {role.sessions === 1 ? "interview" : "interviews"}
            </span>
          </h2>
          <ul className="grid gap-4 sm:grid-cols-2">
            {role.skills.map((s) => (
              <SkillChart
                key={s.skill_id}
                name={s.name}
                points={s.points}
                delta={s.delta}
              />
            ))}
          </ul>
          {role.gaps.length > 0 && (
            <div>
              <h3 className="font-medium">Gaps that keep coming up</h3>
              <ul className="mt-2 divide-y divide-line rounded-lg border border-line bg-card">
                {role.gaps.map((g) => (
                  <li key={g.skill_id} className="p-3" data-testid="gap">
                    <p className="font-medium">{g.name}</p>
                    <p className="text-sm text-muted">
                      {g.title} · {gapLabel(g.sessions)}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
