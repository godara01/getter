// Loads the Monaco editor from a CDN, only when the coding section asks for it.
// Nothing here runs on other pages. Resolves to null if it fails to load, and
// the caller falls back to a plain textarea.

export const MONACO_BASE = "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min";

// The slice of Monaco's API we use.
export interface MonacoEditor {
  getValue(): string;
  onDidChangeModelContent(listener: () => void): void;
  updateOptions(options: { readOnly: boolean }): void;
  dispose(): void;
}
export interface Monaco {
  editor: {
    create(el: HTMLElement, options: Record<string, unknown>): MonacoEditor;
  };
}

type AmdRequire = {
  (deps: string[], ok: () => void, fail: () => void): void;
  config(options: { paths: Record<string, string> }): void;
};
type MonacoWindow = Window & {
  require?: AmdRequire;
  monaco?: Monaco;
  MonacoEnvironment?: { getWorkerUrl: () => string };
};

let loading: Promise<Monaco | null> | null = null;

export function loadMonaco(timeoutMs = 10_000): Promise<Monaco | null> {
  if (loading) return loading;
  const w = window as unknown as MonacoWindow;
  loading = new Promise<Monaco | null>((resolve) => {
    let done = false;
    const finish = (m: Monaco | null) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      if (!m) loading = null; // allow a retry on the next visit
      resolve(m);
    };
    const timer = setTimeout(() => finish(null), timeoutMs);
    // Monaco's workers must come from the same origin as the page, so wrap the CDN one.
    w.MonacoEnvironment = {
      getWorkerUrl: () =>
        "data:text/javascript;charset=utf-8," +
        encodeURIComponent(
          `self.MonacoEnvironment={baseUrl:'${MONACO_BASE}/'};` +
            `importScripts('${MONACO_BASE}/vs/base/worker/workerMain.js');`,
        ),
    };
    const script = document.createElement("script");
    script.src = `${MONACO_BASE}/vs/loader.js`;
    script.onerror = () => finish(null);
    script.onload = () => {
      const amd = w.require;
      if (!amd) return finish(null);
      amd.config({ paths: { vs: `${MONACO_BASE}/vs` } });
      amd(
        ["vs/editor/editor.main"],
        () => finish(w.monaco ?? null),
        () => finish(null),
      );
    };
    document.head.appendChild(script);
  });
  return loading;
}
