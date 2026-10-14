"""Formal Comparison Finding Consolidation prompt loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROMPT_MANIFEST_FILENAME = "manifest.json"
PROMPT_DIR_SYSTEM_FILE = "system.txt"
PROMPT_DIR_USER_FILE = "user.txt"


@dataclass(frozen=True, slots=True)
class FormalPromptDefinition:
    """One versioned formal prompt identity with on-disk templates."""

    prompt_id: str
    version: str
    system_text: str
    user_text: str


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_manifest(
    payload: Any,
    *,
    requested_prompt_id: str,
) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise TypeError("prompt manifest must be an object")
    manifest_prompt_id = _require_non_empty_str(
        payload.get("prompt_id"), field="manifest.prompt_id"
    )
    version = _require_non_empty_str(payload.get("version"), field="manifest.version")
    if manifest_prompt_id != requested_prompt_id:
        raise ValueError(
            "prompt manifest prompt_id does not match requested formal prompt "
            f"identity: expected {requested_prompt_id!r}, got {manifest_prompt_id!r}"
        )
    return manifest_prompt_id, version


def load_formal_prompt_definition(
    prompt_id: str,
    *,
    prompt_dir: Path,
) -> FormalPromptDefinition:
    """Load one formal prompt template and its manifest metadata."""

    manifest_path = prompt_dir / PROMPT_MANIFEST_FILENAME
    system_path = prompt_dir / PROMPT_DIR_SYSTEM_FILE
    user_path = prompt_dir / PROMPT_DIR_USER_FILE
    for path in (manifest_path, system_path, user_path):
        if not path.is_file():
            raise ValueError(f"formal prompt file does not exist: {path}")

    manifest_prompt_id, version = _validate_manifest(
        json.loads(manifest_path.read_text(encoding="utf-8")),
        requested_prompt_id=prompt_id,
    )
    return FormalPromptDefinition(
        prompt_id=manifest_prompt_id,
        version=version,
        system_text=system_path.read_text(encoding="utf-8"),
        user_text=user_path.read_text(encoding="utf-8").rstrip("\r\n"),
    )


__all__ = [
    "PROMPT_DIR_SYSTEM_FILE",
    "PROMPT_DIR_USER_FILE",
    "PROMPT_MANIFEST_FILENAME",
    "FormalPromptDefinition",
    "load_formal_prompt_definition",
]
