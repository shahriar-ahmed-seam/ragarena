import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import RunView from "@/components/RunView";
import { getRun, getRunIndex } from "@/lib/data";

type Params = { runId: string };

export function generateStaticParams(): Params[] {
  return getRunIndex().map((run) => ({ runId: run.run_id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { runId } = await params;
  const run = getRun(runId);
  if (!run) return { title: "Run not found" };
  return {
    title: `Run ${runId}`,
    description:
      run.notes ||
      `RAGArena benchmark of ${run.strategies.length} strategies on ${run.dataset.name}.`,
  };
}

export default async function RunPage({ params }: { params: Promise<Params> }) {
  const { runId } = await params;
  const run = getRun(runId);
  if (!run) notFound();

  return (
    <>
      <Link href="/runs/" className="text-sm text-accent-2 hover:underline">
        ← All runs
      </Link>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">
        {run.strategies.length} strateg
        {run.strategies.length === 1 ? "y" : "ies"} on {run.dataset.name}
      </h1>
      <p className="num mt-1 font-mono text-xs text-muted">{run.run_id}</p>
      <div className="mt-6">
        <RunView run={run} />
      </div>
    </>
  );
}
