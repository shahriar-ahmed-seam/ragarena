"use client";

import { useState } from "react";

import { METRIC_LABELS } from "@/lib/format";
import type { RunSummary } from "@/lib/types";

const W = 860;
const H = 340;
const PAD = { top: 24, right: 40, bottom: 52, left: 68 };

const PALETTE = [
  "#6ee7b7",
  "#60a5fa",
  "#c084fc",
  "#fbbf24",
  "#fb7185",
  "#34d399",
  "#f472b6",
  "#93c5fd",
];

export default function CostQualityChart({ run }: { run: RunSummary }) {
  const [hover, setHover] = useState<string | null>(null);
  const metric = run.primary_metric;

  const points = run.strategies.map((s, i) => ({
    name: s.name,
    label: s.label || s.name,
    cost: s.cost_per_1k_queries_uncached_usd,
    score: s.metrics[metric] ?? 0,
    p95: s.latency.p95_ms,
    color: PALETTE[i % PALETTE.length],
  }));

  if (points.length === 0) return null;

  const costs = points.map((p) => p.cost);
  const scores = points.map((p) => p.score);
  const costMin = Math.min(...costs);
  const costMax = Math.max(...costs);
  const scoreMin = Math.min(...scores);
  const scoreMax = Math.max(...scores);
  // Pad the domains so points never sit on an axis, and guard against a run
  // where every strategy happens to cost the same.
  const costSpan = costMax - costMin || Math.max(costMax, 0.01);
  const scoreSpan = scoreMax - scoreMin || 0.05;
  const xLo = costMin - costSpan * 0.15;
  const xHi = costMax + costSpan * 0.15;
  const yLo = scoreMin - scoreSpan * 0.2;
  const yHi = scoreMax + scoreSpan * 0.2;

  const x = (v: number) =>
    PAD.left + ((v - xLo) / (xHi - xLo)) * (W - PAD.left - PAD.right);
  const y = (v: number) =>
    H - PAD.bottom - ((v - yLo) / (yHi - yLo)) * (H - PAD.top - PAD.bottom);

  const xTicks = [xLo, (xLo + xHi) / 2, xHi];
  const yTicks = [yLo, (yLo + yHi) / 2, yHi];

  return (
    <figure className="panel p-4">
      <figcaption className="mb-1 text-sm text-muted">
        Up and to the left is better: more{" "}
        {(METRIC_LABELS[metric] ?? metric).toLowerCase()} for fewer dollars per
        thousand queries.
      </figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={`Scatter plot of ${metric} against cost per 1000 queries for ${points.length} strategies`}
      >
        {yTicks.map((t) => (
          <g key={`y${t}`}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(t)}
              y2={y(t)}
              stroke="var(--color-line)"
              strokeDasharray="3 5"
            />
            <text
              x={PAD.left - 10}
              y={y(t) + 4}
              textAnchor="end"
              fontSize="11"
              fill="var(--color-muted)"
            >
              {t.toFixed(3)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text
            key={`x${t}`}
            x={x(t)}
            y={H - PAD.bottom + 20}
            textAnchor="middle"
            fontSize="11"
            fill="var(--color-muted)"
          >
            ${t.toFixed(3)}
          </text>
        ))}

        <text
          x={(PAD.left + W - PAD.right) / 2}
          y={H - 12}
          textAnchor="middle"
          fontSize="11"
          fill="var(--color-muted)"
        >
          cost per 1,000 queries (USD, uncached)
        </text>
        <text
          x={16}
          y={(PAD.top + H - PAD.bottom) / 2}
          textAnchor="middle"
          fontSize="11"
          fill="var(--color-muted)"
          transform={`rotate(-90 16 ${(PAD.top + H - PAD.bottom) / 2})`}
        >
          {METRIC_LABELS[metric] ?? metric}
        </text>

        {points.map((p) => {
          const active = hover === p.name;
          return (
            <g
              key={p.name}
              onMouseEnter={() => setHover(p.name)}
              onMouseLeave={() => setHover(null)}
              tabIndex={0}
              onFocus={() => setHover(p.name)}
              onBlur={() => setHover(null)}
            >
              <circle
                cx={x(p.cost)}
                cy={y(p.score)}
                r={active ? 9 : 6}
                fill={p.color}
                fillOpacity={active ? 1 : 0.85}
                stroke="var(--color-bg)"
                strokeWidth="2"
              />
              <title>
                {`${p.label}: ${p.score.toFixed(3)} ${metric}, $${p.cost.toFixed(3)} per 1k, p95 ${Math.round(p.p95)} ms`}
              </title>
              <text
                x={x(p.cost) + 12}
                y={y(p.score) + 4}
                fontSize="11"
                fill={active ? "var(--color-ink)" : "var(--color-muted)"}
              >
                {p.label}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
