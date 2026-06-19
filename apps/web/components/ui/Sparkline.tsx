import { cn } from "@/lib/cn";

export interface SparklineProps {
  /** Series values (oldest → newest). */
  values: number[];
  width?: number;
  height?: number;
  className?: string;
  /** Accessible label describing the series. */
  label?: string;
  /** Fill the area under the line. */
  area?: boolean;
}

/**
 * Tiny inline sparkline drawn as hand-rolled SVG (NO chart library — keeps the
 * bundle lean, §11). A flat baseline is drawn for an all-zero / single-point
 * series. Color follows the accent token so branding flows through.
 */
export function Sparkline({
  values,
  width = 96,
  height = 28,
  className,
  label,
  area = true,
}: SparklineProps) {
  const pad = 2;
  const w = width;
  const h = height;
  const n = values.length;

  let path = "";
  let areaPath = "";

  if (n === 0) {
    const midY = h / 2;
    path = `M ${pad} ${midY} L ${w - pad} ${midY}`;
  } else {
    const max = Math.max(...values);
    const min = Math.min(...values);
    const range = max - min || 1;
    const stepX = n > 1 ? (w - pad * 2) / (n - 1) : 0;
    const points = values.map((v, i) => {
      const x = pad + i * stepX;
      const y = pad + (1 - (v - min) / range) * (h - pad * 2);
      return [x, y] as const;
    });
    // Single point → draw a flat line so something renders.
    if (n === 1) {
      const [, y] = points[0];
      path = `M ${pad} ${y} L ${w - pad} ${y}`;
    } else {
      path = points
        .map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`)
        .join(" ");
    }
    const lastX = n > 1 ? points[n - 1][0] : w - pad;
    areaPath = `${path} L ${lastX.toFixed(2)} ${h - pad} L ${pad} ${h - pad} Z`;
  }

  const gradientId = `spark-${Math.abs(hashValues(values))}`;

  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      className={cn("text-accent", className)}
      role="img"
      aria-label={label ?? "trend sparkline"}
      data-testid="sparkline"
      preserveAspectRatio="none"
    >
      {area && n > 1 ? (
        <>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.22" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={areaPath} fill={`url(#${gradientId})`} />
        </>
      ) : null}
      <path
        d={path}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Stable-ish id seed so concurrent sparklines don't collide on gradient ids. */
function hashValues(values: number[]): number {
  let h = 0;
  for (const v of values) {
    h = (h * 31 + Math.round(v)) | 0;
  }
  return h;
}
