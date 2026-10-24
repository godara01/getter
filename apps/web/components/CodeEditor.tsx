"use client";

import { useEffect, useRef, useState } from "react";

import { type MonacoEditor, loadMonaco } from "@/lib/monaco";

/** Monaco, loaded on demand. If it cannot load we show a plain textarea instead. */
export default function CodeEditor({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (code: string) => void;
  disabled: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const editor = useRef<MonacoEditor | null>(null);
  const initial = useRef(value);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const [mode, setMode] = useState<"loading" | "monaco" | "textarea">("loading");

  useEffect(() => {
    let gone = false;
    loadMonaco().then((monaco) => {
      if (gone) return;
      if (!monaco || !host.current) return setMode("textarea");
      const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      try {
        editor.current = monaco.editor.create(host.current, {
          value: initial.current,
          language: "python",
          theme: dark ? "vs-dark" : "vs",
          automaticLayout: true,
          minimap: { enabled: false },
          fontSize: 14,
          scrollBeyondLastLine: false,
          ariaLabel: "Code editor",
        });
      } catch {
        return setMode("textarea");
      }
      editor.current.onDidChangeModelContent(() => onChangeRef.current(editor.current!.getValue()));
      setMode("monaco");
    });
    return () => {
      gone = true;
      editor.current?.dispose();
      editor.current = null;
    };
  }, []);

  useEffect(() => {
    editor.current?.updateOptions({ readOnly: disabled });
  }, [disabled, mode]);

  if (mode === "textarea") {
    return (
      <textarea
        aria-label="Code editor"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        spellCheck={false}
        rows={14}
        className="w-full rounded-md border border-line bg-card p-3 font-mono text-sm"
      />
    );
  }
  return (
    <div>
      {mode === "loading" && <p className="text-sm text-muted">Loading the editor…</p>}
      <div
        ref={host}
        data-testid="monaco"
        className={mode === "monaco" ? "h-72 overflow-hidden rounded-md border border-line" : "hidden"}
      />
    </div>
  );
}
