"use client";

import { useEffect, useRef, useState } from "react";

import { ApiError, type Session, api } from "@/lib/api";
import { commandsLeft, promptLabel, recall, scrollback } from "@/lib/terminal";

type Terminal = NonNullable<Session["terminal"]>;

/** A practice terminal. Nothing runs for real; the server answers from a scripted scenario. */
export default function TerminalPanel({
  sessionId,
  terminal,
  turns,
  onSession,
}: {
  sessionId: string;
  terminal: Terminal;
  turns: Session["turns"];
  onSession: (s: Session) => void;
}) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [position, setPosition] = useState(0);
  const end = useRef<HTMLDivElement>(null);
  const exchanges = scrollback(turns, terminal);
  const history = exchanges.map((e) => e.command);
  const left = commandsLeft(terminal);
  const prompt = promptLabel(terminal);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [exchanges.length]);

  async function submit() {
    const command = draft.trim();
    if (!command || busy || left === 0) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api.command(sessionId, command);
      onSession(out.session);
      setDraft("");
      setPosition(0);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The command was not sent. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      submit();
    } else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      const r = recall(history, position, e.key === "ArrowUp" ? "up" : "down");
      setPosition(r.position);
      setDraft(r.text);
    }
  }

  return (
    <section aria-label="Practice terminal" className="space-y-2">
      <div
        data-testid="terminal"
        className="max-h-72 overflow-y-auto rounded-md border border-line bg-black p-3 font-mono text-sm text-green-200"
      >
        <p className="text-green-400/80">
          {terminal.welcome || "Practice terminal. Nothing runs for real."}
        </p>
        {exchanges.map((e, i) => (
          <div key={i} className="mt-2">
            <p>
              <span className="text-green-400">{prompt}</span> {e.command}
            </p>
            <pre className="whitespace-pre-wrap break-words">{e.output}</pre>
          </div>
        ))}
        <div ref={end} />
      </div>
      <div className="flex items-center gap-2 rounded-md border border-line bg-black px-3 py-2 font-mono text-sm text-green-200">
        <label htmlFor="terminal-command" className="shrink-0 text-green-400">
          {prompt}
        </label>
        <input
          id="terminal-command"
          value={draft}
          maxLength={200}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={busy || left === 0}
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          aria-describedby="terminal-help"
          className="min-w-0 flex-1 bg-transparent outline-none"
        />
      </div>
      <p id="terminal-help" className="text-xs text-muted">
        {left === 0
          ? "You have used all your commands. Explain what you found in your answer."
          : `${left} of ${terminal.max_commands} commands left. Press Enter to run, Up for the last command. Nothing runs for real; type "help" for how it works.`}
      </p>
      {error && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}
    </section>
  );
}
