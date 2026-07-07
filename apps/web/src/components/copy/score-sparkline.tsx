"use client";

import React, { useLayoutEffect, useRef, useState } from "react";
import type { ApiScoreSnapshot } from "@/lib/types";

/**
 * Sparkline of a wallet's sustainability score over time (stat-tile trend).
 *
 * Mark spec: single 2px line in the de-emphasis hue (muted-foreground via
 * currentColor), with only the current point marked in the accent. No axes,
 * grid, or per-point labels — the panel's score block carries the current
 * value; this shows shape only.
 *
 * The y-domain is the data extent widened to at least MIN_SPAN points
 * (clamped to 0-100): a fixed 0-100 domain flattens real trends, while a raw
 * min/max domain turns ±0.2 noise into drama.
 */

const HEIGHT = 48;
const PAD = 4; // keeps the 2px stroke and endpoint dot inside the box
const MIN_SPAN = 10;

interface ScoreSparklineProps {
  snapshots: ApiScoreSnapshot[];
}

export function ScoreSparkline({ snapshots }: ScoreSparklineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  // The detail panel has a fixed width, so a one-shot measure is enough;
  // pixel-space rendering keeps the stroke width and dot radius undistorted.
  useLayoutEffect(() => {
    if (containerRef.current) setWidth(containerRef.current.offsetWidth);
  }, []);

  const points = snapshots.filter(
    (s): s is ApiScoreSnapshot & { total_score: number } =>
      typeof s.total_score === "number",
  );
  if (points.length < 2) return null;

  const scores = points.map((p) => p.total_score);
  let lo = Math.min(...scores);
  let hi = Math.max(...scores);
  const shortfall = MIN_SPAN - (hi - lo);
  if (shortfall > 0) {
    lo = Math.max(0, lo - shortfall / 2);
    hi = Math.min(100, lo + Math.max(hi - lo, MIN_SPAN));
    lo = Math.max(0, hi - MIN_SPAN);
  }

  const x = (i: number) =>
    PAD + (i / (points.length - 1)) * (width - 2 * PAD);
  const y = (score: number) =>
    PAD + (1 - (score - lo) / (hi - lo)) * (HEIGHT - 2 * PAD);

  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.total_score).toFixed(1)}`)
    .join(" ");
  const last = points[points.length - 1];

  return (
    <div ref={containerRef} className="w-full text-muted-foreground">
      {width > 0 && (
        <svg
          width={width}
          height={HEIGHT}
          role="img"
          aria-label={`Sustainability score trend, ${points.length} snapshots, currently ${last.total_score.toFixed(0)}`}
        >
          <path d={path} fill="none" stroke="currentColor" strokeWidth={2} />
          <circle
            cx={x(points.length - 1)}
            cy={y(last.total_score)}
            r={3}
            className="fill-accent"
          />
        </svg>
      )}
    </div>
  );
}
