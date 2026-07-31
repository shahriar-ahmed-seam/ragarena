import Link from "next/link";

import RunView from "@/components/RunView";
import { getLatestRun, getRunIndex } from "@/lib/data";

const INSTALL = "pip install ragarena";
const RUN = "ragarena bench --suite default";

function Hero({ runs }: { runs: number }) {
  return (
    <section className="pb-4">
      <p className="eyebrow">Open source RAG evaluation harness</p>
      <h1 className="mt-3 max-w-3xl text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
        Every RAG tutorial ends at{" "}
        <span className="text-muted">&ldquo;and now add a reranker.&rdquo;</span>{" "}
        <span className="bg-gradient-to-r from-accent to-accent-2 bg-clip-text text-transparent">
          None of them tell you what it bought.
        </span>
      </h1>
      <p className="mt-5 max-w-2xl text-base leading-relaxed text-muted">
        RAGArena runs the same labelled questions through several retrieval strategies
        against the same corpus, then reports quality, latency and cost side by side.
        One command, one table, no guessing.
      </p>

      <div className="mt-7 flex flex-wrap items-center gap-3">
        <div className="panel flex items-center gap-3 px-4 py-2.5 font-mono text-sm">
          <span className="text-muted select-none">$</span>
          <span>{INSTALL}</span>
        </div>
        <div className="panel flex items-center gap-3 px-4 py-2.5 font-mono text-sm">
          <span className="text-muted select-none">$</span>
          <span>{RUN}</span>
        </div>
        <a
          href="https://github.com/shahriarseam17/ragarena"
          target="_blank"
          rel="noreferrer noopener"
          className="rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-bg transition-opacity hover:opacity-90"
        >
          Read the source
        </a>
      </div>

      <ul className="mt-8 grid gap-x-8 gap-y-2 text-sm text-muted sm:grid-cols-2 lg:grid-cols-4">
        <li>13 metrics, deterministic and judged</li>
        <li>8 retrieval strategies, 4 chunkers</li>
        <li>Runs with zero API keys on CPU</li>
        <li className="text-ink">
          {runs} committed run{runs === 1 ? "" : "s"}
        </li>
      </ul>
    </section>
  );
}

export default function Home() {
  const run = getLatestRun();
  const index = getRunIndex();

  if (!run) {
    return (
      <>
        <Hero runs={0} />
        <div className="panel mt-10 p-6">
          <h2 className="font-semibold">No runs committed yet</h2>
          <p className="mt-2 max-w-xl text-sm text-muted">
            This site builds its leaderboard from the JSON that{" "}
            <code className="font-mono text-xs">ragarena bench</code> writes into{" "}
            <code className="font-mono text-xs">results/</code>. Produce a run and
            rebuild:
          </p>
          <pre className="mt-4 overflow-x-auto rounded-lg bg-panel-2 p-4 font-mono text-xs text-muted">
            {`pip install -e ".[local]"\nragarena bench --suite quick --out results\ncd site && npm run build`}
          </pre>
        </div>
      </>
    );
  }

  return (
    <>
      <Hero runs={index.length} />

      <div className="mt-10 flex items-baseline justify-between gap-4 border-t border-line pt-8">
        <h2 className="text-sm font-semibold tracking-tight">Latest run</h2>
        {index.length > 1 && (
          <Link href="/runs/" className="text-sm text-accent-2 hover:underline">
            Compare all {index.length} runs →
          </Link>
        )}
      </div>

      <div className="mt-5">
        <RunView run={run} />
      </div>
    </>
  );
}
