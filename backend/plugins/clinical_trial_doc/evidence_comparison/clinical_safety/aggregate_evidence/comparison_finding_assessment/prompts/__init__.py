"""Formal Comparison Finding Assessment prompts and comparison-mode mapping."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from ...comparison_mode import ComparisonModeId
from .formal_prompt import (
    PROMPT_DIR_SYSTEM_FILE,
    PROMPT_DIR_USER_FILE,
    FormalPromptDefinition,
)
from .formal_prompt import (
    load_formal_prompt_definition as _load_formal_prompt_from_directory,
)

INPUT_PLACEHOLDER = "{{INPUT}}"
SUPPORTED_MESSAGE_ROLES = frozenset({"system", "user", "assistant", "tool"})

FormalComparisonFindingAssessmentPromptId = Literal[
    "comparison_finding_assessment.scope_local",
    "comparison_finding_assessment.focus_comparison",
    "comparison_finding_assessment.ib_to_dsur",
    "comparison_finding_assessment.dsur_to_ib",
]

_PROMPTS_ROOT = Path(__file__).resolve().parent

_COMPARISON_MODE_TO_PROMPT_ID: Mapping[
    ComparisonModeId, FormalComparisonFindingAssessmentPromptId
] = {
    "scope_local": "comparison_finding_assessment.scope_local",
    "focus_comparison": "comparison_finding_assessment.focus_comparison",
    "ib_to_dsur": "comparison_finding_assessment.ib_to_dsur",
    "dsur_to_ib": "comparison_finding_assessment.dsur_to_ib",
}

_PROMPT_ID_TO_DIRECTORY_NAME: Mapping[
    FormalComparisonFindingAssessmentPromptId, str
] = {
    "comparison_finding_assessment.scope_local": "scope_local",
    "comparison_finding_assessment.focus_comparison": "focus_comparison",
    "comparison_finding_assessment.ib_to_dsur": "ib_to_dsur",
    "comparison_finding_assessment.dsur_to_ib": "dsur_to_ib",
}


def resolve_formal_prompt_id(
    comparison_mode_id: ComparisonModeId,
) -> FormalComparisonFindingAssessmentPromptId:
    """Map a planned comparison mode to its formal promoted prompt identity."""

    try:
        return _COMPARISON_MODE_TO_PROMPT_ID[comparison_mode_id]
    except KeyError as exc:
        raise ValueError(f"unknown comparison_mode_id: {comparison_mode_id!r}") from exc


def resolve_formal_prompt_directory_name(
    prompt_id: FormalComparisonFindingAssessmentPromptId,
) -> str:
    """Map a formal prompt identity to its package-local storage directory name."""

    try:
        return _PROMPT_ID_TO_DIRECTORY_NAME[prompt_id]
    except KeyError as exc:
        raise ValueError(f"unknown formal prompt id: {prompt_id!r}") from exc


def formal_prompt_dir(prompt_id: FormalComparisonFindingAssessmentPromptId) -> Path:
    """Return the on-disk directory for one formal prompt identity."""

    return _PROMPTS_ROOT / resolve_formal_prompt_directory_name(prompt_id)


def load_formal_prompt_definition(
    prompt_id: FormalComparisonFindingAssessmentPromptId,
) -> FormalPromptDefinition:
    """Load one formal prompt template and its manifest metadata."""

    return _load_formal_prompt_from_directory(
        prompt_id,
        prompt_dir=formal_prompt_dir(prompt_id),
    )


def load_formal_prompt_template_messages(
    prompt_id: FormalComparisonFindingAssessmentPromptId,
) -> list[dict[str, Any]]:
    """Load system/user template messages for one formal prompt identity."""

    definition = load_formal_prompt_definition(prompt_id)
    return [
        {"role": "system", "content": definition.system_text},
        {"role": "user", "content": definition.user_text},
    ]


def _validate_prompt_template_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    placeholder_count = 0
    validated_messages: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError(f"prompt template messages[{index}] must be an object")
        if "role" not in message:
            raise ValueError(f"prompt template messages[{index}] is missing role")
        if "content" not in message:
            raise ValueError(f"prompt template messages[{index}] is missing content")
        role = message["role"]
        content = message["content"]
        if not isinstance(role, str) or role not in SUPPORTED_MESSAGE_ROLES:
            choices = ", ".join(sorted(SUPPORTED_MESSAGE_ROLES))
            raise ValueError(
                f"prompt template messages[{index}].role must be one of: {choices}"
            )
        if not isinstance(content, str):
            raise ValueError(
                f"prompt template messages[{index}].content must be a string"
            )
        placeholder_count += content.count(INPUT_PLACEHOLDER)
        validated_messages.append(dict(message))

    if placeholder_count != 1:
        raise ValueError(
            f"prompt template must contain {INPUT_PLACEHOLDER!r} exactly once; "
            f"found {placeholder_count}"
        )
    return validated_messages


def render_formal_prompt_messages(
    *,
    prompt_id: FormalComparisonFindingAssessmentPromptId,
    evidence_input: str,
) -> list[dict[str, str]]:
    """Render one formal prompt template with a materialized evidence body."""

    if not isinstance(evidence_input, str):
        raise TypeError("evidence_input must be a string")
    rendered_messages = _validate_prompt_template_messages(
        load_formal_prompt_template_messages(prompt_id)
    )
    for message in rendered_messages:
        content = message["content"]
        if INPUT_PLACEHOLDER in content:
            message["content"] = content.replace(INPUT_PLACEHOLDER, evidence_input, 1)
            break
    return rendered_messages


__all__ = [
    "INPUT_PLACEHOLDER",
    "PROMPT_DIR_SYSTEM_FILE",
    "PROMPT_DIR_USER_FILE",
    "FormalComparisonFindingAssessmentPromptId",
    "FormalPromptDefinition",
    "formal_prompt_dir",
    "load_formal_prompt_definition",
    "load_formal_prompt_template_messages",
    "render_formal_prompt_messages",
    "resolve_formal_prompt_directory_name",
    "resolve_formal_prompt_id",
]
