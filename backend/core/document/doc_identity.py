"""Reusable document identity utilities.

Neutral primitives for content hashing and processing-instance identity values.
Callers own the lifecycle decision to start a new per-document processing instance.

Identity fields:

- ``doc_id``: per processing-instance identifier (``doc_<uuid>``). A new value is
  generated on each call to :func:`build_document_processing_identity`; it is not
  stable across processing launches of the same content.

- ``file_hash``: stable content identity derived from raw file bytes (SHA-256).
  Production establishment belongs to Request File Intake; dev/bootstrap callers
  may use :func:`compute_file_hash` or :func:`compute_content_hash`.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SHA256_HEX_LENGTH = 64
FILE_HASH_PREFIX = "sha256:"


@dataclass(frozen=True)
class DocumentProcessingIdentity:
    """Pre-established identity and metadata consumed by canonical Extract."""

    doc_id: str
    file_hash: str
    file_name: str
    display_name: str
    created_at: str


def generate_doc_id() -> str:
    """Return a new per processing-instance document id (``doc_<uuid>``)."""
    return f"doc_{uuid.uuid4()}"


def _finalize_sha256_digest(hasher: hashlib._Hash) -> str:
    return f"{FILE_HASH_PREFIX}{hasher.hexdigest()}"


def compute_content_hash(content: bytes) -> str:
    """Hash in-memory raw bytes; single source of truth for content hashing.

    Returns ``sha256:<hex>``. Same bytes always yield the same hash regardless
    of filename, path, or caller.
    """
    return _finalize_sha256_digest(hashlib.sha256(content))


def validate_file_hash_format(file_hash: str, *, field: str = "file_hash") -> str:
    """Return a normalized ``sha256:<hex>`` value or raise ``ValueError``."""
    if not isinstance(file_hash, str) or not file_hash.strip():
        raise ValueError(f"{field} is required")
    value = file_hash.strip()
    if not value.startswith(FILE_HASH_PREFIX):
        raise ValueError(f"{field} must start with {FILE_HASH_PREFIX!r}")
    hex_part = value.removeprefix(FILE_HASH_PREFIX)
    if len(hex_part) != SHA256_HEX_LENGTH:
        raise ValueError(
            f"{field} hex segment must be {SHA256_HEX_LENGTH} characters"
        )
    try:
        int(hex_part, 16)
    except ValueError as exc:
        raise ValueError(f"{field} hex segment is invalid") from exc
    return value


def compute_file_hash(path: Path) -> str:
    """Hash file content; path-oriented wrapper over the shared SHA-256 primitive.

    Reads the file as binary in 1 MiB chunks, computes SHA-256, and returns
    ``sha256:<hex>``. Same bytes always yield the same hash regardless of
    caller or pipeline stage.
    """
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return _finalize_sha256_digest(hasher)


def build_display_name(path: Path) -> str:
    return path.stem


def display_name_from_file_name(file_name: str) -> str:
    """Derive display name from an original filename (stem, no path read)."""
    return Path(file_name).stem


def utc_created_at() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def require_bundle_file_hash(bundle: dict[str, Any], *, label: str) -> str:
    """Return non-empty ``file_hash`` from an artifact dict or raise ``ValueError``."""
    file_hash = bundle.get("file_hash")
    if not isinstance(file_hash, str) or not file_hash.strip():
        raise ValueError(f"{label}.file_hash is required")
    return file_hash.strip()


def build_document_processing_identity(
    *,
    file_hash: str,
    original_file_name: str,
) -> DocumentProcessingIdentity:
    """Build processing identity from an already-established content hash.

    Generates a fresh ``doc_id`` and sets ``created_at`` to the construction
    timestamp. Does not read filesystem paths or file bytes, and does not
    compute ``file_hash``. The caller owns the decision to start a new
    processing instance.
    """
    normalized_hash = validate_file_hash_format(file_hash, field="file_hash")
    if not isinstance(original_file_name, str) or not original_file_name.strip():
        raise ValueError("original_file_name is required")
    file_name = original_file_name.strip()
    return DocumentProcessingIdentity(
        doc_id=generate_doc_id(),
        file_hash=normalized_hash,
        file_name=file_name,
        display_name=display_name_from_file_name(file_name),
        created_at=utc_created_at(),
    )
