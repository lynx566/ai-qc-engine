"""Browse and search pipeline runs via session index.json files."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stop_points import (
    EVIDENCE_SOURCE_PREPARATION_ASSESS_STEP,
    EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_STEP,
    EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_STEP,
    EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP,
)

DOC_ID_SHORT_LEN = 12

CURRENT_STEPS = (
    "extract",
    "prepare_analysis",
    "filter",
    "doc_meta",
    "route",
    EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP,
    EVIDENCE_SOURCE_PREPARATION_ASSESS_STEP,
    EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_STEP,
    EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_STEP,
)

LEGACY_STEPS = (
    "mask",
    "tag_prepare",
    "tag",
    "compare_candidate",
    "group",
    "match_candidate_select",
    "match_resolve_members",
    "process_prepare",
    "process_assess",
    "process_eligibility",
    "process_assemble",
)

KNOWN_STEPS = CURRENT_STEPS + LEGACY_STEPS


@dataclass
class RunIndexRecord:
    index_path: Path
    index_root: Path
    mtime: float
    step: str
    created_at: str
    documents: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentRunRecord:
    index: RunIndexRecord
    doc_id: str
    label: str
    privacy_level: str
    file_hash: str | None
    outputs: dict[str, str]


def resolve_runs_root(explicit: str | Path | None = None) -> Path:
    """Resolve runs directory: explicit flag, then cwd/runs, then backend/runs."""
    if explicit is not None:
        root = Path(explicit)
        if not root.is_absolute():
            cwd_candidate = Path.cwd() / root
            if cwd_candidate.is_dir():
                return cwd_candidate.resolve()
            backend_candidate = BACKEND_ROOT / root
            if backend_candidate.is_dir():
                return backend_candidate.resolve()
        return root.resolve()
    cwd_runs = Path.cwd() / "runs"
    if cwd_runs.is_dir():
        return cwd_runs.resolve()
    backend_runs = BACKEND_ROOT / "runs"
    return backend_runs.resolve()


def _parse_index_file(index_path: Path) -> RunIndexRecord | None:
    try:
        text = index_path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"warning: skip {index_path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print(f"warning: skip {index_path}: expected JSON object", file=sys.stderr)
        return None
    index_root = index_path.parent.resolve()
    step = str(data.get("step") or "unknown")
    created_at = str(data.get("created_at") or "")
    documents = data.get("documents")
    if not isinstance(documents, list):
        documents = []
    return RunIndexRecord(
        index_path=index_path.resolve(),
        index_root=index_root,
        mtime=index_path.stat().st_mtime,
        step=step,
        created_at=created_at,
        documents=[doc for doc in documents if isinstance(doc, dict)],
        raw=data,
    )


def _is_legacy_index_path(index_path: Path) -> bool:
    return "_legacy" in index_path.parts


def _is_legacy_step(step: str) -> bool:
    return step in LEGACY_STEPS


def load_run_indexes(
    runs_root: Path,
    *,
    include_legacy: bool = False,
) -> list[RunIndexRecord]:
    """Load index.json under *runs_root*, newest mtime first.

    By default skips indexes under ``runs/_legacy/`` and indexes whose ``step``
    is a legacy pipeline stage (``tag_prepare``, ``tag``, …). Pass
    ``include_legacy=True`` to include both.
    """
    runs_root = runs_root.resolve()
    if not runs_root.is_dir():
        return []
    records: list[RunIndexRecord] = []
    for index_path in runs_root.rglob("index.json"):
        if not index_path.is_file():
            continue
        if not include_legacy and _is_legacy_index_path(index_path):
            continue
        record = _parse_index_file(index_path)
        if record is None:
            continue
        if not include_legacy and _is_legacy_step(record.step):
            continue
        records.append(record)
    records.sort(key=lambda r: r.mtime, reverse=True)
    return records


def flatten_documents(index_record: RunIndexRecord) -> list[DocumentRunRecord]:
    """Expand session index into per-document records."""
    docs: list[DocumentRunRecord] = []
    for entry in index_record.documents:
        doc_id = str(entry.get("doc_id") or "unknown")
        label = entry.get("label")
        if not isinstance(label, str) or not label.strip():
            label = doc_id
        privacy = str(entry.get("privacy_level") or "")
        file_hash = entry.get("file_hash")
        if file_hash is not None and not isinstance(file_hash, str):
            file_hash = str(file_hash)
        outputs = entry.get("outputs")
        if not isinstance(outputs, dict):
            outputs = {}
        safe_outputs = {
            str(k): str(v)
            for k, v in outputs.items()
            if isinstance(k, str) and v is not None
        }
        docs.append(
            DocumentRunRecord(
                index=index_record,
                doc_id=doc_id,
                label=label,
                privacy_level=privacy,
                file_hash=file_hash,
                outputs=safe_outputs,
            )
        )
    return docs


def short_doc_id(doc_id: str, *, length: int = DOC_ID_SHORT_LEN) -> str:
    if len(doc_id) <= length:
        return doc_id
    return doc_id[:length]


def session_display_path(index_record: RunIndexRecord, runs_root: Path) -> str:
    """Human-readable session path (prefer runs/... under backend or cwd)."""
    runs_root = runs_root.resolve()
    index_root = index_record.index_root
    for base in (Path.cwd().resolve(), BACKEND_ROOT.resolve()):
        try:
            rel = index_root.relative_to(base)
            return rel.as_posix()
        except ValueError:
            continue
    try:
        rel = index_root.relative_to(runs_root)
        return f"runs/{rel.as_posix()}"
    except ValueError:
        return index_root.as_posix()


def format_output_path(
    rel_path: str,
    index_root: Path,
    *,
    shorten_doc_dirs: bool = True,
) -> tuple[str, str]:
    """
    Return (display_relative, resolved_posix) for an output entry.

    *display_relative* may shorten doc_id directory segments; *resolved_posix*
    is index_root / rel_path.
    """
    display = rel_path
    if shorten_doc_dirs and rel_path:
        parts = rel_path.split("/")
        if parts and parts[0].startswith("doc_"):
            parts[0] = short_doc_id(parts[0]) + "..."
            display = "/".join(parts)
    resolved = (index_root / rel_path).resolve().as_posix()
    return display, resolved


def _haystack(record: RunIndexRecord, doc: DocumentRunRecord | None, runs_root: Path) -> str:
    parts = [
        record.step,
        record.created_at,
        session_display_path(record, runs_root),
        str(record.index_path),
    ]
    if doc is not None:
        parts.extend([doc.doc_id, doc.label, doc.file_hash or ""])
    return "\n".join(parts).lower()


def search_records(
    records: list[RunIndexRecord],
    query: str,
    *,
    runs_root: Path,
) -> list[tuple[RunIndexRecord, DocumentRunRecord | None]]:
    """Case-insensitive match on doc_id, label, file_hash, and index/session path."""
    q = query.strip().lower()
    if not q:
        return []
    hits: list[tuple[RunIndexRecord, DocumentRunRecord | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for record in records:
        docs = flatten_documents(record)
        if not docs:
            if q in _haystack(record, None, runs_root):
                key = (str(record.index_path), None)
                if key not in seen:
                    seen.add(key)
                    hits.append((record, None))
            continue
        for doc in docs:
            if q in _haystack(record, doc, runs_root):
                key = (str(record.index_path), doc.doc_id)
                if key not in seen:
                    seen.add(key)
                    hits.append((record, doc))
    return hits


def find_by_doc_id(
    records: list[RunIndexRecord],
    doc_id_prefix: str,
) -> list[DocumentRunRecord]:
    """All document entries whose doc_id starts with *doc_id_prefix* (case-sensitive)."""
    prefix = doc_id_prefix.strip()
    if not prefix:
        return []
    found: list[DocumentRunRecord] = []
    for record in records:
        for doc in flatten_documents(record):
            if doc.doc_id.startswith(prefix):
                found.append(doc)
    found.sort(key=lambda d: (d.index.mtime, d.index.step), reverse=True)
    return found


def _print_session_header(record: RunIndexRecord, runs_root: Path) -> None:
    session = session_display_path(record, runs_root)
    print(f"[{record.step}] {session}")
    if record.created_at:
        print(f"  created_at: {record.created_at}")


def _print_document(doc: DocumentRunRecord) -> None:
    sid = short_doc_id(doc.doc_id)
    print(f"  {sid}  {doc.label}")
    if doc.privacy_level:
        print(f"    privacy_level: {doc.privacy_level}")
    if doc.file_hash:
        print(f"    file_hash: {doc.file_hash}")
    if doc.outputs:
        print("  outputs:")
        for key, rel in sorted(doc.outputs.items()):
            display, resolved = format_output_path(rel, doc.index.index_root)
            print(f"    {key} -> {display}")
            if display != resolved:
                print(f"      ({resolved})")


def cmd_latest(
    records: list[RunIndexRecord],
    *,
    runs_root: Path,
    step: str | None,
    limit: int,
) -> None:
    filtered = records
    if step:
        filtered = [r for r in records if r.step == step]
    for record in filtered[:limit]:
        _print_session_header(record, runs_root)
        docs = flatten_documents(record)
        if not docs:
            print("  (no documents)")
        else:
            for doc in docs:
                _print_document(doc)
        print()


def cmd_search(
    records: list[RunIndexRecord],
    *,
    runs_root: Path,
    query: str,
) -> None:
    hits = search_records(records, query, runs_root=runs_root)
    if not hits:
        print(f"No matches for {query!r}")
        return
    for record, doc in hits:
        _print_session_header(record, runs_root)
        if doc is None:
            print("  (session match, no document entries)")
        else:
            _print_document(doc)
        print()


def cmd_find(
    records: list[RunIndexRecord],
    *,
    runs_root: Path,
    doc_id_prefix: str,
) -> None:
    docs = find_by_doc_id(records, doc_id_prefix)
    if not docs:
        print(f"No runs for doc_id prefix {doc_id_prefix!r}")
        return
    steps_seen = sorted({d.index.step for d in docs}, key=lambda s: KNOWN_STEPS.index(s) if s in KNOWN_STEPS else 99)
    print(f"doc_id prefix {doc_id_prefix!r}: {len(docs)} run(s), steps: {', '.join(steps_seen)}")
    print()
    for doc in docs:
        _print_session_header(doc.index, runs_root)
        _print_document(doc)
        print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Browse pipeline runs via index.json (no artifact reads).",
    )
    parser.add_argument(
        "--runs-root",
        metavar="PATH",
        help="Runs directory (default: ./runs if present, else backend/runs)",
    )
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help=(
            "Also scan runs/_legacy/ and indexes for legacy steps "
            f"({', '.join(LEGACY_STEPS)}); skipped by default"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    latest = sub.add_parser("latest", help="Show most recent run sessions")
    latest.add_argument(
        "--step",
        help=(
            "Filter by pipeline step (current: "
            + ", ".join(CURRENT_STEPS)
            + "; use --include-legacy for legacy steps)"
        ),
    )
    latest.add_argument("--limit", type=int, default=10, help="Max sessions (default: 10)")

    search = sub.add_parser("search", help="Search label, doc_id, file_hash, or path")
    search.add_argument("--q", required=True, help="Case-insensitive keyword")

    find_p = sub.add_parser("find", help="Find all runs for a doc_id (prefix ok)")
    find_p.add_argument("--doc-id", required=True, dest="doc_id", help="doc_id or prefix")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runs_root = resolve_runs_root(args.runs_root)
    if not runs_root.is_dir():
        print(f"runs root not found: {runs_root}", file=sys.stderr)
        return 1
    records = load_run_indexes(runs_root, include_legacy=args.include_legacy)
    if args.command == "latest":
        cmd_latest(records, runs_root=runs_root, step=args.step, limit=args.limit)
    elif args.command == "search":
        cmd_search(records, runs_root=runs_root, query=args.q)
    elif args.command == "find":
        cmd_find(records, runs_root=runs_root, doc_id_prefix=args.doc_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
