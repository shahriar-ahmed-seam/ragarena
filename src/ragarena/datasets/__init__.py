"""Dataset loading.

A dataset is a directory containing:

    docs/*.md | *.txt      one file per document, filename stem is the doc id
    questions.jsonl        one labelled question per line
    dataset.json           optional metadata (name, version, description)

The bundled ``meridian`` dataset ships inside the package so
``ragarena bench`` works immediately after install.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..errors import DatasetError
from ..types import Dataset, Difficulty, Document, Question, QuestionType

BUNDLED_DIR = Path(__file__).parent
DOC_SUFFIXES = {".md", ".txt", ".markdown", ".rst"}


def list_bundled() -> list[str]:
    return sorted(
        p.name
        for p in BUNDLED_DIR.iterdir()
        if p.is_dir() and (p / "questions.jsonl").is_file()
    )


def _load_documents(docs_dir: Path) -> list[Document]:
    if not docs_dir.is_dir():
        raise DatasetError(f"No docs directory at {docs_dir}")
    documents: list[Document] = []
    for path in sorted(docs_dir.iterdir()):
        if path.suffix.lower() not in DOC_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        first_line = text.splitlines()[0].lstrip("# ").strip()
        documents.append(
            Document(
                id=path.stem,
                text=text,
                title=first_line[:160],
                source=path.name,
            )
        )
    if not documents:
        raise DatasetError(f"No documents found in {docs_dir}")
    return documents


def _load_questions(path: Path, doc_ids: set[str]) -> list[Question]:
    if not path.is_file():
        raise DatasetError(f"No questions.jsonl at {path}")
    questions: list[Question] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{path}:{line_no} is not valid JSON: {exc}") from exc

        try:
            question = Question(
                id=str(raw["id"]),
                question=str(raw["question"]),
                ground_truth=raw.get("ground_truth"),
                relevant_doc_ids=[str(d) for d in raw.get("relevant_doc_ids", [])],
                relevant_snippets=[str(s) for s in raw.get("relevant_snippets", [])],
                answerable=bool(raw.get("answerable", True)),
                type=QuestionType(raw.get("type", "factoid")),
                difficulty=Difficulty(raw.get("difficulty", "medium")),
                tags=[str(t) for t in raw.get("tags", [])],
            )
        except (KeyError, ValueError) as exc:
            raise DatasetError(f"{path}:{line_no} invalid question: {exc}") from exc

        unknown = set(question.relevant_doc_ids) - doc_ids
        if unknown:
            raise DatasetError(
                f"{path}:{line_no} references unknown document ids: {sorted(unknown)}"
            )
        if question.answerable and not question.relevant_doc_ids:
            raise DatasetError(
                f"{path}:{line_no} question {question.id} is answerable but has no relevant_doc_ids"
            )
        questions.append(question)

    if not questions:
        raise DatasetError(f"No questions parsed from {path}")
    return questions


def load_dataset(name_or_path: str = "meridian") -> Dataset:
    """Load a bundled dataset by name, or any dataset directory by path."""
    candidate = BUNDLED_DIR / name_or_path
    root = candidate if candidate.is_dir() else Path(name_or_path).expanduser()
    if not root.is_dir():
        raise DatasetError(
            f"Dataset {name_or_path!r} not found. Bundled datasets: {', '.join(list_bundled())}"
        )

    documents = _load_documents(root / "docs")
    questions = _load_questions(root / "questions.jsonl", {d.id for d in documents})

    meta = {"name": root.name, "version": "1", "description": ""}
    meta_path = root / "dataset.json"
    if meta_path.is_file():
        meta.update(json.loads(meta_path.read_text(encoding="utf-8")))

    return Dataset(
        name=str(meta.get("name", root.name)),
        version=str(meta.get("version", "1")),
        description=str(meta.get("description", "")),
        documents=documents,
        questions=questions,
    )


def validate_dataset(dataset: Dataset) -> list[str]:
    """Return human-readable problems with the labels.

    A `relevant_snippets` entry that does not actually occur in a relevant
    document silently weakens chunk-level relevance judgements, and an
    unanswerable question whose text is trivially answerable makes the
    abstention metric meaningless. Both are label bugs, not code bugs, so they
    get their own check.
    """
    from ..utils import normalise_text

    problems: list[str] = []
    by_id = {d.id: d for d in dataset.documents}
    normalised = {d.id: normalise_text(d.text) for d in dataset.documents}

    seen_ids: set[str] = set()
    for question in dataset.questions:
        if question.id in seen_ids:
            problems.append(f"{question.id}: duplicate question id")
        seen_ids.add(question.id)

        for snippet in question.relevant_snippets:
            target = normalise_text(snippet)
            if not target:
                problems.append(f"{question.id}: empty relevant_snippet")
                continue
            hosts = question.relevant_doc_ids or list(by_id)
            if not any(target in normalised.get(doc_id, "") for doc_id in hosts):
                problems.append(
                    f"{question.id}: snippet not found in {hosts}: {snippet[:60]!r}"
                )

        if question.answerable and not question.ground_truth:
            problems.append(f"{question.id}: answerable but has no ground_truth")
        if not question.answerable and question.ground_truth:
            problems.append(f"{question.id}: unanswerable but has a ground_truth")
        if not question.answerable and question.relevant_doc_ids:
            problems.append(f"{question.id}: unanswerable but lists relevant_doc_ids")

    orphans = {d.id for d in dataset.documents} - {
        doc_id for q in dataset.questions for doc_id in q.relevant_doc_ids
    }
    if orphans:
        problems.append(
            f"note: {len(orphans)} document(s) are pure distractors, never a labelled answer: "
            f"{', '.join(sorted(orphans))}"
        )
    return problems


def dataset_info(dataset: Dataset):
    """Summary counts for the run artefact."""
    from ..types import DatasetInfo

    types: dict[str, int] = {}
    for q in dataset.questions:
        types[q.type.value] = types.get(q.type.value, 0) + 1
    return DatasetInfo(
        name=dataset.name,
        description=dataset.description,
        version=dataset.version,
        n_documents=dataset.n_documents,
        n_questions=dataset.n_questions,
        total_words=dataset.total_words,
        question_types=types,
    )


__all__ = ["dataset_info", "list_bundled", "load_dataset", "validate_dataset"]
