// Geometry and wording for the progress charts. Pure functions so they are easy to test.

export const CHART = { width: 240, height: 80, pad: 10, maxScore: 4 };

export interface Point {
  date: string;
  score: number;
}

/** SVG coordinates for a score history, oldest first. One point sits in the middle. */
export function chartPoints(points: Point[]): { x: number; y: number }[] {
  const { width, height, pad, maxScore } = CHART;
  const inner = { w: width - 2 * pad, h: height - 2 * pad };
  return points.map((p, i) => ({
    x: pad + (points.length === 1 ? inner.w / 2 : (inner.w * i) / (points.length - 1)),
    y: pad + inner.h * (1 - Math.min(Math.max(p.score, 0), maxScore) / maxScore),
  }));
}

export function deltaLabel(delta: number | null): string {
  if (delta === null) return "First score";
  if (delta === 0) return "No change since last time";
  return `${delta > 0 ? "Up" : "Down"} ${Math.abs(delta)} since last time`;
}

export function gapLabel(sessions: number): string {
  return sessions === 1 ? "Came up in 1 interview" : `Came up in ${sessions} interviews`;
}
