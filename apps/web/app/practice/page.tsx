"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ErrorNote } from "@/components/ErrorNote";
import { ApiError, type Level, type TemplateSummary, api, getEmail, setEmail } from "@/lib/api";

export default function PracticePage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<TemplateSummary[] | null>(null);
  const [templateId, setTemplateId] = useState<string>("");
  const [level, setLevel] = useState<Level>("junior");
  const [email, setEmailField] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEmailField(getEmail() ?? "");
    api
      .templates()
      .then((t) => {
        setTemplates(t);
        setTemplateId((current) => current || t[0]?.id || "");
      })
      .catch(() => setError("Could not reach the Getter API. Is it running?"));
  }, []);

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      setEmail(email);
      await api.acceptTerms();
      const session = await api.start(templateId, level);
      router.push(`/interview/?id=${session.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={start} className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Start a practice interview</h1>
        <p className="mt-1 text-muted">
          A text interview of about 35 minutes. Answer as you would in a real interview.
        </p>
      </div>

      <fieldset className="space-y-3">
        <legend className="mb-2 font-medium">Role</legend>
        {templates === null && !error && <p className="text-muted">Loading roles…</p>}
        <div className="grid gap-3 sm:grid-cols-2">
          {templates?.map((t) => (
            <label
              key={t.id}
              className={`cursor-pointer rounded-lg border bg-card p-4 ${
                templateId === t.id ? "border-accent ring-1 ring-accent" : "border-line"
              }`}
            >
              <input
                type="radio"
                name="template"
                value={t.id}
                checked={templateId === t.id}
                onChange={() => setTemplateId(t.id)}
                className="sr-only"
              />
              <span className="font-medium">{t.role_title}</span>
              <span className="mt-1 block text-sm text-muted">
                {t.sections.map((s) => s.title).join(" · ")}
              </span>
              <span className="mt-2 block text-xs text-muted">About {t.minutes} minutes</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-2 font-medium">Level you are aiming for</legend>
        <div className="flex gap-3">
          {(["junior", "mid"] as const).map((l) => (
            <label
              key={l}
              className={`cursor-pointer rounded-md border px-4 py-2 capitalize ${
                level === l ? "border-accent ring-1 ring-accent" : "border-line"
              }`}
            >
              <input
                type="radio"
                name="level"
                value={l}
                checked={level === l}
                onChange={() => setLevel(l)}
                className="sr-only"
              />
              {l === "mid" ? "Mid level" : "Junior"}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="space-y-2">
        <label htmlFor="email" className="block font-medium">
          Your email
        </label>
        <input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmailField(e.target.value)}
          className="w-full max-w-sm rounded-md border border-line bg-card px-3 py-2"
          placeholder="you@example.com"
        />
        <p className="text-xs text-muted">
          Development sign-in: your email identifies your interviews on this test server.
        </p>
      </div>

      <label className="flex max-w-2xl items-start gap-3 text-sm">
        <input
          type="checkbox"
          checked={agreed}
          onChange={(e) => setAgreed(e.target.checked)}
          className="mt-1"
        />
        <span>
          I accept the practice terms (draft, pending legal review). Getter stores my answers and the AI feedback on them so I can see my
          report. Practice interviews are private to me, are never shown to companies, and I can
          delete them at any time. <a href="/terms/" target="_blank" rel="noreferrer" className="underline">Read draft terms</a>.
        </span>
      </label>

      <ErrorNote message={error} />

      <button
        type="submit"
        disabled={!agreed || !templateId || busy}
        className="rounded-md bg-accent px-5 py-2.5 font-medium text-accent-fg disabled:opacity-40"
      >
        {busy ? "Starting…" : "Start interview"}
      </button>
    </form>
  );
}
