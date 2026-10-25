// Typed client for the Getter API. Types mirror services/api/src/getter_api/schemas.py.

export type Level = "junior" | "mid";

export interface TemplateSummary {
  id: string;
  title: string;
  role_title: string;
  levels: Level[];
  minutes: number;
  sections: { id: string; title: string; minutes: number }[];
  skills: string[];
}

export interface Turn {
  index: number;
  speaker: "interviewer" | "candidate";
  kind: "intro" | "question" | "follow_up" | "answer" | "closing" | "code" | "run_result" | "command" | "command_output";
  section_id: string | null;
  question_id: string | null;
  text: string;
  created_at: string;
}

export type SessionStatus = "in_progress" | "grading" | "completed" | "failed" | "abandoned";

export interface Session {
  id: string;
  template_id: string;
  title: string;
  level: Level;
  status: SessionStatus;
  created_at: string;
  ended_at: string | null;
  progress: {
    section_number: number;
    section_count: number;
    section_title: string;
    section_seconds_left: number | null;
  } | null;
  /** Set while the current question is a coding task. */
  coding: {
    language: string;
    starter_code: string;
    test_names: string[];
    runner_enabled: boolean;
    max_runs: number;
    runs_used: number;
  } | null;
  /** Set while the current question has a scripted terminal. */
  terminal: {
    question_id: string;
    hostname: string;
    user: string;
    welcome: string;
    max_commands: number;
    commands_used: number;
  } | null;
  turns: Turn[];
}

export interface RunResult {
  status: "ok" | "error" | "timeout" | "output_limit" | "not_configured" | "unavailable";
  message: string;
  tests: { name: string; passed: boolean; detail: string }[];
  stdout: string;
  stderr: string;
  duration_ms: number;
}

export interface SessionListItem {
  id: string;
  title: string;
  level: Level;
  status: SessionStatus;
  created_at: string;
  verdict: Verdict | null;
  mean_score: number | null;
}

export type Verdict = "below" | "meets" | "above" | "insufficient_evidence";

export interface Report {
  session_id: string;
  title: string;
  level: Level;
  target_score: number;
  scale: Record<string, string>;
  verdict: Verdict;
  mean_score: number | null;
  summary: string;
  strengths: string[];
  skills: {
    skill_id: string;
    name: string;
    score: number | null;
    level_description: string | null;
    evidence: { turn: number; quote: string }[];
    rationale: string;
  }[];
  learning_plan: { skill_id: string; title: string; detail: string; practice: string[] }[];
  needs_review: boolean;
  graded_by: string;
  checked_by: string | null;
  rubric: string;
  created_at: string;
}

export interface Rating {
  rating: number;
  comment: string | null;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
let tokenGetter: (() => Promise<string | null>) | null = null;

export function setTokenGetter(getter: (() => Promise<string | null>) | null): void {
  tokenGetter = getter;
}

const EMAIL_KEY = "getter.email";

export function apiBase(): string {
  return (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
}

export function getEmail(): string | null {
  try {
    return localStorage.getItem(EMAIL_KEY);
  } catch {
    return null;
  }
}

export function setEmail(email: string): void {
  try {
    localStorage.setItem(EMAIL_KEY, email.trim().toLowerCase());
  } catch {
    // Private mode: the email lives only for this page view.
  }
}

type Fetch = typeof fetch;

export async function request<T>(
  path: string,
  init: RequestInit = {},
  opts: { email?: string | null; fetchImpl?: Fetch } = {},
): Promise<{ status: number; data: T }> {
  const email = opts.email === undefined ? getEmail() : opts.email;
  const headers = new Headers(init.headers);
  if (init.body) headers.set("content-type", "application/json");
  headers.delete("x-dev-user-email");
  if (clerkEnabled) {
    const token = await tokenGetter?.();
    if (token) headers.set("authorization", `Bearer ${token}`);
  } else if (email) headers.set("x-dev-user-email", email);
  const res = await (opts.fetchImpl ?? fetch)(`${apiBase()}${path}`, { ...init, headers });
  if (res.status === 204) return { status: 204, data: undefined as T };
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join("; ")
          : `Request failed (${res.status})`;
    throw new ApiError(res.status, message);
  }
  return { status: res.status, data: body as T };
}

export interface Consent {
  id: string;
  kind: string;
  text_version: string;
  granted: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProgressData {
  roles: {
    template_id: string;
    title: string;
    level: Level;
    sessions: number;
    skills: {
      skill_id: string;
      name: string;
      points: { session_id: string; date: string; score: number }[];
      latest: number;
      previous: number | null;
      delta: number | null;
    }[];
    gaps: { skill_id: string; name: string; title: string; sessions: number }[];
  }[];
}

export const api = {
  progress: async () => (await request<ProgressData>("/progress")).data,
  waitlist: async (email: string, role_interest: string) =>
    (await request<{ message: string }>("/waitlist", {
      method: "POST", body: JSON.stringify({ email, role_interest }),
    })).data,
  consents: async () => (await request<Consent[]>("/consents")).data,
  withdrawConsent: async (id: string) => { await request(`/consents/${id}`, { method: "DELETE" }); },
  acceptTerms: async () => (await request<Consent>("/account/terms", {
    method: "POST", body: JSON.stringify({ accept_terms: true, text_version: "practice-terms-draft-v1" }),
  })).data,
  templates: async () => (await request<TemplateSummary[]>("/templates")).data,
  sessions: async () => (await request<SessionListItem[]>("/sessions")).data,
  session: async (id: string) => (await request<Session>(`/sessions/${id}`)).data,
  start: async (template_id: string, level: Level) =>
    (
      await request<Session>("/sessions", {
        method: "POST",
        body: JSON.stringify({ template_id, level, accept_terms: true }),
      })
    ).data,
  answer: async (id: string, text: string) =>
    (
      await request<Session>(`/sessions/${id}/answers`, {
        method: "POST",
        body: JSON.stringify({ text }),
      })
    ).data,
  run: async (id: string, code: string) =>
    (
      await request<{ result: RunResult; session: Session }>(`/sessions/${id}/runs`, {
        method: "POST",
        body: JSON.stringify({ code }),
      })
    ).data,
  command: async (id: string, command: string) =>
    (
      await request<{ output: string; session: Session }>(`/sessions/${id}/terminal`, {
        method: "POST",
        body: JSON.stringify({ command }),
      })
    ).data,
  end: async (id: string) =>
    (await request<Session>(`/sessions/${id}/end`, { method: "POST" })).data,
  /** Returns null while the report is still being prepared. */
  report: async (id: string) => {
    const { status, data } = await request<Report | { status: string }>(
      `/sessions/${id}/report`,
    );
    return status === 202 ? null : (data as Report);
  },
  /** The candidate's own rating of this report, or null if they have not rated it. */
  rating: async (id: string) =>
    (await request<Rating | null>(`/sessions/${id}/report/rating`)).data,
  rate: async (id: string, rating: number, comment: string) =>
    (
      await request<Rating>(`/sessions/${id}/report/rating`, {
        method: "PUT",
        body: JSON.stringify({ rating, comment: comment.trim() || null }),
      })
    ).data,
  remove: async (id: string) => {
    await request<void>(`/sessions/${id}`, { method: "DELETE" });
  },
};

export const VERDICT_LABEL: Record<Verdict, string> = {
  above: "Above the bar",
  meets: "Meets the bar",
  below: "Not yet at the bar",
  insufficient_evidence: "Not enough evidence",
};
