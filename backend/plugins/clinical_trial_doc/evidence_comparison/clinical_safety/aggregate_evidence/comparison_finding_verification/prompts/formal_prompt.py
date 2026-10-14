"""Formal Comparison Finding Verification prompt definition and manifest loading."""

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
    """One versioned formal prompt identity with on-disk template text."""

    prompt_id: str
    version: str
    system_text: str
    user_text: str


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _read_utf8_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _validate_manifest(
    payload: Any,
    *,
    requested_prompt_id: str,
) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise TypeError("prompt manifest must be an object")
    manifest_prompt_id = _require_non_empty_str(
        payload.get("prompt_id"),
        field="manifest.prompt_id",
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
    if not manifest_path.is_file():
        raise ValueError(
            f"formal prompt must contain {PROMPT_MANIFEST_FILENAME!r}: {manifest_path}"
        )
    if not system_path.is_file():
        raise ValueError(
            f"formal prompt must contain {PROMPT_DIR_SYSTEM_FILE!r}: {system_path}"
        )
    if not user_path.is_file():
        raise ValueError(
            f"formal prompt must contain {PROMPT_DIR_USER_FILE!r}: {user_path}"
        )

    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_prompt_id, version = _validate_manifest(
        manifest_payload,
        requested_prompt_id=prompt_id,
    )
    return FormalPromptDefinition(
        prompt_id=manifest_prompt_id,
        version=version,
        system_text=_read_utf8_text(system_path),
        user_text=_read_utf8_text(user_path),
    )


__all__ = [
    "PROMPT_MANIFEST_FILENAME",
    "FormalPromptDefinition",
    "load_formal_prompt_definition",
]
