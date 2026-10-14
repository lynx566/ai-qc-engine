"""Formal consolidation prompts and comparison-mode binding."""

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

FormalComparisonFindingConsolidationPromptId = Literal[
    "comparison_finding_consolidation.focus_comparison"
]

_PROMPTS_ROOT = Path(__file__).resolve().parent

_COMPARISON_MODE_TO_PROMPT_ID: Mapping[
    ComparisonModeId, FormalComparisonFindingConsolidationPromptId
] = {
    "focus_comparison": "comparison_finding_consolidation.focus_comparison",
}

_PROMPT_ID_TO_DIRECTORY_NAME: Mapping[
    FormalComparisonFindingConsolidationPromptId, str
] = {
    "comparison_finding_consolidation.focus_comparison": "focus_comparison",
}


def resolve_formal_prompt_id(
    comparison_mode_id: ComparisonModeId,
) -> FormalComparisonFindingConsolidationPromptId:
    """Resolve the formal prompt identity bound to a comparison mode."""

    try:
        return _COMPARISON_MODE_TO_PROMPT_ID[comparison_mode_id]
    except KeyError as exc:
        raise ValueError(f"unknown comparison_mode_id: {comparison_mode_id!r}") from exc


def resolve_formal_prompt_directory_name(
    prompt_id: FormalComparisonFindingConsolidationPromptId,
) -> str:
    """Resolve package-local storage for a formal prompt identity."""

    try:
        return _PROMPT_ID_TO_DIRECTORY_NAME[prompt_id]
    except KeyError as exc:
        raise ValueError(f"unknown formal prompt id: {prompt_id!r}") from exc


def formal_prompt_dir(
    prompt_id: FormalComparisonFindingConsolidationPromptId,
) -> Path:
    return _PROMPTS_ROOT / resolve_formal_prompt_directory_name(prompt_id)


def load_formal_prompt_definition(
    prompt_id: FormalComparisonFindingConsolidationPromptId,
) -> FormalPromptDefinition:
    return _load_formal_prompt_from_directory(
        prompt_id,
        prompt_dir=formal_prompt_dir(prompt_id),
    )


def load_formal_prompt_template_messages(
    prompt_id: FormalComparisonFindingConsolidationPromptId,
) -> list[dict[str, Any]]:
    definition = load_formal_prompt_definition(prompt_id)
    return [
        {"role": "system", "content": definition.system_text},
        {"role": "user", "content": definition.user_text},
    ]


def _validate_prompt_template_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    placeholder_count = 0
    validated: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError(f"prompt template messages[{index}] must be an object")
        role = message.get("role")
        content = message.get("content")
        if role not in SUPPORTED_MESSAGE_ROLES:
            raise ValueError(f"prompt template messages[{index}].role is invalid")
        if not isinstance(content, str):
            raise ValueError(
                f"prompt template messages[{index}].content must be a string"
            )
        placeholder_count += content.count(INPUT_PLACEHOLDER)
        validated.append(dict(message))
    if placeholder_count != 1:
        raise ValueError(
            f"prompt template must contain {INPUT_PLACEHOLDER!r} exactly once; "
            f"found {placeholder_count}"
        )
    return validated


def render_formal_prompt_messages(
    *,
    prompt_id: FormalComparisonFindingConsolidationPromptId,
    consolidation_input_text: str,
) -> list[dict[str, str]]:
    """Render one formal prompt with a materialized consolidation input."""

    if not isinstance(consolidation_input_text, str):
        raise TypeError("consolidation_input_text must be a string")
    messages = _validate_prompt_template_messages(
        load_formal_prompt_template_messages(prompt_id)
    )
    for message in messages:
        content = message["content"]
        if INPUT_PLACEHOLDER in content:
            message["content"] = content.replace(
                INPUT_PLACEHOLDER, consolidation_input_text, 1
            )
            break
    return messages


__all__ = [
    "INPUT_PLACEHOLDER",
    "PROMPT_DIR_SYSTEM_FILE",
    "PROMPT_DIR_USER_FILE",
    "FormalComparisonFindingConsolidationPromptId",
    "FormalPromptDefinition",
    "formal_prompt_dir",
    "load_formal_prompt_definition",
    "load_formal_prompt_template_messages",
    "render_formal_prompt_messages",
    "resolve_formal_prompt_directory_name",
    "resolve_formal_prompt_id",
]
