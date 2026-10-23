"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ErrorNote } from "@/components/ErrorNote";
import { ApiError, type SessionListItem, VERDICT_LABEL, api, getEmail } from "@/lib/api";

export default function SessionsPage() {
  const [items, setItems] = useState<SessionListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getEmail()) {
      setItems([]);
      return;
    }
    api.sessions().then(setItems, (err) =>
      setError(err instanceof ApiError ? err.message : "Could not load your interviews."),
    );
  }, []);

  async function remove(id: string) {
    if (!confirm("Delete this interview, its transcript and its report for good?")) return;
    try {
      await api.remove(id);
      setItems((list) => list?.filter((s) => s.id !== id) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete the interview.");
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">My interviews</h1>
      <ErrorNote message={error} />
      {items === null && !error && <p className="text-muted">Loading…</p>}
      {items?.length === 0 && (
        <p className="text-muted">
          No interviews yet.{" "}
          <Link href="/practice/" className="text-accent underline">
            Start one
          </Link>
          .
        </p>
      )}
      <ul className="divide-y divide-line rounded-lg border border-line bg-card">
        {items?.map((s) => (
          <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <Link
                href={s.status === "completed" ? `/report/?id=${s.id}` : `/interview/?id=${s.id}`}
                className="font-medium hover:underline"
              >
                {s.title} ({s.level === "mid" ? "mid" : "junior"})
              </Link>
              <p className="text-sm text-muted">
                {new Date(s.created_at).toLocaleString()} ·{" "}
                {s.verdict ? VERDICT_LABEL[s.verdict] : s.status.replace("_", " ")}
                {s.mean_score !== null && ` · ${s.mean_score.toFixed(1)}/4`}
              </p>
            </div>
            <button onClick={() => remove(s.id)} className="text-sm text-muted underline">
              Delete
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
