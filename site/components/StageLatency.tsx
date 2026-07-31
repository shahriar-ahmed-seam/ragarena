import { formatMs, leaderboard } from "@/lib/format";
import type { RunSummary } from "@/lib/types";

const STAGES = [
  { key: "embed_query_ms", label: "embed query", color: "#60a5fa" },
  { key: "retrieve_ms", label: "retrieve + transform", color: "#6ee7b7" },
  { key: "rerank_ms", label: "rerank", color: "#fbbf24" },
  { key: "generate_ms", label: "generate", color: "#c084fc" },
] as const;

export default function StageLatency({ run }: { run: RunSummary }) {
  const rows = leaderboard(run);
  const totals = rows.map((s) =>
    STAGES.reduce((sum, stage) => sum + (s.stage_latency[stage.key] ?? 0), 0),
  );
  const max = Math.max(...totals, 1);

  return (
    <div className="panel p-4">
      <div className="mb-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted">
        {STAGES.map((stage) => (
          <span key={stage.key} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block size-2.5 rounded-sm"
              style={{ background: stage.color }}
            />
            {stage.label}
          </span>
        ))}
      </div>

      <ul className="space-y-3">
        {rows.map((s, i) => {
          const total = totals[i];
          return (
            <li key={s.name}>
              <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
                <span className="truncate">{s.label || s.name}</span>
                <span className="num shrink-0 text-xs text-muted">
                  {formatMs(total)} mean
                </span>
              </div>
              <div
                className="flex h-3 w-full overflow-hidden rounded-full bg-panel-2"
                role="img"
                aria-label={STAGES.map(
                  (stage) =>
                    `${stage.label} ${Math.round(s.stage_latency[stage.key] ?? 0)} ms`,
                ).join(", ")}
              >
                {STAGES.map((stage) => {
                  const value = s.stage_latency[stage.key] ?? 0;
                  if (value <= 0) return null;
                  return (
                    <span
                      key={stage.key}
                      title={`${stage.label}: ${Math.round(value)} ms`}
                      style={{
                        width: `${(value / max) * 100}%`,
                        background: stage.color,
                      }}
                    />
                  );
                })}
              </div>
            </li>
          );
        })}
      </ul>

      <p className="mt-4 text-xs text-muted">
        Mean milliseconds per stage, cache hits excluded, bars scaled to the slowest
        strategy. Query expansion shows up under retrieve because it happens before
        the retrievers run.
      </p>
    </div>
  );
}
