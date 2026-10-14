"""Runtime-only source bindings between Intake content identity and filesystem paths."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DocumentIntakeSourceBinding:
    """Join Intake-established source facts to a resolved runtime source path."""

    file_hash: str
    original_file_name: str
    source_path: Path


def build_intake_source_binding(
    *,
    source_path: Path,
    request_file_intake_result: Mapping[str, Any],
) -> DocumentIntakeSourceBinding:
    """Build one binding for a single-source Intake invocation."""
    document = request_file_intake_result.get("document")
    if not isinstance(document, Mapping):
        raise RuntimeError(
            "Intake source binding join failed: request_file_intake_result.document "
            "must be a mapping"
        )
    file_hash = document.get("file_hash")
    if not isinstance(file_hash, str) or not file_hash.strip():
        raise RuntimeError(
            "Intake source binding join failed: document.file_hash is required"
        )
    original_file_name = document.get("original_file_name")
    if not isinstance(original_file_name, str) or not original_file_name.strip():
        raise RuntimeError(
            "Intake source binding join failed: document.original_file_name is required"
        )
    return DocumentIntakeSourceBinding(
        file_hash=file_hash.strip(),
        original_file_name=original_file_name.strip(),
        source_path=source_path,
    )
