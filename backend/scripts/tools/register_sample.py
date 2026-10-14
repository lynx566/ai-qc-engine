"""Register an immutable sample version (per-snapshot index + snapshot docx)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.samples.sample_version_index import (  # noqa: E402
    load_snapshot_record,
    register_sample,
    resolve_snapshot_path,
)

DEFAULT_SAMPLES_ROOT = BACKEND_ROOT / "samples" / "clinical_trial_doc"


def resolve_samples_root(path_str: str | None, *, flag_name: str = "--samples-root") -> Path:
    if path_str is None:
        root = DEFAULT_SAMPLES_ROOT
    else:
        root = _resolve_path(path_str)
    if not root.is_dir():
        raise SystemExit(f"{flag_name} must be a directory: {root}")
    return root.resolve()


def _resolve_user_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()

    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists():
        return cwd_candidate.resolve()

    if path.parts and path.parts[0] == BACKEND_ROOT.name:
        return (REPO_ROOT / path).resolve()

    backend_candidate = BACKEND_ROOT / path
    if backend_candidate.exists():
        return backend_candidate.resolve()

    return cwd_candidate.resolve()


def _resolve_path(path_str: str) -> Path:
    return _resolve_user_path(path_str)


def _resolve_file(path_str: str, *, flag_name: str) -> Path:
    path = _resolve_path(path_str)
    if not path.is_file():
        raise SystemExit(f"{flag_name} must be a file: {path_str!r}")
    return path


def cmd_register(args: argparse.Namespace) -> int:
    source_file = _resolve_file(args.file, flag_name="--file")
    samples_root = resolve_samples_root(args.samples_root)

    result = register_sample(
        source_file,
        samples_root,
        note=args.note or None,
        git_root=REPO_ROOT,
    )

    if result.skipped:
        print(f"Already registered: {result.file_hash}")
        print(f"  snapshot: {result.snapshot_path}")
        return 0

    print(f"Registered sample version: {result.file_hash}")
    print(f"  snapshot: {result.snapshot_path}")
    print(f"  index:    {result.index_path}")
    if result.record.get("note"):
        print(f"  note:     {result.record['note']}")
    print(
        f"  git:      {result.record.get('git_commit')} "
        f"(repo_dirty={result.record.get('repo_git_dirty')}, "
        f"file={result.record.get('source_file_git_status')})"
    )
    return 0


def cmd_lookup(args: argparse.Namespace) -> int:
    samples_root = resolve_samples_root(args.samples_root)
    snapshot = resolve_snapshot_path(args.file_hash, samples_root=samples_root)
    if snapshot is None:
        print(f"No snapshot for {args.file_hash}")
        return 1
    print(snapshot.as_posix())
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    import json

    samples_root = resolve_samples_root(args.samples_root)
    record = load_snapshot_record(args.file_hash, samples_root=samples_root)
    if record is None:
        print(f"No registration record for {args.file_hash}")
        return 1
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Register immutable sample versions "
            "(per-snapshot sample_version_index.json + snapshots/docx/.../sha256_*/)"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    reg = sub.add_parser(
        "register",
        help="Compute hash, copy snapshot, write per-snapshot sample_version_index.json",
    )
    reg.add_argument("--file", required=True, help="Source docx path")
    reg.add_argument(
        "--samples-root",
        default=None,
        help=f"Samples root (default: {DEFAULT_SAMPLES_ROOT.as_posix()})",
    )
    reg.add_argument("--note", default=None, help="Optional note (e.g. what changed)")

    lookup = sub.add_parser("lookup", help="Print snapshot path for a file_hash")
    lookup.add_argument("--file-hash", required=True, help="Content hash (sha256:...)")
    lookup.add_argument(
        "--samples-root",
        default=None,
        help=f"Samples root (default: {DEFAULT_SAMPLES_ROOT.as_posix()})",
    )

    show = sub.add_parser("show", help="Print full registration record for a file_hash")
    show.add_argument("--file-hash", required=True, help="Content hash (sha256:...)")
    show.add_argument(
        "--samples-root",
        default=None,
        help=f"Samples root (default: {DEFAULT_SAMPLES_ROOT.as_posix()})",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "register":
        return cmd_register(args)
    if args.command == "lookup":
        return cmd_lookup(args)
    if args.command == "show":
        return cmd_show(args)
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
