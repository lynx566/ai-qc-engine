"""
Privacy safety scanners for public pipeline artifacts.

Production-only helpers: forbidden key / path-pattern walks and raw-term scans.
Callers must pass explicit ``terms`` to :func:`scan_raw_term_leaks`; this module
does not embed document-specific golden term lists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Sequence

# Keys forbidden at any dict depth in public pipeline artifacts.
FORBIDDEN_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "normalized_text",
        "span_map",
        "original_text",
        "raw_text_before_normalize",
        "raw_text",
        "raw_rows",
    }
)

# Top-level block-group keys on public analysis_bundle (Phase 0 detect; Phase 2 enforce).
PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_KEYS: frozenset[str] = FORBIDDEN_SENSITIVE_KEYS

# block_manifest: existing safe keys plus table/meta leaks (Phase 0 detect).
PUBLIC_BLOCK_MANIFEST_FORBIDDEN_KEYS: frozenset[str] = (
    FORBIDDEN_SENSITIVE_KEYS
    | frozenset(
        {
            "source_ref",
            "document_meta",
            "privacy_transforms",
            "sentences",
            "table_ref_candidates",
        }
    )
)

PUBLIC_ZONE_MATCH_FORBIDDEN_KEYS: frozenset[str] = FORBIDDEN_SENSITIVE_KEYS | frozenset(
    {
        "original_text",
        "source_ref",
        "heading_text_stripped",
        "matched_heading_text",
        "matched_heading_text_stripped",
        "matched_heading_original_text",
    }
)

# Path suffix patterns using ``*`` for a single list-index segment.
# ``sentences`` itself is allowed on public bundles; nested pre-mask fields are not.
PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_PATH_SUFFIXES: tuple[tuple[str, ...], ...] = (
    ("sentences", "*", "normalized_text"),
    ("sentences", "*", "span_map"),
    ("sentences", "*", "original_text"),
    ("sentences", "*", "text"),
    ("sentences", "*", "start"),
    ("sentences", "*", "end"),
    ("span_map", "*", "normalized_text"),
)

PathSegment = str


@dataclass(frozen=True)
class ForbiddenKeyHit:
    key: str
    path: str


@dataclass(frozen=True)
class ForbiddenPathHit:
    pattern: tuple[str, ...]
    path: str


@dataclass(frozen=True)
class RawTermLeakHit:
    term: str
    path: str
    matched_preview: str


def path_ends_with_pattern(path_parts: Sequence[PathSegment], pattern: Sequence[str]) -> bool:
    if len(path_parts) < len(pattern):
        return False
    tail = path_parts[-len(pattern) :]
    for part, pat in zip(tail, pattern, strict=True):
        if pat == "*":
            continue
        if part != pat:
            return False
    return True


def walk_forbidden_keys(
    payload: Any,
    forbidden: frozenset[str],
    *,
    root_label: str = "artifact",
) -> list[ForbiddenKeyHit]:
    hits: list[ForbiddenKeyHit] = []

    def _walk(value: Any, *, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                child_path = f"{path}.{key_text}"
                if key_text in forbidden:
                    hits.append(ForbiddenKeyHit(key=key_text, path=child_path))
                _walk(item, path=child_path)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                _walk(item, path=f"{path}[{index}]")

    _walk(payload, path=root_label)
    return hits


def walk_forbidden_path_patterns(
    payload: Any,
    patterns: Sequence[tuple[str, ...]],
    *,
    root_label: str = "artifact",
) -> list[ForbiddenPathHit]:
    hits: list[ForbiddenPathHit] = []
    if not patterns:
        return hits

    def _walk(value: Any, *, parts: list[str], path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                child_parts = parts + [key_text]
                child_path = f"{path}.{key_text}"
                for pattern in patterns:
                    if path_ends_with_pattern(child_parts, pattern):
                        hits.append(
                            ForbiddenPathHit(pattern=tuple(pattern), path=child_path)
                        )
                _walk(item, parts=child_parts, path=child_path)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                index_text = str(index)
                child_parts = parts + [index_text]
                child_path = f"{path}[{index}]"
                for pattern in patterns:
                    if path_ends_with_pattern(child_parts, pattern):
                        hits.append(
                            ForbiddenPathHit(pattern=tuple(pattern), path=child_path)
                        )
                _walk(item, parts=child_parts, path=child_path)

    _walk(payload, parts=[root_label], path=root_label)
    return hits


def iter_string_values(
    payload: Any,
    *,
    root_label: str = "artifact",
) -> Iterator[tuple[str, str]]:
    def _walk(value: Any, *, path: str) -> Iterator[tuple[str, str]]:
        if isinstance(value, str):
            yield path, value
        elif isinstance(value, dict):
            for key, item in value.items():
                yield from _walk(item, path=f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from _walk(item, path=f"{path}[{index}]")

    yield from _walk(payload, path=root_label)


def scan_raw_term_leaks(
    payload: Any,
    terms: Sequence[str],
    *,
    root_label: str = "artifact",
    skip_paths: frozenset[str] | None = None,
    preview_limit: int = 120,
) -> list[RawTermLeakHit]:
    """Return substring leak hits. *terms* must be supplied by the caller."""
    normalized_terms = [term for term in terms if isinstance(term, str) and term.strip()]
    if not normalized_terms:
        return []

    skipped = skip_paths or frozenset()
    hits: list[RawTermLeakHit] = []
    seen_terms: set[str] = set()

    for path, text in iter_string_values(payload, root_label=root_label):
        if path in skipped or not text:
            continue
        for term in normalized_terms:
            if term in seen_terms:
                continue
            if term in text:
                hits.append(
                    RawTermLeakHit(
                        term=term,
                        path=path,
                        matched_preview=text[:preview_limit],
                    )
                )
                seen_terms.add(term)
                break
    return hits


def assert_public_analysis_bundle_safe(
    payload: dict[str, Any],
    *,
    terms: Sequence[str] | None = None,
    label: str = "analysis_bundle",
) -> None:
    """
    Enforce slim public analysis_bundle contract when privacy transform applied.

    Scans the full payload including ``document_meta`` and ``privacy_transforms``.
    """
    assert_no_forbidden_keys(
        payload,
        PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_KEYS,
        label=label,
    )
    assert_no_forbidden_path_patterns(
        payload,
        PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_PATH_SUFFIXES,
        label=label,
    )
    if terms:
        assert_no_raw_term_leaks(payload, terms, label=label)


def scan_public_block_manifest_violations(
    payload: dict[str, Any],
    terms: Sequence[str],
    *,
    root_label: str = "block_manifest",
) -> dict[str, Any]:
    forbidden_keys = walk_forbidden_keys(
        payload,
        PUBLIC_BLOCK_MANIFEST_FORBIDDEN_KEYS,
        root_label=root_label,
    )
    term_leaks = scan_raw_term_leaks(payload, terms, root_label=root_label)
    return {
        "forbidden_keys": forbidden_keys,
        "forbidden_paths": [],
        "raw_term_leaks": term_leaks,
        "passed": not forbidden_keys and not term_leaks,
    }


def assert_zone_match_public_safe(
    payload: dict[str, Any],
    *,
    terms: Sequence[str] | None = None,
    label: str = "zone_match_bundle",
) -> None:
    """Enforce public zone_match_bundle contract (forbidden keys; optional term scan)."""
    assert_no_forbidden_keys(
        payload,
        PUBLIC_ZONE_MATCH_FORBIDDEN_KEYS,
        label=label,
    )
    if terms:
        assert_no_raw_term_leaks(payload, terms, label=label)


def assert_no_forbidden_keys(
    payload: Any,
    forbidden: Iterable[str],
    *,
    label: str,
) -> None:
    hits = walk_forbidden_keys(payload, frozenset(forbidden), root_label=label)
    if hits:
        first = hits[0]
        raise ValueError(f"forbidden key {first.key!r} at {first.path}")


def assert_no_forbidden_path_patterns(
    payload: Any,
    patterns: Sequence[tuple[str, ...]],
    *,
    label: str,
) -> None:
    hits = walk_forbidden_path_patterns(payload, patterns, root_label=label)
    if hits:
        first = hits[0]
        pattern = ".".join(first.pattern)
        raise ValueError(f"forbidden path pattern {pattern!r} at {first.path}")


def assert_no_raw_term_leaks(
    payload: Any,
    terms: Sequence[str],
    *,
    label: str,
) -> None:
    hits = scan_raw_term_leaks(payload, terms, root_label=label)
    if hits:
        first = hits[0]
        raise ValueError(
            f"raw term {first.term!r} leaked at {first.path}: {first.matched_preview!r}"
        )
