import { CHART, type Point, chartPoints, deltaLabel } from "@/lib/progress";

export function SkillChart({
  name,
  points,
  delta,
}: {
  name: string;
  points: Point[];
  delta: number | null;
}) {
  const coords = chartPoints(points);
  const latest = points[points.length - 1]?.score;
  const summary = `${name}: ${points.map((p) => p.score).join(", ")} out of ${CHART.maxScore}`;
  return (
    <li className="rounded-lg border border-line bg-card p-4" data-testid="skill-chart">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="font-medium">{name}</h3>
        <span className="text-sm tabular-nums text-muted">{latest}/{CHART.maxScore}</span>
      </div>
      <svg
        viewBox={`0 0 ${CHART.width} ${CHART.height}`}
        role="img"
        aria-label={summary}
        className="mt-2 h-20 w-full text-accent"
      >
        <line
          x1={CHART.pad}
          x2={CHART.width - CHART.pad}
          y1={CHART.height - CHART.pad}
          y2={CHART.height - CHART.pad}
          stroke="var(--line)"
        />
        {coords.length > 1 && (
          <polyline
            points={coords.map((c) => `${c.x},${c.y}`).join(" ")}
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
          />
        )}
        {coords.map((c, i) => (
          <circle key={i} cx={c.x} cy={c.y} r={3.5} fill="currentColor" />
        ))}
      </svg>
      <p className="text-sm text-muted">{deltaLabel(delta)}</p>
    </li>
  );
}
