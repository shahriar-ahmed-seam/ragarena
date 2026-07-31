/**
 * Pure presentation helpers. No filesystem access, so client components can
 * import these without dragging the build-time data loader into the bundle.
 */

import type { RunSummary, StrategyResult } from "./types";

export const METRIC_LABELS: Record<string, string> = {
  arena_score: "Arena score",
  faithfulness: "Faithfulness",
  answer_correctness: "Correctness",
  answer_relevance: "Relevance",
  context_precision: "Context precision",
  hit_rate: "Hit rate",
  doc_recall: "Doc recall",
  "precision@k": "Precision@k",
  mrr: "MRR",
  "ndcg@k": "nDCG@k",
  citation_validity: "Citation validity",
  citation_coverage: "Citation coverage",
  abstention_correct: "Abstention",
  hallucination_rate: "Hallucination rate",
};

export const METRIC_HELP: Record<string, string> = {
  arena_score:
    "Weighted composite: faithfulness 35%, correctness 25%, context precision 20%, citation validity 10%, abstention 10%.",
  faithfulness:
    "Share of the answer's atomic claims the retrieved context actually supports, graded claim by claim.",
  answer_correctness:
    "Agreement with the reference answer on a 0-4 rubric, normalised to 0-1.",
  answer_relevance: "Does the answer address what was asked? 0-4 rubric.",
  context_precision:
    "Rank-sensitive precision: relevant passages ranked above irrelevant ones.",
  hit_rate: "At least one relevant passage was retrieved.",
  doc_recall: "Labelled relevant documents represented in the results.",
  "precision@k": "Relevant passages divided by passages returned.",
  mrr: "Reciprocal rank of the first relevant passage.",
  "ndcg@k": "Binary-gain nDCG: rewards ranking the right passage first.",
  citation_validity:
    "Of the passages the answer cited, the share that were genuinely relevant.",
  citation_coverage: "Non-abstaining answers that cited at least one passage.",
  abstention_correct:
    "Refused exactly when it should have, scored on answerable questions too.",
  hallucination_rate:
    "Unanswerable questions answered anyway. Lower is better.",
};

export const LOWER_IS_BETTER = new Set(["hallucination_rate"]);

export function leaderboard(run: RunSummary): StrategyResult[] {
  return [...run.strategies].sort(
    (a, b) =>
      (b.metrics[run.primary_metric] ?? -Infinity) -
      (a.metrics[run.primary_metric] ?? -Infinity),
  );
}

/** Segment columns present across a run, with the unanswerable column last. */
export function segmentColumns(run: RunSummary): string[] {
  const seen = new Set<string>();
  for (const strategy of run.strategies) {
    for (const key of Object.keys(strategy.metrics_by_segment)) {
      if (key.startsWith("type:") || key === "unanswerable") seen.add(key);
    }
  }
  return [...seen].sort((a, b) => {
    if (a === "unanswerable") return 1;
    if (b === "unanswerable") return -1;
    return a.localeCompare(b);
  });
}

export function formatMetric(value: number | undefined): string {
  return value === undefined ? "—" : value.toFixed(3);
}

export function formatPercent(value: number | undefined): string {
  return value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}

export function formatMs(ms: number): string {
  if (ms >= 10_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.round(ms)} ms`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toISOString().slice(0, 16).replace("T", " ") + " UTC";
}
