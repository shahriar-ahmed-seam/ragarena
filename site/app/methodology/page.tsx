import type { Metadata } from "next";

import { getLatestRun } from "@/lib/data";
import { METRIC_HELP, METRIC_LABELS } from "@/lib/format";

export const metadata: Metadata = {
  title: "Methodology",
  description:
    "How RAGArena measures RAG pipelines: metrics, the judge, latency, cost accounting, and what the numbers do not tell you.",
};

const REPO = "https://github.com/shahriar-ahmed-seam/ragarena";

function Block({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      <div className="mt-3 max-w-3xl space-y-3 text-sm leading-relaxed text-muted">
        {children}
      </div>
    </section>
  );
}

export default function MethodologyPage() {
  const run = getLatestRun();
  const weights = run?.arena_weights ?? {};

  return (
    <>
      <p className="eyebrow">How this works</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">Methodology</h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted">
        A benchmark you cannot audit is a vibe with a decimal point. Everything below is
        implemented in{" "}
        <a className="text-accent-2 hover:underline" href={REPO}>
          the repository
        </a>
        , and every number on this site was produced by the same code path a user gets
        from <code className="font-mono text-xs">pip install ragarena</code>.
      </p>

      <Block title="The pipeline under test">
        <p>
          A strategy is a point in one configuration space rather than a bespoke class,
          which keeps the axes composable and makes a leaderboard interpretable:
        </p>
        <pre className="panel overflow-x-auto p-4 font-mono text-xs leading-relaxed text-ink">
          {`query transform  ->  dense / lexical retrieval  ->  fusion  ->  rerank  ->  top_k`}
        </pre>
        <p>
          The default suite walks that ladder one change at a time: BM25 only, dense
          only, hybrid with reciprocal rank fusion, hybrid plus a cross-encoder, a wider
          reranking pool, multi-query expansion, then HyDE. Two rows that differ in
          three ways tell you nothing about which of the three mattered.
        </p>
      </Block>

      <Block title="Metrics">
        <p>
          Deterministic metrics come from the labels and cost nothing. Judged metrics
          use an LLM grader on a fixed rubric at temperature 0. Metrics undefined for a
          question type are skipped rather than zero-filled, so the unanswerable subset
          cannot drag retrieval averages down for reasons unrelated to retrieval.
        </p>
        <dl className="panel divide-y divide-line/60">
          {Object.entries(METRIC_HELP).map(([key, help]) => (
            <div key={key} className="px-4 py-3">
              <dt className="text-sm font-medium text-ink">
                {METRIC_LABELS[key] ?? key}
              </dt>
              <dd className="mt-1 text-sm">{help}</dd>
            </div>
          ))}
        </dl>
      </Block>

      <Block title="Faithfulness is graded claim by claim">
        <p>
          The judge decomposes an answer into atomic factual claims and labels each one
          supported or unsupported against the retrieved context. The score is supported
          divided by total. A holistic one-to-five rating would average away the single
          fabricated sentence inside an otherwise correct answer, which is precisely the
          failure worth catching. Numbers, names and thresholds must match exactly,
          which matters on a corpus that deliberately contains six different retention
          windows.
        </p>
        <p>
          Unsupported claims are stored on the trace and rendered on every run page, so
          a low score is always traceable to a specific sentence.
        </p>
      </Block>

      <Block title="Abstention counts, in both directions">
        <p>
          Eleven of the bundled questions have no answer anywhere in the corpus, and
          their vocabulary overlaps heavily with content that does exist. Refusing them
          scores; answering them anyway is a hallucination. Abstention is also scored on
          answerable questions, so a pipeline that refuses everything is penalised
          rather than rewarded.
        </p>
      </Block>

      <Block title="The composite">
        {Object.keys(weights).length > 0 ? (
          <>
            <p>The headline score is a weighted blend:</p>
            <ul className="panel divide-y divide-line/60">
              {Object.entries(weights).map(([key, weight]) => (
                <li
                  key={key}
                  className="flex items-center justify-between px-4 py-2.5 text-sm"
                >
                  <span className="text-ink">{METRIC_LABELS[key] ?? key}</span>
                  <span className="num">{(weight * 100).toFixed(0)}%</span>
                </li>
              ))}
            </ul>
          </>
        ) : null}
        <p>
          The weights are an opinion: for a RAG product the worst outcome is a confident
          wrong answer, so grounding and correctness dominate, retrieval quality is the
          mechanism that produces them, and citation and abstention behaviour are what
          make the product trustworthy rather than merely accurate. Disagree and rank on
          a single column instead; the table sorts.
        </p>
        <p>
          With judging disabled the composite is omitted entirely rather than
          recalculated from three retrieval metrics and presented as answer quality.
        </p>
      </Block>

      <Block title="Latency">
        <p>
          Measured end to end per question and broken out per stage. Cache hits are
          excluded, because a cached run measures SQLite rather than a pipeline. The
          concurrency used is recorded in every run artefact: local ONNX models saturate
          the CPU, so parallel questions contend and inflate the tail. Compare latency
          only across strategies measured at the same concurrency.
        </p>
      </Block>

      <Block title="Cost">
        <p>
          Real token counts from provider responses multiplied by published prices. The
          model that actually ran is what gets billed, so requesting a hosted embedding
          model and falling back to a local one does not charge you for the hosted one.
        </p>
        <p>
          Three figures are tracked separately. What you would really pay, including
          provider prompt-cache discounts. The same figure with every prompt token
          priced at the cache-miss rate, which is the comparable one and the one this
          site ranks on: DeepSeek bills cached prefixes at roughly two percent of the
          miss rate, so without it whichever strategy ran second looks cheaper.
          And the cost of judging, kept out of both, because it is the price of
          measuring rather than of serving.
        </p>
      </Block>

      <Block title="The corpus">
        <p>
          The bundled <code className="font-mono text-xs">meridian</code> dataset is a
          synthetic knowledge base for a fictional logistics API company, written from
          scratch for this project. That matters twice over: no licensing restrictions,
          and it cannot have leaked into any model&apos;s training data, so a model
          cannot answer from memory instead of from retrieval.
        </p>
        <p>
          It is deliberately adversarial. Two different rate limits, three different
          request timeouts, two signature schemes with different tolerances, six
          retention windows, two retry policies. Lexical search has real distractors to
          fall for, and several questions can only be answered by combining two
          documents.
        </p>
      </Block>

      <Block title="What these numbers do not tell you">
        <p>
          LLM-as-judge is not ground truth. Agreement with human grading is good on
          factoid and numeric questions and weaker on open-ended ones. The mitigations
          are structural rather than rhetorical: judge with a different model than you
          generate with, keep the deterministic retrieval metrics visible alongside the
          judged ones, and publish the judge&apos;s reasoning for every question so it
          can be checked.
        </p>
        <p>
          Absolute values are specific to this corpus. Run it on your own documents; the
          ranking on your data is the only ranking that predicts anything about your
          product.
        </p>
      </Block>
    </>
  );
}
