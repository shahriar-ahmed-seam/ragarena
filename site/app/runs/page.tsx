import type { Metadata } from "next";
import Link from "next/link";

import { getRunIndex } from "@/lib/data";
import { formatDate, formatMetric } from "@/lib/format";

export const metadata: Metadata = {
  title: "Runs",
  description:
    "Every committed RAGArena benchmark run, with the models and corpus each one used.",
};

export default function RunsPage() {
  const runs = getRunIndex();

  return (
    <>
      <p className="eyebrow">Archive</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">Committed runs</h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted">
        Each run is a JSON artefact in the repository, so a result can be re-rendered,
        diffed against a later run, or checked against the exact configuration that
        produced it. Absolute numbers are corpus-specific; the useful output is the
        ranking of strategies within a run.
      </p>

      {runs.length === 0 ? (
        <p className="panel mt-8 p-6 text-sm text-muted">
          No runs committed yet.
        </p>
      ) : (
        <ul className="mt-8 space-y-3">
          {runs.map((run) => (
            <li key={run.run_id}>
              <Link
                href={`/runs/${run.run_id}/`}
                className="panel block p-5 transition-colors hover:border-accent/40"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <h2 className="font-medium">
                    {run.n_strategies} strateg{run.n_strategies === 1 ? "y" : "ies"} ·{" "}
                    {run.n_questions} questions · {run.dataset} v
                    {run.dataset_version}
                  </h2>
                  <span className="num text-xs text-muted">
                    {formatDate(run.created_at)}
                  </span>
                </div>

                {run.notes && (
                  <p className="mt-2 max-w-3xl text-sm text-muted">{run.notes}</p>
                )}

                <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1.5 text-xs text-muted">
                  <span>
                    winner{" "}
                    <span className="font-medium text-accent">
                      {run.winner_label || run.winner}
                    </span>{" "}
                    <span className="num">{formatMetric(run.winner_score)}</span>
                  </span>
                  <span>
                    generator <span className="text-ink">{run.generator_model}</span>
                  </span>
                  <span>
                    judge <span className="text-ink">{run.judge_model}</span>
                  </span>
                  <span>
                    embeddings <span className="text-ink">{run.embed_model}</span>
                  </span>
                  <span>
                    reranker <span className="text-ink">{run.rerank_model}</span>
                  </span>
                  <span className="num">{run.duration_s.toFixed(0)}s wall clock</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
