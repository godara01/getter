import { describe, expect, it, vi } from "vitest";

import { ApiError, request } from "../lib/api";
import { formatClock, splitBlocks } from "../lib/text";

describe("splitBlocks", () => {
  it("separates prose from fenced code", () => {
    const blocks = splitBlocks("Review this:\n\n```dockerfile\nFROM node\nRUN x\n```\n\nWhy?");
    expect(blocks).toEqual([
      { kind: "text", text: "Review this:" },
      { kind: "code", lang: "dockerfile", text: "FROM node\nRUN x" },
      { kind: "text", text: "Why?" },
    ]);
  });

  it("keeps plain text whole", () => {
    expect(splitBlocks("Just a question?")).toEqual([{ kind: "text", text: "Just a question?" }]);
  });
});

describe("formatClock", () => {
  it("formats minutes and seconds", () => {
    expect(formatClock(480)).toBe("8:00");
    expect(formatClock(65.9)).toBe("1:05");
    expect(formatClock(-3)).toBe("0:00");
  });
});

describe("request", () => {
  it("sends the dev sign-in header and JSON body", async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ ok: 1 }), { status: 201 }));
    const res = await request<{ ok: number }>(
      "/sessions",
      { method: "POST", body: "{}" },
      { email: "a@b.co", fetchImpl },
    );
    expect(res).toEqual({ status: 201, data: { ok: 1 } });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/sessions");
    const headers = new Headers(init.headers);
    expect(headers.get("x-dev-user-email")).toBe("a@b.co");
    expect(headers.get("content-type")).toBe("application/json");
  });

  it("turns API errors into ApiError with the server's message", async () => {
    const fetchImpl = vi.fn(
      async () => new Response(JSON.stringify({ detail: "limit reached" }), { status: 429 }),
    );
    await expect(request("/sessions", {}, { email: null, fetchImpl })).rejects.toEqual(
      new ApiError(429, "limit reached"),
    );
  });

  it("joins validation errors", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(JSON.stringify({ detail: [{ msg: "a" }, { msg: "b" }] }), { status: 422 }),
    );
    await expect(request("/x", {}, { email: null, fetchImpl })).rejects.toThrow("a; b");
  });
});
