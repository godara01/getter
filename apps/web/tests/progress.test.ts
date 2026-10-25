import { describe, expect, it, vi } from "vitest";

import { request } from "../lib/api";
import { CHART, chartPoints, deltaLabel, gapLabel } from "../lib/progress";

describe("chartPoints", () => {
  it("spreads points left to right and higher scores sit higher", () => {
    const pts = chartPoints([
      { date: "a", score: 1 },
      { date: "b", score: 2 },
      { date: "c", score: 4 },
    ]);
    expect(pts[0].x).toBe(CHART.pad);
    expect(pts[2].x).toBe(CHART.width - CHART.pad);
    expect(pts[0].y).toBeGreaterThan(pts[1].y);
    expect(pts[1].y).toBeGreaterThan(pts[2].y);
    expect(pts[2].y).toBe(CHART.pad);
  });

  it("centres a single point and clamps out-of-range scores", () => {
    const [p] = chartPoints([{ date: "a", score: 9 }]);
    expect(p.x).toBe(CHART.width / 2);
    expect(p.y).toBe(CHART.pad);
    expect(chartPoints([])).toEqual([]);
  });
});

describe("labels", () => {
  it("describes the change since last time", () => {
    expect(deltaLabel(null)).toBe("First score");
    expect(deltaLabel(0)).toBe("No change since last time");
    expect(deltaLabel(2)).toBe("Up 2 since last time");
    expect(deltaLabel(-1)).toBe("Down 1 since last time");
  });

  it("counts interviews for a gap", () => {
    expect(gapLabel(1)).toBe("Came up in 1 interview");
    expect(gapLabel(3)).toBe("Came up in 3 interviews");
  });
});

describe("progress request", () => {
  it("sends the dev sign-in header to /progress", async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ roles: [] })));
    const { data } = await request("/progress", {}, { email: "a@example.com", fetchImpl });
    expect(data).toEqual({ roles: [] });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url.endsWith("/progress")).toBe(true);
    expect(new Headers(init.headers).get("x-dev-user-email")).toBe("a@example.com");
  });
});
