"""Frozen Overview semantic decomposition prompt contract."""

from __future__ import annotations

from pathlib import Path

OVERVIEW_SEMANTIC_DECOMPOSITION_PROMPT_VERSION = "0.2.0"

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
_SYSTEM_PROMPT_PATH = _PROMPT_DIR / "system.txt"
_USER_PROMPT_PATH = _PROMPT_DIR / "user.txt"
_INPUT_PLACEHOLDER = "{{INPUT}}"


def _read_prompt_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_overview_assessment_messages(*, input_json: str) -> list[dict[str, str]]:
    """Build provider-neutral messages for Overview semantic assessment."""

    system_prompt = _read_prompt_text(_SYSTEM_PROMPT_PATH)
    user_template = _read_prompt_text(_USER_PROMPT_PATH)
    if _INPUT_PLACEHOLDER not in user_template:
        raise ValueError("overview user prompt must contain {{INPUT}} placeholder")
    user_prompt = user_template.replace(_INPUT_PLACEHOLDER, input_json)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


__all__ = [
    "OVERVIEW_SEMANTIC_DECOMPOSITION_PROMPT_VERSION",
    "build_overview_assessment_messages",
]
