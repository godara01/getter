import { afterEach, beforeEach, expect, it, vi } from "vitest";

const store = new Map<string, string>();

beforeEach(() => {
  store.clear();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

const load = () => import("../lib/analytics");
const ok = () => vi.fn<typeof fetch>(async () => new Response("{}"));

it("sends nothing and loads nothing without keys", async () => {
  const { track, initSentry, monitoringEnabled } = await load();
  const fetchImpl = ok();
  const loader = vi.fn();
  track("report_viewed", { verdict: "meets" }, fetchImpl);
  expect(await initSentry(loader)).toBe(false);
  expect(fetchImpl).not.toHaveBeenCalled();
  expect(loader).not.toHaveBeenCalled();
  expect(monitoringEnabled()).toBe(false);
});

it("sends only the declared, non-sensitive fields when PostHog is configured", async () => {
  vi.stubEnv("NEXT_PUBLIC_POSTHOG_KEY", "phc_test");
  const { track } = await load();
  const fetchImpl = ok();
  // Extra fields are a type error; the runtime guard still drops them if one slips through.
  const props = { template_id: "backend", level: "junior", text: "my answer", email: "a@b.co" };
  track("practice_started", props as never, fetchImpl);
  expect(fetchImpl).toHaveBeenCalledOnce();
  const body = JSON.parse(String(fetchImpl.mock.calls[0][1]?.body));
  expect(body.event).toBe("practice_started");
  expect(body.api_key).toBe("phc_test");
  expect(body.properties).toMatchObject({ template_id: "backend", level: "junior" });
  expect(JSON.stringify(body)).not.toMatch(/my answer|a@b\.co/);
});

it("respects Do Not Track, Global Privacy Control and the stored opt-out", async () => {
  vi.stubEnv("NEXT_PUBLIC_POSTHOG_KEY", "phc_test");
  vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", "https://k@example.invalid/1");
  const { track, initSentry, setOptOut } = await load();
  const fetchImpl = ok();
  const loader = vi.fn();

  vi.stubGlobal("navigator", { doNotTrack: "1" });
  track("report_viewed", { verdict: "meets" }, fetchImpl);
  expect(await initSentry(loader)).toBe(false);

  vi.stubGlobal("navigator", { globalPrivacyControl: true });
  track("report_viewed", { verdict: "meets" }, fetchImpl);

  vi.stubGlobal("navigator", {});
  setOptOut(true);
  track("report_viewed", { verdict: "meets" }, fetchImpl);
  expect(await initSentry(loader)).toBe(false);

  expect(fetchImpl).not.toHaveBeenCalled();
  expect(loader).not.toHaveBeenCalled();

  setOptOut(false);
  track("report_viewed", { verdict: "meets" }, fetchImpl);
  expect(fetchImpl).toHaveBeenCalledOnce();
});

it("starts Sentry with no PII and scrubs events when a DSN is set", async () => {
  vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", "https://k@example.invalid/1");
  const { initSentry } = await load();
  const init = vi.fn();
  expect(await initSentry(async () => ({ init }) as never)).toBe(true);
  const options = init.mock.calls[0][0];
  expect(options.dataCollection).toEqual({
    userInfo: false,
    cookies: false,
    httpHeaders: false,
    httpBodies: [],
    urlQueryParams: false,
  });
  expect(options.tracesSampleRate).toBeUndefined();

  const event = {
    message: "failed for a@b.co with Bearer abc.def.ghi",
    user: { email: "a@b.co" },
    request: { url: "http://x/interview/?id=1", data: { text: "my answer" }, cookies: { a: "b" } },
    extra: { transcript: ["my answer"], answer: "my answer", attempt: 2 },
  };
  const out = JSON.stringify(options.beforeSend(event));
  expect(out).not.toMatch(/my answer|a@b\.co|abc\.def\.ghi|cookies/);
  expect(out).toContain('"attempt":2');
  expect(out).toContain("http://x/interview/?id=1");
});
