import AnswerInspector from "@/components/AnswerInspector";
import CostQualityChart from "@/components/CostQualityChart";
import Leaderboard from "@/components/Leaderboard";
import SegmentTable from "@/components/SegmentTable";
import StageLatency from "@/components/StageLatency";
import {
  METRIC_LABELS,
  formatDate,
  formatMetric,
  formatMs,
  formatPercent,
  leaderboard,
} from "@/lib/format";
import type { RunSummary } from "@/lib/types";

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-full border border-line bg-panel/70 px-3 py-1 text-xs text-muted">
      {label} <span className="font-medium text-ink">{value}</span>
    </span>
  );
}

function Stat({
  label,
  value,
  note,
  accent,
}: {
  label: string;
  value: string;
  note: string;
  accent?: boolean;
}) {
  return (
    <div className="panel p-4">
      <p className="eyebrow">{label}</p>
      <p
        className={`num mt-1.5 text-2xl font-semibold tracking-tight ${accent ? "text-accent" : ""}`}
      >
        {value}
      </p>
      <p className="mt-1 text-xs text-muted">{note}</p>
    </div>
  );
}

export function Section({
  id,
  title,
  lead,
  children,
}: {
  id: string;
  title: string;
  lead?: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="mt-14 scroll-mt-20">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {lead && <p className="mt-1 max-w-3xl text-sm text-muted">{lead}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default function RunView({ run }: { run: RunSummary }) {
  const board = leaderboard(run);
  const top = board[0];
  const bottom = board[board.length - 1];
  const metric = run.primary_metric;
  const spread =
    (top?.metrics[metric] ?? 0) - (bottom?.metrics[metric] ?? 0);
  const judged = run.environment.judge_model !== "none";

  const weights = Object.entries(run.arena_weights)
    .map(([k, v]) => `${METRIC_LABELS[k] ?? k} ${(v * 100).toFixed(0)}%`)
    .join(", ");

  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Chip label="dataset" value={`${run.dataset.name} v${run.dataset.version}`} />
        <Chip
          label="corpus"
          value={`${run.dataset.n_documents} docs · ${run.dataset.total_words.toLocaleString()} words`}
        />
        <Chip label="questions" value={String(top?.n_questions ?? run.dataset.n_questions)} />
        <Chip label="generator" value={run.environment.generator_model} />
        <Chip label="judge" value={run.environment.judge_model} />
        <Chip label="embeddings" value={run.environment.embed_model} />
        <Chip label="reranker" value={run.environment.rerank_model} />
        <Chip label="index" value={run.environment.index_backend} />
        <Chip label="wall clock" value={`${run.duration_s.toFixed(0)}s`} />
      </div>

      {run.notes && (
        <p className="mt-4 max-w-3xl border-l-2 border-line pl-3 text-sm text-muted">
          {run.notes}
        </p>
      )}

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Winner"
          value={top?.label ?? "—"}
          note={`${METRIC_LABELS[metric] ?? metric} ${formatMetric(top?.metrics[metric])}`}
          accent
        />
        {judged ? (
          <Stat
            label="Faithfulness"
            value={formatPercent(top?.metrics.faithfulness)}
            note="claim-level grounding, winning strategy"
          />
        ) : (
          <Stat
            label="Context precision"
            value={formatPercent(top?.metrics.context_precision)}
            note="rank-sensitive retrieval precision"
          />
        )}
        <Stat
          label="p95 latency"
          value={formatMs(top?.latency.p95_ms ?? 0)}
          note={`end to end, concurrency ${run.environment.concurrency}`}
        />
        <Stat
          label="Cost / 1k queries"
          value={`$${(top?.cost_per_1k_queries_uncached_usd ?? 0).toFixed(3)}`}
          note="serving only, no cache discount"
        />
      </div>

      <Section
        id="leaderboard"
        title="Leaderboard"
        lead={
          judged
            ? `Ranked by ${METRIC_LABELS[metric] ?? metric}, a weighted composite of ${weights}. Every strategy ran the identical question set against the identical corpus, so each row differs from the one above it in exactly one decision.`
            : `Judging was disabled for this run, so strategies are ranked on ${METRIC_LABELS[metric] ?? metric} and the answer-quality metrics are absent rather than estimated.`
        }
      >
        <Leaderboard run={run} />
      </Section>

      <Section
        id="cost"
        title="Quality against cost"
        lead={`The spread between best and worst on this corpus is ${(spread * 100).toFixed(1)} points. Whether that is worth the extra latency is the actual decision.`}
      >
        <CostQualityChart run={run} />
      </Section>

      <Section
        id="latency"
        title="Where the time goes"
        lead="Reranking and query expansion buy quality with latency. This is the bill."
      >
        <StageLatency run={run} />
      </Section>

      <Section
        id="segments"
        title="Behaviour by question type"
        lead="The bundled corpus contains competing near-identical facts on purpose: two rate limits, three request timeouts, two signature schemes, six retention windows. Multi-hop and comparison questions are where that bites."
      >
        <SegmentTable run={run} />
      </Section>

      {top && (
        <Section
          id="answers"
          title={`Answer inspection: ${top.label}`}
          lead="Every question the winning strategy answered, with the specific claims the judge could not ground in the retrieved context. An eval you cannot audit is a vibe with a decimal point."
        >
          <AnswerInspector strategy={top} />
        </Section>
      )}

      <Section id="provenance" title="Provenance">
        <div className="panel p-4 text-sm text-muted">
          <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
            <div className="flex justify-between gap-4">
              <dt>Run id</dt>
              <dd className="font-mono text-xs text-ink">{run.run_id}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Completed</dt>
              <dd className="text-ink">{formatDate(run.created_at)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>RAGArena</dt>
              <dd className="text-ink">{run.environment.ragarena_version}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Python</dt>
              <dd className="text-ink">{run.environment.python_version}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Strategies</dt>
              <dd className="text-ink">{run.strategies.length}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Judging cost</dt>
              <dd className="num text-ink">
                $
                {run.strategies
                  .reduce((sum, s) => sum + s.eval_cost_usd, 0)
                  .toFixed(4)}
              </dd>
            </div>
          </dl>
          <p className="mt-4 border-t border-line pt-3 text-xs">
            {run.dataset.description}
          </p>
        </div>
      </Section>
    </>
  );
}
