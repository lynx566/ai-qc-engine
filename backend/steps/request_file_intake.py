"""Request File Intake pipeline step: one in-memory file → one content identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from artifacts.request_file_intake import build_request_file_intake_result
from core.document.doc_identity import compute_content_hash


@dataclass(frozen=True)
class RequestFileInput:
    """One in-memory request file before content hashing."""

    content: bytes
    original_file_name: str


@dataclass(frozen=True)
class RequestFileIntakeStepResult:
    """In-memory Step output: formal single-document artifact."""

    request_file_intake_result: dict[str, Any]


def _validate_input(record: RequestFileInput) -> RequestFileInput:
    if not isinstance(record, RequestFileInput):
        raise TypeError("input must be a RequestFileInput")
    if not isinstance(record.content, (bytes, bytearray)):
        raise TypeError("input.content must be bytes")
    if not isinstance(record.original_file_name, str) or not record.original_file_name.strip():
        raise ValueError("input.original_file_name is required")
    return RequestFileInput(
        content=bytes(record.content),
        original_file_name=record.original_file_name.strip(),
    )


def run(input: RequestFileInput) -> RequestFileIntakeStepResult:
    """Hash one request file and return a formal single-document artifact."""
    validated = _validate_input(input)
    file_hash = compute_content_hash(validated.content)
    request_file_intake_result = build_request_file_intake_result(
        file_hash=file_hash,
        original_file_name=validated.original_file_name,
    )
    return RequestFileIntakeStepResult(
        request_file_intake_result=request_file_intake_result,
    )
