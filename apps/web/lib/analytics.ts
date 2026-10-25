// Optional monitoring. Nothing runs, loads or is sent unless a key is set at
// build time, and never when the visitor has opted out (Do Not Track, Global
// Privacy Control, or the opt-out link in the footer).
//
// Events carry no answer text, emails or names; see EventMap below.

import type { Level, Verdict } from "./api";

export interface EventMap {
  practice_started: { template_id: string; level: Level };
  interview_completed: { level: Level };
  report_viewed: { verdict: Verdict };
  pack_purchased: { pack_id: string };
}

export type EventName = keyof EventMap;

const OPT_OUT_KEY = "getter-analytics-opt-out";
const ID_KEY = "getter-anon-id";
const DEFAULT_POSTHOG_HOST = "https://us.i.posthog.com";

const SENSITIVE_KEYS = /answer|text|transcript|quote|email|token|authorization|cookie|password|secret|summary|rationale/i;
const REDACTED = "[redacted]";
const STRING_PATTERNS = [
  /eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*/g,
  /bearer\s+[A-Za-z0-9._~+/=-]+/gi,
  /[\w.+-]+@[\w-]+\.[\w.-]+/g,
];

function storage(): Storage | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

export function optedOut(): boolean {
  if (typeof navigator !== "undefined") {
    const nav = navigator as Navigator & { globalPrivacyControl?: boolean; msDoNotTrack?: string };
    const win = typeof window === "undefined" ? undefined : (window as { doNotTrack?: string });
    if (
      nav.doNotTrack === "1" ||
      nav.doNotTrack === "yes" ||
      nav.msDoNotTrack === "1" ||
      win?.doNotTrack === "1" ||
      nav.globalPrivacyControl === true
    ) {
      return true;
    }
  }
  return storage()?.getItem(OPT_OUT_KEY) === "1";
}

export function setOptOut(value: boolean): void {
  try {
    if (value) storage()?.setItem(OPT_OUT_KEY, "1");
    else storage()?.removeItem(OPT_OUT_KEY);
  } catch {
    // Storage can be blocked; the choice then lasts only for this page view.
  }
}

// Read at call time. Next.js inlines these literal names at build time.
export const posthogKey = () => process.env.NEXT_PUBLIC_POSTHOG_KEY ?? "";
export const sentryDsn = () => process.env.NEXT_PUBLIC_SENTRY_DSN ?? "";
export const monitoringEnabled = () => Boolean(posthogKey() || sentryDsn());

function anonymousId(): string {
  const s = storage();
  let id = s?.getItem(ID_KEY) ?? "";
  if (!id) {
    id = crypto.randomUUID();
    try {
      s?.setItem(ID_KEY, id);
    } catch {
      // Fall back to an id for this page view only.
    }
  }
  return id;
}

/** Redact secrets and personal data from any value; used for Sentry events. */
export function scrub(value: unknown, key?: string): unknown {
  if (key !== undefined && SENSITIVE_KEYS.test(key)) return REDACTED;
  if (typeof value === "string") {
    return STRING_PATTERNS.reduce((s, p) => s.replace(p, REDACTED), value);
  }
  if (Array.isArray(value)) return value.map((v) => scrub(v));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, scrub(v, k)]));
  }
  return value;
}

export function scrubSentryEvent<T extends object>(event: T): T {
  const copy = { ...event } as Record<string, unknown>;
  delete copy.user;
  const request = copy.request;
  if (request && typeof request === "object") {
    const { data: _data, cookies: _cookies, query_string: _query, ...rest } = request as Record<string, unknown>;
    copy.request = rest;
  }
  return scrub(copy) as T;
}

type SentryModule = typeof import("@sentry/browser");

/** Starts Sentry in the browser when a DSN is set. The SDK is fetched only then. */
export async function initSentry(
  load: () => Promise<SentryModule> = () => import("@sentry/browser"),
): Promise<boolean> {
  const dsn = sentryDsn();
  if (!dsn || optedOut()) return false;
  const Sentry = await load();
  Sentry.init({
    dsn,
    // Collect no user info, cookies, headers, request bodies or query strings.
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      httpBodies: [],
      urlQueryParams: false,
    },
    // No performance tracing or session replay: both can capture page content.
    integrations: (defaults) => defaults.filter((i) => i.name !== "Breadcrumbs"),
    beforeSend: (event) => (optedOut() ? null : scrubSentryEvent(event)),
  });
  return true;
}

/** Send one product event to PostHog's capture API. No SDK, no cookies. */
export function track<E extends EventName>(
  name: E,
  properties: EventMap[E],
  fetchImpl: typeof fetch = fetch,
): void {
  const key = posthogKey();
  if (!key || optedOut()) return;
  const safe = Object.fromEntries(
    Object.entries(properties).filter(
      ([k, v]) =>
        !SENSITIVE_KEYS.test(k) &&
        (typeof v === "number" || typeof v === "boolean" || (typeof v === "string" && !v.includes("@"))),
    ),
  );
  const host = (process.env.NEXT_PUBLIC_POSTHOG_HOST || DEFAULT_POSTHOG_HOST).replace(/\/$/, "");
  void fetchImpl(`${host}/capture/`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      api_key: key,
      event: name,
      distinct_id: anonymousId(),
      properties: { ...safe, $process_person_profile: false },
    }),
    keepalive: true,
  }).catch(() => {
    // Analytics must never break the product.
  });
}
