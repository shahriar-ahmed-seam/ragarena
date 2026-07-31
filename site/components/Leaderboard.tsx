"use client";

import { useMemo, useState } from "react";

import {
  LOWER_IS_BETTER,
  METRIC_HELP,
  METRIC_LABELS,
  formatMetric,
} from "@/lib/format";
import type { RunSummary, StrategyResult } from "@/lib/types";

type SortKey = string;

const COLUMNS = [
  "faithfulness",
  "answer_correctness",
  "context_precision",
  "mrr",
  "citation_validity",
  "abstention_correct",
] as const;

export default function Leaderboard({ run }: { run: RunSummary }) {
  const primary = run.primary_metric;
  const [sortKey, setSortKey] = useState<SortKey>(primary);
  const [ascending, setAscending] = useState(false);

  const rows = useMemo(() => {
    const value = (s: StrategyResult): number => {
      if (sortKey === "p95") return s.latency.p95_ms;
      if (sortKey === "cost") return s.cost_per_1k_queries_uncached_usd;
      return s.metrics[sortKey] ?? -Infinity;
    };
    return [...run.strategies].sort((a, b) =>
      ascending ? value(a) - value(b) : value(b) - value(a),
    );
  }, [run.strategies, sortKey, ascending]);

  const best = useMemo(() => {
    const out: Record<string, number> = {};
    for (const key of [primary, ...COLUMNS]) {
      const values = run.strategies
        .map((s) => s.metrics[key])
        .filter((v): v is number => v !== undefined);
      if (values.length) {
        out[key] = LOWER_IS_BETTER.has(key)
          ? Math.min(...values)
          : Math.max(...values);
      }
    }
    return out;
  }, [run.strategies, primary]);

  const cheapest = Math.min(
    ...run.strategies.map((s) => s.cost_per_1k_queries_uncached_usd),
  );
  const fastest = Math.min(...run.strategies.map((s) => s.latency.p95_ms));

  function sortBy(key: SortKey) {
    if (key === sortKey) {
      setAscending((prev) => !prev);
    } else {
      setSortKey(key);
      setAscending(key === "p95" || key === "cost");
    }
  }

  const arrow = (key: SortKey) =>
    key === sortKey ? (ascending ? "↑" : "↓") : "";

  return (
    <div className="panel overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">
            Benchmark leaderboard, sortable by any metric
          </caption>
          <thead>
            <tr className="border-b border-line text-left">
              <th scope="col" className="px-4 py-3 eyebrow">
                Strategy
              </th>
              <th scope="col" className="px-3 py-3 text-right">
                <button
                  type="button"
                  onClick={() => sortBy(primary)}
                  title={METRIC_HELP[primary]}
                  className="eyebrow transition-colors hover:text-ink"
                >
                  {METRIC_LABELS[primary] ?? primary} {arrow(primary)}
                </button>
              </th>
              <th scope="col" className="w-28 px-3 py-3" />
              {COLUMNS.map((key) => (
                <th key={key} scope="col" className="px-3 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => sortBy(key)}
                    title={METRIC_HELP[key]}
                    className="eyebrow whitespace-nowrap transition-colors hover:text-ink"
                  >
                    {METRIC_LABELS[key] ?? key} {arrow(key)}
                  </button>
                </th>
              ))}
              <th scope="col" className="px-3 py-3 text-right">
                <button
                  type="button"
                  onClick={() => sortBy("p95")}
                  title="95th percentile end-to-end latency, cache hits excluded."
                  className="eyebrow whitespace-nowrap transition-colors hover:text-ink"
                >
                  p95 {arrow("p95")}
                </button>
              </th>
              <th scope="col" className="px-4 py-3 text-right">
                <button
                  type="button"
                  onClick={() => sortBy("cost")}
                  title="USD per 1000 queries, every prompt token priced at the cache-miss rate. Judging excluded."
                  className="eyebrow whitespace-nowrap transition-colors hover:text-ink"
                >
                  $/1k {arrow("cost")}
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s, i) => {
              const score = s.metrics[primary];
              return (
                <tr
                  key={s.name}
                  className="border-b border-line/60 transition-colors last:border-0 hover:bg-panel-2/60"
                >
                  <th scope="row" className="max-w-xs px-4 py-3 text-left font-normal">
                    <span className="flex items-baseline gap-2">
                      <span className="num w-4 text-xs text-muted">{i + 1}</span>
                      <span>
                        <span className="font-medium">{s.label || s.name}</span>
                        <span className="mt-0.5 block text-xs leading-snug text-muted">
                          {s.description}
                        </span>
                      </span>
                    </span>
                  </th>
                  <td
                    className={`num px-3 py-3 text-right font-semibold ${
                      score === best[primary] ? "text-accent" : ""
                    }`}
                  >
                    {formatMetric(score)}
                  </td>
                  <td className="px-3 py-3">
                    <div
                      className="h-1.5 w-full overflow-hidden rounded-full bg-panel-2"
                      role="img"
                      aria-label={`${METRIC_LABELS[primary] ?? primary} ${formatMetric(score)}`}
                    >
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-accent-2 to-accent"
                        style={{ width: `${Math.max(0, Math.min(1, score ?? 0)) * 100}%` }}
                      />
                    </div>
                  </td>
                  {COLUMNS.map((key) => (
                    <td
                      key={key}
                      className={`num px-3 py-3 text-right ${
                        s.metrics[key] !== undefined && s.metrics[key] === best[key]
                          ? "text-accent"
                          : "text-muted"
                      }`}
                    >
                      {formatMetric(s.metrics[key])}
                    </td>
                  ))}
                  <td
                    className={`num px-3 py-3 text-right ${
                      s.latency.p95_ms === fastest ? "text-accent" : "text-muted"
                    }`}
                  >
                    {Math.round(s.latency.p95_ms).toLocaleString()}
                  </td>
                  <td
                    className={`num px-4 py-3 text-right ${
                      s.cost_per_1k_queries_uncached_usd === cheapest
                        ? "text-accent"
                        : "text-muted"
                    }`}
                  >
                    ${s.cost_per_1k_queries_uncached_usd.toFixed(3)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="border-t border-line px-4 py-3 text-xs text-muted">
        Click any column to re-sort. Green marks the best value in that column. Latency
        excludes cache hits and was measured at concurrency{" "}
        {run.environment.concurrency}; cost excludes judging and prices every prompt
        token at the cache-miss rate so run order cannot flatter a strategy.
      </p>
    </div>
  );
}
