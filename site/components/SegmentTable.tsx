import { formatMetric, leaderboard, segmentColumns } from "@/lib/format";
import type { RunSummary } from "@/lib/types";

function heat(value: number | undefined, lo: number, hi: number): string {
  if (value === undefined) return "";
  if (hi - lo < 1e-9) return "";
  const t = (value - lo) / (hi - lo);
  // Low values get a warm tint, high values a cool green one. Subtle enough to
  // read as emphasis rather than decoration.
  return t >= 0.66
    ? "bg-accent/10 text-accent"
    : t <= 0.33
      ? "bg-bad/10 text-bad"
      : "text-ink";
}

export default function SegmentTable({ run }: { run: RunSummary }) {
  const rows = leaderboard(run);
  const columns = segmentColumns(run);

  const metricFor = (column: string) =>
    column === "unanswerable" ? "abstention_correct" : "arena_score";

  const ranges = new Map<string, [number, number]>();
  for (const column of columns) {
    const values = rows
      .map((s) => s.metrics_by_segment[column]?.[metricFor(column)])
      .filter((v): v is number => v !== undefined);
    if (values.length) ranges.set(column, [Math.min(...values), Math.max(...values)]);
  }

  const counts = new Map<string, number>();
  for (const column of columns) {
    const n = rows[0]?.metrics_by_segment[column]?.n;
    if (n !== undefined) counts.set(column, n);
  }

  return (
    <div className="panel overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">
            Scores broken down by question type
          </caption>
          <thead>
            <tr className="border-b border-line text-left">
              <th scope="col" className="px-4 py-3 eyebrow">
                Strategy
              </th>
              {columns.map((column) => (
                <th key={column} scope="col" className="px-3 py-3 text-right">
                  <span className="eyebrow whitespace-nowrap">
                    {column.replace("type:", "").replace(/_/g, " ")}
                  </span>
                  {counts.has(column) && (
                    <span className="num mt-0.5 block text-[10px] font-normal normal-case tracking-normal text-muted">
                      n={counts.get(column)}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr
                key={s.name}
                className="border-b border-line/60 last:border-0 hover:bg-panel-2/60"
              >
                <th scope="row" className="px-4 py-2.5 text-left font-normal">
                  {s.label || s.name}
                </th>
                {columns.map((column) => {
                  const value = s.metrics_by_segment[column]?.[metricFor(column)];
                  const [lo, hi] = ranges.get(column) ?? [0, 1];
                  return (
                    <td
                      key={column}
                      className={`num px-3 py-2.5 text-right ${heat(value, lo, hi)}`}
                    >
                      {formatMetric(value)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="border-t border-line px-4 py-3 text-xs text-muted">
        Arena score per question type, except the unanswerable column which shows
        abstention accuracy: the share of questions with no answer in the corpus that
        the pipeline correctly refused. Averages hide the interesting failures, and
        multi-hop and comparison questions are usually where strategies separate.
      </p>
    </div>
  );
}
