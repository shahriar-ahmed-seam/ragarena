/**
 * Build-time data access. Server-only: reads the committed run artefacts from
 * ../results during `next build`, so the exported site ships plain HTML with no
 * runtime data fetching. Client components must import from ./format instead.
 */

import "server-only";

import fs from "node:fs";
import path from "node:path";

import type { RunIndexEntry, RunSummary } from "./types";

const RESULTS_DIR = path.join(process.cwd(), "..", "results");

function readJson<T>(file: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8")) as T;
  } catch {
    return null;
  }
}

export function getRunIndex(): RunIndexEntry[] {
  const index = readJson<{ runs: RunIndexEntry[] }>(
    path.join(RESULTS_DIR, "index.json"),
  );
  if (index?.runs?.length) {
    return index.runs;
  }
  // No index.json: derive entries from whatever summaries exist, so the site
  // still builds from a partially populated results directory.
  if (!fs.existsSync(RESULTS_DIR)) return [];
  return fs
    .readdirSync(RESULTS_DIR)
    .filter((f) => f.endsWith(".summary.json"))
    .map((f) => readJson<RunSummary>(path.join(RESULTS_DIR, f)))
    .filter((r): r is RunSummary => r !== null)
    .map((run) => {
      const winner = run.strategies.find((s) => s.name === run.winner);
      return {
        run_id: run.run_id,
        created_at: run.created_at,
        duration_s: run.duration_s,
        notes: run.notes,
        primary_metric: run.primary_metric,
        dataset: run.dataset.name,
        dataset_version: run.dataset.version,
        n_documents: run.dataset.n_documents,
        n_questions: winner?.n_questions ?? run.dataset.n_questions,
        n_strategies: run.strategies.length,
        generator_model: run.environment.generator_model,
        judge_model: run.environment.judge_model,
        embed_model: run.environment.embed_model,
        rerank_model: run.environment.rerank_model,
        winner: run.winner,
        winner_label: winner?.label ?? "",
        winner_score: winner?.metrics[run.primary_metric] ?? 0,
        summary: `${run.run_id}.summary.json`,
      } satisfies RunIndexEntry;
    })
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
}

export function getRun(runId: string): RunSummary | null {
  return readJson<RunSummary>(path.join(RESULTS_DIR, `${runId}.summary.json`));
}

export function getLatestRun(): RunSummary | null {
  const [newest] = getRunIndex();
  return newest ? getRun(newest.run_id) : null;
}
