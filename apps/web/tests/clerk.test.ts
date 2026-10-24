import { afterEach, expect, it, vi } from "vitest";

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

it("uses a fresh Clerk token and never the development email in Clerk mode", async () => {
  vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "pk_test_example");
  vi.resetModules();
  const { request, setTokenGetter } = await import("../lib/api");
  const getToken = vi.fn().mockResolvedValueOnce("first").mockResolvedValueOnce("second");
  setTokenGetter(getToken);
  const sent: Headers[] = [];
  const fetchImpl: typeof fetch = async (_url, init) => {
    sent.push(new Headers(init?.headers));
    return Response.json([]);
  };
  await request("/sessions", {}, { email: "dev@test.com", fetchImpl });
  await request("/sessions", {}, { email: "dev@test.com", fetchImpl });
  expect(sent.map(h => h.get("authorization"))).toEqual(["Bearer first", "Bearer second"]);
  expect(sent.every(h => !h.has("x-dev-user-email"))).toBe(true);
});
