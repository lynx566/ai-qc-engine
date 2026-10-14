"""Overview LLM response parsing and assessment validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from plugins.clinical_trial_doc.filter_output_projection.overview.source_items import (
    PreparedOverviewInput,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.vocabulary import (
    ASSESSMENTS_FIELD,
    normalize_content_modules,
)


def extract_json_text(raw_text: str) -> str:
    """Remove one complete, standard outer Markdown JSON fence when present."""

    text = raw_text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            opening = lines[0].strip()
            closing = lines[-1].strip()
            if opening in {"```", "```json", "```JSON"} and closing == "```":
                return "\n".join(lines[1:-1]).strip()
    return text


@dataclass(frozen=True, slots=True)
class ValidatedOverviewAssessment:
    """One validated Overview assessment mapped back from a prompt-local alias."""

    prompt_alias: str
    content_modules: tuple[str, ...]


def parse_overview_assessment_response(raw_text: str) -> dict[str, Any]:
    """Parse raw provider text into a JSON object."""

    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("overview assessment response must be non-empty text")
    try:
        parsed = json.loads(extract_json_text(raw_text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"overview assessment response must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise TypeError("overview assessment response root must be an object")
    return parsed


def _validate_assessment_item(
    item: Any,
    *,
    path: str,
) -> tuple[str, tuple[str, ...]]:
    if not isinstance(item, dict):
        raise TypeError(f"{path} must be an object")
    keys = set(item)
    if keys != {"source_id", "content_modules"}:
        raise ValueError(f"{path} must contain exactly source_id and content_modules")
    source_id = item["source_id"]
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError(f"{path}.source_id must be a non-empty string")
    content_modules = item["content_modules"]
    if not isinstance(content_modules, list):
        raise TypeError(f"{path}.content_modules must be a list")
    return source_id.strip(), normalize_content_modules(content_modules)


def validate_and_canonicalize_assessments(
    parsed: dict[str, Any],
    prepared: PreparedOverviewInput,
) -> tuple[ValidatedOverviewAssessment, ...]:
    """Validate exhaustive alias coverage and return assessments in input order."""

    if set(parsed) != {ASSESSMENTS_FIELD}:
        raise ValueError(
            f"overview assessment response must contain exactly {ASSESSMENTS_FIELD!r}"
        )
    assessments_raw = parsed[ASSESSMENTS_FIELD]
    if not isinstance(assessments_raw, list):
        raise TypeError(f"{ASSESSMENTS_FIELD} must be an array")

    by_alias: dict[str, tuple[str, ...]] = {}
    for index, item in enumerate(assessments_raw):
        alias, modules = _validate_assessment_item(
            item,
            path=f"{ASSESSMENTS_FIELD}[{index}]",
        )
        if alias in by_alias:
            raise ValueError(f"duplicate overview assessment for alias: {alias}")
        if alias not in prepared.prompt_alias_index:
            raise ValueError(f"unknown overview assessment alias: {alias}")
        by_alias[alias] = modules

    expected_aliases = [item.prompt_alias for item in prepared.items]
    missing = [alias for alias in expected_aliases if alias not in by_alias]
    if missing:
        raise ValueError(f"missing overview assessments for aliases: {', '.join(missing)}")

    return tuple(
        ValidatedOverviewAssessment(
            prompt_alias=alias,
            content_modules=by_alias[alias],
        )
        for alias in expected_aliases
    )


__all__ = [
    "ValidatedOverviewAssessment",
    "extract_json_text",
    "parse_overview_assessment_response",
    "validate_and_canonicalize_assessments",
]
