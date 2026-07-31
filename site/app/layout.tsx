import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

const REPO = "https://github.com/shahriarseam17/ragarena";

export const metadata: Metadata = {
  title: {
    default: "RAGArena — head-to-head benchmarking for RAG pipelines",
    template: "%s · RAGArena",
  },
  description:
    "Retrieval quality, answer faithfulness, latency and cost for RAG pipelines, measured on the same corpus and the same labelled questions. Open source Python harness with a committed leaderboard.",
  keywords: [
    "RAG",
    "retrieval augmented generation",
    "evaluation",
    "benchmark",
    "faithfulness",
    "reranking",
    "hybrid search",
    "LLM",
  ],
  authors: [{ name: "Shahriar Ahmed Seam" }],
  openGraph: {
    title: "RAGArena — head-to-head benchmarking for RAG pipelines",
    description:
      "Quality, latency and cost for every RAG strategy, on one corpus, in one run.",
    type: "website",
  },
  robots: { index: true, follow: true },
};

function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-line/80 bg-bg/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-5 py-3.5">
        <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
          <span
            aria-hidden
            className="inline-block size-2.5 rounded-full bg-accent shadow-[0_0_14px_var(--color-accent)]"
          />
          RAGArena
        </Link>
        <nav className="ml-auto flex items-center gap-5 text-sm text-muted">
          <Link href="/" className="transition-colors hover:text-ink">
            Leaderboard
          </Link>
          <Link href="/runs/" className="transition-colors hover:text-ink">
            Runs
          </Link>
          <Link href="/methodology/" className="transition-colors hover:text-ink">
            Methodology
          </Link>
          <a
            href={REPO}
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-lg border border-line px-3 py-1.5 text-ink transition-colors hover:border-accent/60 hover:text-accent"
          >
            GitHub
          </a>
        </nav>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="mt-24 border-t border-line/80">
      <div className="mx-auto grid max-w-6xl gap-6 px-5 py-10 text-sm text-muted sm:grid-cols-2">
        <div>
          <p className="font-semibold text-ink">RAGArena</p>
          <p className="mt-1.5 max-w-md">
            An open-source harness that measures RAG pipelines instead of guessing at
            them. Every number on this site was produced by{" "}
            <code className="font-mono text-xs text-ink">ragarena bench</code> and
            committed to the repository as JSON.
          </p>
        </div>
        <div className="sm:text-right">
          <p>
            Built by{" "}
            <a
              className="text-accent-2 hover:underline"
              href="https://github.com/shahriarseam17"
              target="_blank"
              rel="noreferrer noopener"
            >
              Shahriar Ahmed Seam
            </a>
          </p>
          <p className="mt-1.5">
            <a className="hover:text-ink" href={`${REPO}/blob/main/LICENSE`}>
              MIT licensed
            </a>
            {" · "}
            <a className="hover:text-ink" href="https://pypi.org/project/ragarena/">
              PyPI
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-panel focus:px-4 focus:py-2"
        >
          Skip to content
        </a>
        <Nav />
        <main id="main" className="mx-auto max-w-6xl px-5 pt-10">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
