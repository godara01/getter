"use client";

import { useEffect, useState } from "react";

import { ErrorNote } from "@/components/ErrorNote";
import { ApiError, api } from "@/lib/api";

const MAX_COMMENT = 500;

export function RatingWidget({ sessionId }: { sessionId: string }) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stopped = false;
    api
      .rating(sessionId)
      .then((r) => {
        if (stopped || !r) return;
        setRating(r.rating);
        setComment(r.comment ?? "");
        setSaved(true);
      })
      .catch(() => {
        // The widget is optional; a failed lookup just shows it empty.
      });
    return () => {
      stopped = true;
    };
  }, [sessionId]);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.rate(sessionId, rating, comment);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save your rating.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-3 rounded-lg border border-line bg-card p-4" data-testid="rating">
      <h2 className="text-lg font-semibold">Was this report useful?</h2>
      <div role="radiogroup" aria-label="Usefulness, 1 to 5" className="flex gap-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={rating === n}
            aria-label={`${n} out of 5`}
            onClick={() => {
              setRating(n);
              setSaved(false);
            }}
            className={`h-9 w-9 rounded-md border text-sm ${
              rating === n ? "border-accent bg-accent text-white" : "border-line"
            }`}
          >
            {n}
          </button>
        ))}
      </div>
      <p className="text-xs text-muted">1 is not useful, 5 is very useful.</p>
      <label className="block text-sm">
        <span className="sr-only">Comment (optional)</span>
        <textarea
          value={comment}
          maxLength={MAX_COMMENT}
          rows={2}
          placeholder="Anything we should improve? (optional)"
          onChange={(e) => {
            setComment(e.target.value);
            setSaved(false);
          }}
          className="w-full rounded-md border border-line bg-transparent p-2"
        />
      </label>
      <ErrorNote message={error} />
      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={rating === 0 || busy || saved}
          onClick={submit}
          className="rounded-md bg-accent px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {saved ? "Saved" : "Save rating"}
        </button>
        {saved && <span className="text-xs text-muted">Thanks. You can change this any time.</span>}
      </div>
    </section>
  );
}
