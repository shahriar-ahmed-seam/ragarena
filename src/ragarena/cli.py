"""RAGArena command line interface."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from . import _version
from .cache import ResponseCache
from .config import Settings, get_settings
from .datasets import list_bundled, load_dataset
from .errors import RAGArenaError
from .presets import (
    DEFAULT_SUITE,
    PRESETS,
    QUICK_SUITE,
    build_suite,
    chunking_suite,
    default_chunker,
    get_preset,
)
from .report import update_index, write_html, write_json, write_summary
from .runner import BenchmarkRunner, StrategySpec
from .types import RunResult

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Head-to-head benchmarking for RAG pipelines: retrieval quality, "
    "answer faithfulness, latency and cost in one run.",
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"ragarena {_version.__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    """RAGArena."""


# --------------------------------------------------------------------------- #
# bench
# --------------------------------------------------------------------------- #
@app.command()
def bench(
    dataset: str = typer.Option("meridian", "--dataset", "-d", help="Bundled name or directory."),
    suite: str = typer.Option(
        "default", "--suite", "-s", help="default | quick | chunking | all"
    ),
    strategies: str = typer.Option(
        "", "--strategies", help="Comma-separated preset names, overrides --suite."
    ),
    limit: int = typer.Option(0, "--limit", "-n", help="Only run the first N questions."),
    out: Path = typer.Option(Path("results"), "--out", "-o", help="Output directory."),
    concurrency: int = typer.Option(0, "--concurrency", "-c", help="Parallel questions."),
    judge: bool = typer.Option(True, "--judge/--no-judge", help="Run LLM-as-judge metrics."),
    index: str = typer.Option("memory", "--index", help="memory | pgvector"),
    embed_provider: str = typer.Option("", "--embed-provider", help="voyage | fastembed | hash"),
    embed_model: str = typer.Option("", "--embed-model"),
    rerank_provider: str = typer.Option("", "--rerank-provider", help="voyage | crossencoder | none"),
    rerank_model: str = typer.Option("", "--rerank-model"),
    generator_model: str = typer.Option("", "--generator-model"),
    judge_model: str = typer.Option("", "--judge-model"),
    voyage_rpm: int = typer.Option(
        0, "--voyage-rpm", help="Throttle Voyage calls to N requests/minute (0 = no pacing)."
    ),
    llm_rpm: int = typer.Option(0, "--llm-rpm", help="Throttle LLM calls to N requests/minute."),
    cache: bool = typer.Option(True, "--cache/--no-cache", help="Reuse cached provider calls."),
    notes: str = typer.Option("", "--notes", help="Free text stored in the run artefact."),
) -> None:
    """Run a benchmark and write JSON + an HTML report."""
    overrides: dict[str, object] = {"cache_enabled": cache}
    if concurrency:
        overrides["concurrency"] = concurrency
    if embed_provider:
        overrides["embed_provider"] = embed_provider
    if embed_model:
        overrides["embed_model"] = embed_model
    if rerank_provider:
        overrides["rerank_provider"] = rerank_provider
    if rerank_model:
        overrides["rerank_model"] = rerank_model
    if generator_model:
        overrides["generator_model"] = generator_model
    if judge_model:
        overrides["judge_model"] = judge_model
    if voyage_rpm:
        overrides["voyage_rpm"] = voyage_rpm
    if llm_rpm:
        overrides["llm_rpm"] = llm_rpm

    try:
        settings = get_settings(refresh=True, **overrides)
        data = load_dataset(dataset)
        specs = _resolve_specs(suite, strategies)
    except RAGArenaError as exc:
        console.print(f"[bold red]error[/] {exc}")
        raise typer.Exit(code=1) from exc

    total_questions = limit or data.n_questions
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        tasks: dict[str, TaskID] = {}

        def on_strategy_start(name: str, position: int, total: int) -> None:
            tasks[name] = progress.add_task(
                f"[{position}/{total}] {name}", total=total_questions
            )

        def on_progress(name: str, done: int, _total: int) -> None:
            task_id = tasks.get(name)
            if task_id is not None:
                progress.update(task_id, completed=done)

        try:
            runner = BenchmarkRunner(
                settings,
                data,
                specs,
                index_backend=index,
                judge_enabled=judge,
                limit_questions=limit or None,
                notes=notes,
                on_progress=on_progress,
                on_strategy_start=on_strategy_start,
            )
        except RAGArenaError as exc:
            console.print(f"[bold red]error[/] {exc}")
            raise typer.Exit(code=1) from exc

        # Printed after construction so the panel names the models that were
        # actually loaded, not the ones that were requested.
        progress.console.print(
            Panel.fit(
                f"[bold]{data.name}[/] v{data.version}  "
                f"{data.n_documents} docs / {data.total_words:,} words / "
                f"{total_questions} questions\n"
                f"generator [cyan]{settings.generator_model}[/]  "
                f"judge [cyan]{settings.judge_model if judge else 'off'}[/]\n"
                f"embed [cyan]{runner.embed_model}[/]  "
                f"rerank [cyan]{runner.rerank_model}[/]\n"
                f"index [cyan]{index}[/]  concurrency [cyan]{settings.concurrency}[/]  "
                f"cache [cyan]{'on' if settings.cache_enabled else 'off'}[/]",
                title=f"RAGArena {_version.__version__}",
                border_style="cyan",
            )
        )
        try:
            result = asyncio.run(runner.run())
        except RAGArenaError as exc:
            console.print(f"[bold red]error[/] {exc}")
            raise typer.Exit(code=1) from exc

    _print_leaderboard(result)

    out.mkdir(parents=True, exist_ok=True)
    json_path = write_json(result, out / f"{result.run_id}.json")
    html_path = write_html(result, out / f"{result.run_id}.html")
    summary_path = write_summary(result, out / f"{result.run_id}.summary.json")
    index_path = update_index(out, result)

    console.print()
    console.print(f"  json    [cyan]{json_path}[/]")
    console.print(f"  report  [cyan]{html_path}[/]")
    console.print(f"  site    [cyan]{summary_path}[/]")
    console.print(f"  index   [cyan]{index_path}[/]")

    errors = sum(s.n_errors for s in result.strategies)
    if errors:
        console.print(f"[yellow]{errors} question run(s) errored; see the JSON for details.[/]")


def _resolve_specs(suite: str, strategies: str) -> list[StrategySpec]:
    if strategies:
        names = [n.strip() for n in strategies.split(",") if n.strip()]
        return [StrategySpec(strategy=get_preset(n)) for n in names]
    key = suite.lower()
    if key == "chunking":
        return [StrategySpec(strategy=s, chunker=c) for s, c in chunking_suite()]
    if key == "quick":
        return [StrategySpec(strategy=s) for s in build_suite(QUICK_SUITE)]
    if key == "all":
        return [StrategySpec(strategy=s) for s in build_suite(sorted(PRESETS))]
    return [StrategySpec(strategy=s) for s in build_suite(DEFAULT_SUITE)]


def _print_leaderboard(result: RunResult) -> None:
    table = Table(title="Leaderboard", title_style="bold", header_style="dim")
    table.add_column("#", justify="right")
    table.add_column("strategy")
    table.add_column("arena", justify="right")
    table.add_column("faith", justify="right")
    table.add_column("correct", justify="right")
    table.add_column("ctx prec", justify="right")
    table.add_column("cite", justify="right")
    table.add_column("abstain", justify="right")
    table.add_column("p95 ms", justify="right")
    table.add_column("$/1k", justify="right")

    for rank, strategy in enumerate(result.leaderboard(), start=1):
        m = strategy.metrics
        style = "bold green" if rank == 1 else ""
        table.add_row(
            str(rank),
            strategy.label,
            f"{m.get('arena_score', 0):.3f}",
            f"{m.get('faithfulness', 0):.3f}",
            f"{m.get('answer_correctness', 0):.3f}",
            f"{m.get('context_precision', 0):.3f}",
            f"{m.get('citation_validity', 0):.3f}",
            f"{m.get('abstention_correct', 0):.3f}",
            f"{strategy.latency.p95_ms:.0f}",
            f"{strategy.cost_per_1k_queries_uncached_usd:.2f}",
            style=style,
        )
    console.print()
    console.print(table)

    serving = sum(s.cost.total_usd for s in result.strategies)
    judging = sum(s.eval_cost_usd for s in result.strategies)
    console.print(
        f"  run took [cyan]{result.duration_s}s[/] - "
        f"serving [cyan]${serving:.4f}[/] + judging [cyan]${judging:.4f}[/]"
    )


# --------------------------------------------------------------------------- #
# ask
# --------------------------------------------------------------------------- #
@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to answer."),
    dataset: str = typer.Option("meridian", "--dataset", "-d"),
    strategy: str = typer.Option("hybrid-rerank", "--strategy", "-s"),
    show_context: bool = typer.Option(False, "--context", help="Print the retrieved passages."),
) -> None:
    """Answer one question with one strategy. Useful for eyeballing behaviour."""

    async def run() -> None:
        settings = get_settings(refresh=True)
        data = load_dataset(dataset)
        selected = get_preset(strategy)

        from .generation import Generator
        from .index import build_index
        from .providers import build_embedder, build_llm, build_reranker
        from .strategies import RetrievalContext

        cache = ResponseCache(settings.cache_dir, enabled=settings.cache_enabled)
        llm = build_llm(settings, cache)
        embedder = build_embedder(settings, cache)
        reranker = build_reranker(settings, cache)
        index = build_index("memory", embedder)
        try:
            with console.status("indexing corpus..."):
                await index.build(default_chunker().chunk_all(data.documents))
            ctx = RetrievalContext(
                index=index, embedder=embedder, reranker=reranker, llm=llm
            )
            with console.status(f"running {selected.name}..."):
                outcome = await selected.retrieve(question, ctx)
                generated = await Generator(
                    llm, model=settings.generator_model
                ).generate(question, outcome.chunks)
        finally:
            await index.aclose()
            await llm.aclose()
            await embedder.aclose()
            await reranker.aclose()
            cache.close()

        console.print(
            Panel(
                generated.answer.text,
                title=f"{selected.label} - {index.size} chunks indexed",
                border_style="green" if not generated.answer.abstained else "yellow",
            )
        )
        if generated.answer.citations:
            cited = ", ".join(
                f"[{i}] {outcome.chunks[i - 1].doc_id}" for i in generated.answer.citations
            )
            console.print(f"  citations: {cited}")
        if outcome.expanded_queries:
            console.print(f"  expanded queries: {outcome.expanded_queries}")
        console.print(
            f"  retrieve {outcome.retrieve_ms:.0f} ms, rerank {outcome.rerank_ms:.0f} ms"
        )
        if show_context:
            for chunk in outcome.chunks:
                console.print(
                    Panel(
                        chunk.preview(600),
                        title=f"[{chunk.rank}] {chunk.doc_id} score={chunk.score:.4f}",
                        border_style="dim",
                    )
                )

    try:
        asyncio.run(run())
    except RAGArenaError as exc:
        console.print(f"[bold red]error[/] {exc}")
        raise typer.Exit(code=1) from exc


# --------------------------------------------------------------------------- #
# introspection
# --------------------------------------------------------------------------- #
@app.command("strategies")
def list_strategies() -> None:
    """List the built-in strategy presets."""
    table = Table(header_style="dim")
    table.add_column("name")
    table.add_column("retriever")
    table.add_column("transform")
    table.add_column("rerank")
    table.add_column("top_k / cand")
    table.add_column("description")
    for name in sorted(PRESETS):
        s = get_preset(name)
        c = s.config
        table.add_row(
            name,
            c.retriever,
            c.query_transform,
            "yes" if c.rerank else "no",
            f"{c.top_k} / {c.candidate_k}",
            s.description,
        )
    console.print(table)
    console.print(f"  default suite: {', '.join(DEFAULT_SUITE)}")


@app.command("datasets")
def list_datasets() -> None:
    """List bundled datasets."""
    table = Table(header_style="dim")
    table.add_column("name")
    table.add_column("docs", justify="right")
    table.add_column("words", justify="right")
    table.add_column("questions", justify="right")
    table.add_column("unanswerable", justify="right")
    for name in list_bundled():
        data = load_dataset(name)
        table.add_row(
            name,
            str(data.n_documents),
            f"{data.total_words:,}",
            str(data.n_questions),
            str(sum(1 for q in data.questions if not q.answerable)),
        )
    console.print(table)


@app.command("validate")
def validate_cmd(
    dataset: str = typer.Option("meridian", "--dataset", "-d", help="Bundled name or directory."),
) -> None:
    """Check a dataset's labels for the mistakes that silently skew metrics."""
    from .datasets import validate_dataset

    try:
        data = load_dataset(dataset)
    except RAGArenaError as exc:
        console.print(f"[bold red]error[/] {exc}")
        raise typer.Exit(code=1) from exc

    problems = validate_dataset(data)
    errors = [p for p in problems if not p.startswith("note:")]
    console.print(
        f"  {data.name} v{data.version}: {data.n_documents} docs, "
        f"{data.total_words:,} words, {data.n_questions} questions "
        f"({sum(1 for q in data.questions if not q.answerable)} unanswerable)"
    )
    for problem in problems:
        style = "yellow" if problem.startswith("note:") else "red"
        console.print(f"  [{style}]{problem}[/]")
    if not errors:
        console.print("  [green]labels ok[/]")
    else:
        raise typer.Exit(code=1)


@app.command("doctor")
def doctor() -> None:
    """Check configuration and provider connectivity."""

    async def run() -> None:
        settings = Settings.from_env()
        table = Table(header_style="dim")
        table.add_column("check")
        table.add_column("result")

        for key, value in settings.redacted().items():
            table.add_row(key, str(value))

        # Live probes, each isolated so one failure still reports the rest.
        from .providers import build_embedder, build_llm, build_reranker

        try:
            llm = build_llm(settings)
            response = await llm.chat(
                [{"role": "user", "content": "reply with the single word: ok"}], max_tokens=16
            )
            table.add_row("llm call", f"[green]ok[/] ({response.text[:40]!r})")
            await llm.aclose()
        except Exception as exc:
            table.add_row("llm call", f"[red]{type(exc).__name__}: {exc}[/]")

        try:
            embedder = build_embedder(settings)
            result = await embedder.embed(["connectivity probe"], input_type="query")
            table.add_row("embeddings", f"[green]ok[/] (dim {result.vectors.shape[1]})")
            await embedder.aclose()
        except Exception as exc:
            table.add_row("embeddings", f"[red]{type(exc).__name__}: {exc}[/]")

        try:
            reranker = build_reranker(settings)
            ranked = await reranker.rerank("probe", ["alpha", "beta"], top_k=2)
            table.add_row("reranker", f"[green]ok[/] ({len(ranked.ranking)} scored)")
            await reranker.aclose()
        except Exception as exc:
            table.add_row("reranker", f"[red]{type(exc).__name__}: {exc}[/]")

        try:
            data = load_dataset("meridian")
            table.add_row(
                "bundled dataset",
                f"[green]ok[/] ({data.n_documents} docs, {data.n_questions} questions)",
            )
        except Exception as exc:
            table.add_row("bundled dataset", f"[red]{exc}[/]")

        console.print(table)

    asyncio.run(run())


@app.command("report")
def report_cmd(
    result_json: Path = typer.Argument(..., help="A run JSON produced by `ragarena bench`."),
    out: Path = typer.Option(None, "--out", "-o", help="Output HTML path."),
) -> None:
    """Re-render the HTML report from a saved run."""
    payload = json.loads(Path(result_json).read_text(encoding="utf-8"))
    run = RunResult.model_validate(payload)
    target = out or result_json.with_suffix(".html")
    write_html(run, target)
    directory = target.parent
    summary_path = write_summary(run, directory / f"{run.run_id}.summary.json")
    index_path = update_index(directory, run)
    console.print(f"  report  [cyan]{target}[/]")
    console.print(f"  site    [cyan]{summary_path}[/]")
    console.print(f"  index   [cyan]{index_path}[/]")


@app.command("cache")
def cache_cmd(
    clear: bool = typer.Option(False, "--clear", help="Delete every cached provider response."),
) -> None:
    """Inspect or clear the provider response cache."""
    settings = get_settings(refresh=True)
    store = ResponseCache(settings.cache_dir, enabled=True)
    if clear:
        removed = store.clear()
        console.print(f"  cleared [cyan]{removed}[/] entries from {store.path}")
    else:
        console.print(f"  path    [cyan]{store.path}[/]")
        console.print(f"  entries [cyan]{store.size()}[/]")
    store.close()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
