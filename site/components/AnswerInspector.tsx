"use client";

import { useMemo, useState } from "react";

import { formatMs } from "@/lib/format";
import type { StrategyResult } from "@/lib/types";

type Filter = "all" | "grounded" | "ungrounded" | "unanswerable";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "ungrounded", label: "Ungrounded claims" },
  { key: "unanswerable", label: "Unanswerable" },
  { key: "grounded", label: "Fully grounded" },
];

export default function AnswerInspector({
  strategy,
}: {
  strategy: StrategyResult;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [open, setOpen] = useState<string | null>(null);

  const traces = useMemo(() => {
    return strategy.traces.filter((t) => {
      const faith = t.scores.faithfulness;
      switch (filter) {
        case "grounded":
          return faith !== undefined && faith >= 0.999;
        case "ungrounded":
          return faith !== undefined && faith < 0.999;
        case "unanswerable":
          return !t.answerable;
        default:
          return true;
      }
    });
  }, [strategy.traces, filter]);

  if (strategy.traces.length === 0) {
    return (
      <p className="panel p-4 text-sm text-muted">
        Per-question traces are kept for the winning strategy only, to keep this page
        small. The full run JSON in the repository has every trace for every strategy.
      </p>
    );
  }

  const counts: Record<Filter, number> = {
    all: strategy.traces.length,
    grounded: strategy.traces.filter(
      (t) => (t.scores.faithfulness ?? 0) >= 0.999,
    ).length,
    ungrounded: strategy.traces.filter(
      (t) => t.scores.faithfulness !== undefined && t.scores.faithfulness < 0.999,
    ).length,
    unanswerable: strategy.traces.filter((t) => !t.answerable).length,
  };

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            aria-pressed={filter === f.key}
            className={`rounded-lg border px-3 py-1.5 text-xs transition-colors ${
              filter === f.key
                ? "border-accent/60 bg-accent/10 text-accent"
                : "border-line text-muted hover:border-line hover:text-ink"
            }`}
          >
            {f.label}
            <span className="num ml-1.5 opacity-60">{counts[f.key]}</span>
          </button>
        ))}
      </div>

      <ul className="panel divide-y divide-line/60">
        {traces.map((t) => {
          const isOpen = open === t.question_id;
          const faith = t.scores.faithfulness;
          const abstained = t.answer?.abstained ?? false;
          const badge = t.error
            ? { text: "error", tone: "text-bad border-bad/40" }
            : !t.answerable
              ? abstained
                ? { text: "correctly refused", tone: "text-accent border-accent/40" }
                : { text: "answered anyway", tone: "text-bad border-bad/40" }
              : faith === undefined
                ? null
                : faith >= 0.999
                  ? { text: "grounded", tone: "text-accent border-accent/40" }
                  : {
                      text: `faith ${faith.toFixed(2)}`,
                      tone: "text-warn border-warn/40",
                    };

          return (
            <li key={t.question_id}>
              <button
                type="button"
                onClick={() => setOpen(isOpen ? null : t.question_id)}
                aria-expanded={isOpen}
                className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-panel-2/60"
              >
                <span
                  aria-hidden
                  className={`mt-1 shrink-0 text-xs text-muted transition-transform ${isOpen ? "rotate-90" : ""}`}
                >
                  ▶
                </span>
                <span className="flex-1 text-sm">{t.question}</span>
                {badge && (
                  <span
                    className={`shrink-0 rounded-md border px-2 py-0.5 text-[11px] ${badge.tone}`}
                  >
                    {badge.text}
                  </span>
                )}
              </button>

              {isOpen && (
                <div className="space-y-3 px-4 pb-4 pl-11 text-sm">
                  {t.error ? (
                    <p className="text-bad">{t.error}</p>
                  ) : (
                    <>
                      <p className="whitespace-pre-wrap">
                        {t.answer?.text ?? "(no answer)"}
                      </p>

                      {t.ground_truth && (
                        <p className="text-muted">
                          <span className="font-medium text-ink">Reference: </span>
                          {t.ground_truth}
                        </p>
                      )}

                      {t.judge_notes.grounding && (
                        <p className="text-muted">
                          <span className="font-medium text-ink">
                            Unsupported claims:{" "}
                          </span>
                          {t.judge_notes.grounding}
                        </p>
                      )}

                      {t.judge_notes.quality && (
                        <p className="text-muted">
                          <span className="font-medium text-ink">Judge: </span>
                          {t.judge_notes.quality}
                        </p>
                      )}

                      <div className="flex flex-wrap gap-1.5">
                        {t.retrieved.map((c) => {
                          const cited = t.answer?.citations.includes(c.rank);
                          return (
                            <span
                              key={c.chunk_id}
                              title={c.text.slice(0, 400)}
                              className={`rounded-md border px-2 py-0.5 font-mono text-[11px] ${
                                cited
                                  ? "border-accent-2/50 text-accent-2"
                                  : "border-line text-muted"
                              }`}
                            >
                              [{c.rank}] {c.doc_id}
                            </span>
                          );
                        })}
                      </div>

                      <p className="num text-xs text-muted">
                        {formatMs(t.timings.total_ms)} ·{" "}
                        {(
                          t.usage.prompt_tokens + t.usage.completion_tokens
                        ).toLocaleString()}{" "}
                        tokens · ${t.cost.llm_usd.toFixed(5)}
                        {t.cached && " · served from cache"}
                      </p>
                    </>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      <p className="mt-3 text-xs text-muted">
        Cited passages are highlighted. Hover a passage chip to read the retrieved
        text. Chips that are not highlighted were retrieved but never cited.
      </p>
    </div>
  );
}
