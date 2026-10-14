"""Materialize multipart uploads into local paths for application create-flow."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from bridge.document_consistency_qc.upload_staging_session import UploadStagingSession

_UPLOAD_SLOT_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


class UploadMaterializationError(ValueError):
    """Raised when uploaded multipart parts cannot be materialized."""


def materialize_slot_uploads(
    *,
    uploads: Mapping[str, tuple[str, bytes]],
    staging_root: Path,
    upload_staging_session_id: str,
    staging_session: UploadStagingSession,
) -> dict[str, Path]:
    """Write uploaded bytes to controlled local files keyed by slot_id.

    ``uploads`` maps ``slot_id`` to ``(original_file_name, content)``.
    Each create-flow request gets one ``upload_staging_session_id`` directory
    under ``staging_root`` that may contain one subdirectory per slot.
    """

    if not uploads:
        raise UploadMaterializationError("at least one slot upload is required")

    session_dir = staging_root / upload_staging_session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    staging_session.initialize()

    materialized: dict[str, Path] = {}
    try:
        for slot_id, (original_file_name, content) in uploads.items():
            if not _UPLOAD_SLOT_PATTERN.fullmatch(slot_id):
                raise UploadMaterializationError(
                    f"upload field name must be a slot_id, got {slot_id!r}"
                )
            if not isinstance(original_file_name, str) or not original_file_name.strip():
                raise UploadMaterializationError(
                    f"upload for slot {slot_id!r} is missing a file name"
                )
            if not content:
                raise UploadMaterializationError(f"upload for slot {slot_id!r} is empty")
            slot_dir = session_dir / slot_id
            slot_dir.mkdir(parents=True, exist_ok=True)
            target_path = slot_dir / Path(original_file_name).name
            target_path.write_bytes(content)
            materialized[slot_id] = target_path.resolve()
            staging_session.record_materialized_slot(
                slot_id=slot_id,
                original_file_name=Path(original_file_name).name,
            )
    except (UploadMaterializationError, OSError) as exc:
        staging_session.record_failed(str(exc))
        raise
    return materialized


__all__ = [
    "UploadMaterializationError",
    "materialize_slot_uploads",
]
