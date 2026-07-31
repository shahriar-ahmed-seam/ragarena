"""Run artefacts: a self-contained HTML report and JSON for the leaderboard site."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..cost import unpriced_models
from ..metrics.aggregate import ARENA_WEIGHTS, METRIC_ORDER
from ..types import RunResult

TEMPLATE_DIR = Path(__file__).parent

# Colour ramp used for the cost/quality scatter, best first.
_COLORS = ["#6ee7b7", "#60a5fa", "#c084fc", "#fbbf24", "#fb7185", "#34d399", "#f472b6", "#93c5fd"]


def _scatter_points(board: list, metric: str = "arena_score") -> list[dict[str, Any]]:
    """Map (cost, quality) into the SVG viewBox used by the template."""
    if not board:
        return []
    costs = [s.cost_per_1k_queries_uncached_usd for s in board]
    scores = [s.metrics.get(metric, 0.0) for s in board]
    cost_lo, cost_hi = min(costs), max(costs)
    score_lo, score_hi = min(scores), max(scores)
    cost_span = (cost_hi - cost_lo) or 1.0
    score_span = (score_hi - score_lo) or 1.0

    points = []
    for i, strategy in enumerate(board):
        x = 90 + 700 * (strategy.cost_per_1k_queries_uncached_usd - cost_lo) / cost_span
        y = 250 - 210 * (strategy.metrics.get(metric, 0.0) - score_lo) / score_span
        points.append(
            {
                "x": round(x, 1),
                "y": round(y, 1),
                "label": strategy.name,
                "color": _COLORS[i % len(_COLORS)],
            }
        )
    return points


def _segment_columns(run: RunResult) -> list[str]:
    seen: list[str] = []
    for strategy in run.strategies:
        for key in strategy.metrics_by_segment:
            if (key.startswith("type:") or key == "unanswerable") and key not in seen:
                seen.append(key)
    # Keep the unanswerable column last: it reads as the "did it lie?" column.
    seen.sort(key=lambda k: (k == "unanswerable", k))
    return seen


def render_html(run: RunResult) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("template.html")
    board = run.leaderboard()
    present = {m for s in run.strategies for m in s.metrics}
    return template.render(
        run=run,
        board=board,
        weights=ARENA_WEIGHTS,
        scatter=_scatter_points(board, run.primary_metric),
        segments=_segment_columns(run),
        metric_rows=[m for m in METRIC_ORDER if m in present],
        unpriced=unpriced_models(
            run.environment.generator_model,
            run.environment.judge_model,
            run.environment.embed_model,
            run.environment.rerank_model,
        ),
    )


def write_html(run: RunResult, path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(run), encoding="utf-8")
    return out


def write_json(run: RunResult, path: Path | str, *, include_traces: bool = True) -> Path:
    """Full run artefact. Traces can be dropped for a compact file."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = run.model_dump(mode="json")
    if not include_traces:
        for strategy in payload.get("strategies", []):
            strategy["traces"] = []
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def summary_payload(run: RunResult, *, max_traces: int = 60) -> dict[str, Any]:
    """Compact payload for the leaderboard website.

    Keeps aggregate numbers for every strategy but only the winner's traces, so
    the site stays fast to load while remaining inspectable.
    """
    board = run.leaderboard()
    winner = board[0].name if board else ""
    strategies = []
    for strategy in board:
        item = strategy.model_dump(mode="json")
        item["traces"] = list(item["traces"][:max_traces]) if strategy.name == winner else []
        strategies.append(item)
    return {
        "run_id": run.run_id,
        "created_at": run.created_at.isoformat(),
        "duration_s": run.duration_s,
        "primary_metric": run.primary_metric,
        "notes": run.notes,
        "dataset": run.dataset.model_dump(mode="json"),
        "environment": run.environment.model_dump(mode="json"),
        "arena_weights": ARENA_WEIGHTS,
        "metric_order": [m for m in METRIC_ORDER if any(m in s.metrics for s in run.strategies)],
        "winner": winner,
        "strategies": strategies,
    }


def write_summary(run: RunResult, path: Path | str, *, max_traces: int = 60) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(summary_payload(run, max_traces=max_traces), indent=2), encoding="utf-8"
    )
    return out


def update_index(results_dir: Path | str, run: RunResult) -> Path:
    """Maintain ``index.json``: the list of runs the leaderboard site reads.

    Idempotent per run id, so re-rendering a run updates its entry instead of
    duplicating it.
    """
    directory = Path(results_dir)
    directory.mkdir(parents=True, exist_ok=True)
    index_path = directory / "index.json"

    entries: list[dict[str, Any]] = []
    if index_path.is_file():
        try:
            loaded = json.loads(index_path.read_text(encoding="utf-8"))
            entries = [e for e in loaded.get("runs", []) if e.get("run_id") != run.run_id]
        except (json.JSONDecodeError, AttributeError):
            entries = []

    board = run.leaderboard()
    winner = board[0] if board else None
    entries.append(
        {
            "run_id": run.run_id,
            "created_at": run.created_at.isoformat(),
            "duration_s": run.duration_s,
            "notes": run.notes,
            "primary_metric": run.primary_metric,
            "dataset": run.dataset.name,
            "dataset_version": run.dataset.version,
            "n_documents": run.dataset.n_documents,
            "n_questions": winner.n_questions if winner else run.dataset.n_questions,
            "n_strategies": len(run.strategies),
            "generator_model": run.environment.generator_model,
            "judge_model": run.environment.judge_model,
            "embed_model": run.environment.embed_model,
            "rerank_model": run.environment.rerank_model,
            "winner": winner.name if winner else "",
            "winner_label": winner.label if winner else "",
            "winner_score": winner.metrics.get(run.primary_metric, 0.0) if winner else 0.0,
            "summary": f"{run.run_id}.summary.json",
        }
    )
    entries.sort(key=lambda e: e["created_at"], reverse=True)
    index_path.write_text(
        json.dumps({"generated_at": run.created_at.isoformat(), "runs": entries}, indent=2),
        encoding="utf-8",
    )
    return index_path


__all__ = [
    "render_html",
    "summary_payload",
    "update_index",
    "write_html",
    "write_json",
    "write_summary",
]
