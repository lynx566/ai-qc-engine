"""LLM-facing comparison alias contract for aggregate evidence comparison."""

from __future__ import annotations

import re

COMPARISON_ALIAS_DIGIT_WIDTH = 4
COMPARISON_ALIAS_MAX_INDEX = 10**COMPARISON_ALIAS_DIGIT_WIDTH - 1

SCOPE_ALIAS_PREFIX = "H"
UNIT_ALIAS_PREFIX = "U"
SENTENCE_ALIAS_PREFIX = "T"

_ALIAS_PREFIXES = {
    "scope_alias": SCOPE_ALIAS_PREFIX,
    "unit_alias": UNIT_ALIAS_PREFIX,
    "sentence_alias": SENTENCE_ALIAS_PREFIX,
}

SCOPE_ALIAS_PATTERN = re.compile(
    rf"^{SCOPE_ALIAS_PREFIX}\d{{{COMPARISON_ALIAS_DIGIT_WIDTH}}}$"
)
UNIT_ALIAS_PATTERN = re.compile(
    rf"^{UNIT_ALIAS_PREFIX}\d{{{COMPARISON_ALIAS_DIGIT_WIDTH}}}$"
)
SENTENCE_ALIAS_PATTERN = re.compile(
    rf"^{SENTENCE_ALIAS_PREFIX}\d{{{COMPARISON_ALIAS_DIGIT_WIDTH}}}$"
)

SCOPE_ALIAS_SCAN_PATTERN = re.compile(
    rf"{SCOPE_ALIAS_PREFIX}\d{{{COMPARISON_ALIAS_DIGIT_WIDTH}}}"
)
UNIT_ALIAS_SCAN_PATTERN = re.compile(
    rf"{UNIT_ALIAS_PREFIX}\d{{{COMPARISON_ALIAS_DIGIT_WIDTH}}}"
)
SENTENCE_ALIAS_SCAN_PATTERN = re.compile(
    rf"{SENTENCE_ALIAS_PREFIX}\d{{{COMPARISON_ALIAS_DIGIT_WIDTH}}}"
)

_ALIAS_PATTERNS = {
    "scope_alias": SCOPE_ALIAS_PATTERN,
    "unit_alias": UNIT_ALIAS_PATTERN,
    "sentence_alias": SENTENCE_ALIAS_PATTERN,
}


def comparison_alias_format_description(*, prefix: str) -> str:
    """Human-readable alias format for validation errors."""

    return f"{prefix} followed by {COMPARISON_ALIAS_DIGIT_WIDTH} digits"


def format_comparison_alias(*, prefix: str, index: int) -> str:
    """Format one comparison-plan alias as prefix + fixed-width digits."""

    if not isinstance(index, int) or index < 1:
        raise ValueError(
            f"comparison alias index must be a positive integer, got {index!r}"
        )
    if index > COMPARISON_ALIAS_MAX_INDEX:
        raise ValueError(
            f"comparison alias index {index} exceeds maximum "
            f"{COMPARISON_ALIAS_MAX_INDEX} for prefix {prefix!r}"
        )
    return f"{prefix}{index:0{COMPARISON_ALIAS_DIGIT_WIDTH}d}"


def format_scope_alias(index: int) -> str:
    return format_comparison_alias(prefix=SCOPE_ALIAS_PREFIX, index=index)


def format_unit_alias(index: int) -> str:
    return format_comparison_alias(prefix=UNIT_ALIAS_PREFIX, index=index)


def format_sentence_alias(index: int) -> str:
    return format_comparison_alias(prefix=SENTENCE_ALIAS_PREFIX, index=index)


__all__ = [
    "COMPARISON_ALIAS_DIGIT_WIDTH",
    "COMPARISON_ALIAS_MAX_INDEX",
    "SCOPE_ALIAS_SCAN_PATTERN",
    "SCOPE_ALIAS_PREFIX",
    "SENTENCE_ALIAS_PATTERN",
    "SENTENCE_ALIAS_PREFIX",
    "SENTENCE_ALIAS_SCAN_PATTERN",
    "UNIT_ALIAS_PATTERN",
    "UNIT_ALIAS_PREFIX",
    "UNIT_ALIAS_SCAN_PATTERN",
    "_ALIAS_PATTERNS",
    "_ALIAS_PREFIXES",
    "comparison_alias_format_description",
    "format_comparison_alias",
    "format_scope_alias",
    "format_sentence_alias",
    "format_unit_alias",
]
